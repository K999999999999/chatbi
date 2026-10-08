# Sourced by local; all mutations run while the local operation lock is held.
prepare_operations_directories() {
    python3 - "$ROOT" <<'PY'
import sys
from pathlib import Path
from scripts.local_backup import secure_directory
root = Path(sys.argv[1]) / '.local'
for path in ('operations', 'backup-keys', 'backups', 'operations/api'):
    secure_directory(root / path)
secure_directory(root / 'operations/public', public=True)
PY
}

require_operations_image() {
    CHATBI_OPERATIONS_IMAGE="$(python3 - "$ROOT" <<'PY'
import json, re, sys
from pathlib import Path
from scripts.local_backup import secure_file
value = json.loads(secure_file(Path(sys.argv[1]) / '.local/operations/tool-image.json'))
assert value['format'] == 1 and re.fullmatch('sha256:[0-9a-f]{64}', value['image_id'])
assert re.fullmatch('[0-9a-f]{40}', value['source_commit'])
print(value['image_id'])
PY
    )" || fail '备份工具未构建或身份记录无效；先运行 ./local build-operations。'
    docker image inspect "$CHATBI_OPERATIONS_IMAGE" >/dev/null 2>&1 \
        || fail '已登记备份工具镜像不存在；先运行 ./local build-operations。'
    local expected_revision actual_revision
    expected_revision="$(python3 - "$ROOT" <<'PYCODE'
import json, sys
from pathlib import Path
from scripts.local_backup import secure_file
print(json.loads(secure_file(Path(sys.argv[1]) / '.local/operations/tool-image.json'))['source_commit'])
PYCODE
    )" || fail '备份工具来源记录无效。'
    actual_revision="$(docker image inspect --format '{{index .Config.Labels "org.opencontainers.image.revision"}}' "$CHATBI_OPERATIONS_IMAGE")"
    [[ "$actual_revision" == "$expected_revision" ]] || fail '备份工具镜像来源不一致。'
    export CHATBI_OPERATIONS_IMAGE
}

build_operations_image() {
    require_docker
    [[ -z "$(git status --porcelain)" ]] || fail '备份工具必须从 clean commit 构建。'
    prepare_operations_directories
    local source_commit image_tag image_id
    source_commit="$(git rev-parse HEAD)"
    image_tag="chatbi-local-operations:build-$source_commit"
    docker build --file "$ROOT/docker/operations.Dockerfile" \
        --build-arg "CHATBI_SOURCE_COMMIT=$source_commit" --tag "$image_tag" "$ROOT"
    image_id="$(docker image inspect --format '{{.Id}}' "$image_tag")"
    python3 - "$ROOT" "$source_commit" "$image_id" <<'PY'
import sys
from pathlib import Path
from scripts.local_backup import atomic_json
root, source, image = sys.argv[1:]
atomic_json(Path(root) / '.local/operations/tool-image.json',
            {'format':1, 'source_commit':source, 'image_id':image})
PY
    printf '备份工具已登记，age v1.3.2 / PG16；尚未初始化密钥或备份。\n'
}

capture_backup_source() {
    python3 -m scripts.local_backup_source "$ROOT" \
        || fail '无法核对实际运行的备份来源；原API保持运行。'
}

run_manual_backup() {
    prepare_operations_directories
    require_operations_image
    capture_backup_source
    compose run --rm -T --no-deps operations backup --host-locked \
        || fail '备份失败；未删除已有副本，原API保持运行。'
}
