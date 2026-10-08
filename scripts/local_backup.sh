# Sourced by local. Host needs only the existing Bash/Docker/coreutils/flock tools.
check_operations_root() {
    local mode
    [[ -d "$ROOT/.local" && ! -L "$ROOT/.local" && "$(stat -c '%u' "$ROOT/.local")" == "$(id -u)" ]] \
        || fail '本机状态根目录归属未确认。'
    mode="$(stat -c '%a' "$ROOT/.local")"
    (( (8#$mode & 022) == 0 )) || fail '本机状态根目录不能允许其他账号写入。'
}

prepare_operations_directories() {
    local path mode expected
    check_operations_root
    for path in operations backup-keys backups operations/api operations/public; do
        expected=700
        [[ "$path" != operations/public ]] || expected=755
        if [[ ! -e "$ROOT/.local/$path" && ! -L "$ROOT/.local/$path" ]]; then
            mkdir -m 700 "$ROOT/.local/$path" || fail '无法创建受限运维目录。'
            [[ "$expected" != 755 ]] || chmod 755 "$ROOT/.local/$path"
        fi
        [[ -d "$ROOT/.local/$path" && ! -L "$ROOT/.local/$path" ]] \
            || fail '运维目录类型未确认。'
        mode="$(stat -c '%a' "$ROOT/.local/$path")"
        [[ "$mode" == "$expected" && "$(stat -c '%u' "$ROOT/.local/$path")" == "$(id -u)" ]] \
            || fail '运维目录权限或归属未确认。'
    done
}

require_operations_image() {
    check_operations_root
    local record="$ROOT/.local/operations/tool-image.env" key value expected_revision='' actual_revision seen_source=false seen_image=false
    [[ -f "$record" && ! -L "$record" && "$(stat -c '%a' "$record")" == 600 && "$(stat -c '%u' "$record")" == "$(id -u)" ]] \
        || fail '备份工具未构建或记录归属无效；先运行 ./local build-operations。'
    CHATBI_OPERATIONS_IMAGE=''
    while IFS='=' read -r key value; do
        case "$key" in
            CHATBI_OPERATIONS_IMAGE_ID)
                [[ "$seen_image" == false ]] || fail '备份工具记录包含重复字段。'
                CHATBI_OPERATIONS_IMAGE="$value"; seen_image=true ;;
            CHATBI_OPERATIONS_SOURCE_COMMIT)
                [[ "$seen_source" == false ]] || fail '备份工具记录包含重复字段。'
                expected_revision="$value"; seen_source=true ;;
            *) fail '备份工具记录包含未知字段。' ;;
        esac
    done < "$record"
    [[ "$CHATBI_OPERATIONS_IMAGE" =~ ^sha256:[0-9a-f]{64}$ && "$expected_revision" =~ ^[0-9a-f]{40}$ ]] \
        || fail '备份工具身份记录无效。'
    actual_revision="$(docker image inspect --format '{{index .Config.Labels "org.opencontainers.image.revision"}}' "$CHATBI_OPERATIONS_IMAGE")" \
        || fail '已登记备份工具镜像不存在。'
    [[ "$actual_revision" == "$expected_revision" ]] || fail '备份工具镜像来源不一致。'
    export CHATBI_OPERATIONS_IMAGE
}

build_operations_image() {
    require_docker
    [[ -z "$(git status --porcelain)" ]] || fail '备份工具必须从 clean commit 构建。'
    prepare_operations_directories
    local source_commit image_tag image_id temporary
    source_commit="$(git rev-parse HEAD)"
    image_tag="chatbi-local-operations:build-$source_commit"
    docker build --file "$ROOT/docker/operations.Dockerfile" \
        --build-arg "CHATBI_SOURCE_COMMIT=$source_commit" --tag "$image_tag" "$ROOT"
    image_id="$(docker image inspect --format '{{.Id}}' "$image_tag")"
    temporary="$(mktemp "$ROOT/.local/operations/.tool-image-XXXXXX")"
    chmod 600 "$temporary"
    printf 'CHATBI_OPERATIONS_SOURCE_COMMIT=%s\nCHATBI_OPERATIONS_IMAGE_ID=%s\n' \
        "$source_commit" "$image_id" > "$temporary"
    mv -T "$temporary" "$ROOT/.local/operations/tool-image.env"
    printf '备份工具已登记，age v1.3.2 / PG16；尚未初始化密钥或备份。\n'
}

capture_backup_source() (
    umask 077
    local api postgres raw="$ROOT/.local/operations/capture" asset_reader
    api="$(stable_container_ids api)"
    postgres="$(stable_container_ids postgres)"
    [[ "$api" =~ ^[0-9a-f]{12,64}$ && "$postgres" =~ ^[0-9a-f]{12,64}$ ]] \
        || fail '备份需要唯一且归属明确的API/PG容器。'
    [[ ! -e "$raw" && ! -L "$raw" ]] || fail '来源捕获残留未确认；拒绝覆盖。'
    mkdir -m 700 "$raw"
    # This directory was created exclusively by this invocation.
    trap 'rm -rf -- "$raw"' EXIT
    docker inspect --format '{{json .}}' "$api" > "$raw/api.json"
    docker inspect --format '{{json .}}' "$postgres" > "$raw/postgres.json"
    cp --no-dereference "$CONFIG_FILE" "$raw/config.env"
    cp --no-dereference "$SECRET_FILE" "$raw/secrets.env"
    docker exec "$api" cat /opt/chatbi-release.json > "$raw/release.json"
    docker exec "$api" python -c 'import json; from pathlib import Path; print(json.dumps({"operations_status": Path("/workspace/src/bootstrap/operations_socket.py").is_file()}))' > "$raw/capabilities.json"
    docker exec "$api" cat /opt/chatbi-compatibility.json > "$raw/compatibility.json"
    asset_reader='import json,os,sys; from pathlib import Path
try:
 root=Path(os.environ.get("RAG_OUTPUT_DIR","/opt/chatbi-rag")); pointer=(root/"current.json").read_bytes()
 assert len(pointer)<=1048576
 ref=Path(json.loads(pointer)["manifest_path"])
 assert not ref.is_absolute() and ".." not in ref.parts
 target=root/ref
 assert not target.is_symlink() and target.resolve().is_relative_to(root.resolve())
 data=pointer if sys.argv[1]=="current" else target.read_bytes()
 assert len(data)<=1048576
 sys.stdout.buffer.write(data)
except Exception: sys.exit(1)'
    docker exec "$api" python -c "$asset_reader" current > "$raw/rag-current.json"
    docker exec "$api" python -c "$asset_reader" manifest > "$raw/rag-manifest.json"
    compose run --rm -T --no-deps operations capture --host-locked \
        || fail '无法核对实际运行的备份来源；原API保持运行。'
)

run_manual_backup() {
    prepare_operations_directories
    require_operations_image
    capture_backup_source
    compose run --rm -T --no-deps operations backup --host-locked \
        || fail '备份失败；未删除已有副本，原API保持运行。'
}

start_backup_scheduler() {
    if [[ ! -f "$ROOT/.local/operations/tool-image.env" ]]; then
        # No tool is available to interpret/publish state; retain any previous projection.
        printf '备份工具未初始化：API已运行，但自动备份不可用；先build-operations/init-backup。\n' >&2
        return 0
    fi
    require_operations_image
    capture_backup_source
    compose up -d --no-deps --force-recreate backup
}
