#!/usr/bin/env bash
# 实际Compose链路验收；凭证仅存在于临时0600文件，退出时清理专用账号。
set -euo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd "$root"
host_root=${LOCAL_WORKSPACE_FOLDER:-$root}
source "$root/scripts/dev_environment.sh"
source "$root/scripts/container_hot_reload.sh"
prepare_git_mounts
git_worktree=$(git -C "$root" rev-parse --absolute-git-dir)
mode=${1:-isolated}
if [[ "$mode" != isolated && "$mode" != real ]]; then
    echo '用法: scripts/verify_container_dev.sh {isolated|real}' >&2; exit 2
fi
export CHATBI_DEV_ENV_FILE=${CHATBI_DEV_ENV_FILE:-$root/.env}
validate_env_file_permissions "$CHATBI_DEV_ENV_FILE" || exit 2
browser_image=chatbi-browser-dev:local
python_image=${CHATBI_DEV_PYTHON_IMAGE:-chatbi-python-dev:local}
dirty=false
if [[ -n "$(git status --porcelain)" ]]; then
    dirty=true
    if [[ "${CHATBI_CONTAINER_ALLOW_DIRTY:-0}" != 1 ]]; then
        echo '正式容器验收要求clean candidate；开发诊断可显式设置CHATBI_CONTAINER_ALLOW_DIRTY=1。' >&2
        exit 2
    fi
fi
work=$(mktemp -d /tmp/chatbi-container-verify.XXXXXX)
chmod 700 "$work"
umask 077
mkdir -p "$work/report"
mkdir -p "$root/reports/browser-real" "$root/reports/browser-real-artifacts"
export CHATBI_PUBLISHED_REPORT_DIR=$(host_source_path "$root/reports")
export CHATBI_DEV_COMPOSE_OVERRIDE="$work/compose.yml"
export CHATBI_DEV_UID=$(id -u) CHATBI_DEV_GID=$(id -g)
export CHATBI_DEV_SECCOMP_PROFILE=${CHATBI_DEV_SECCOMP_PROFILE:-$root/docker/third-party/playwright-seccomp-profile.json}
export CHATBI_CONTAINER_REPORT_DIR="$work/report"
business_run_id=
printf 'services:\n' > "$work/compose.yml"
hot_reload_ready=false
hot_reload_root="$work/hot-reload"
if [[ "$mode" == isolated ]]; then
    export COMPOSE_PROJECT_NAME="chatbi-verify-$(date +%s)-$$"
    export POSTGRES_PUBLISHED_PORT=${CHATBI_VERIFY_PG_PORT:-15433}
    export CHATBI_DEV_API_PORT=${CHATBI_VERIFY_API_PORT:-18080}
    export CHATBI_DEV_WEB_PORT=${CHATBI_VERIFY_WEB_PORT:-18173}
    browser_image=chatbi-browser-result-export-v1:local
    model_revision=$(sed -nE 's/^DEFAULT_MODEL_REVISION = "([0-9a-f]{40})"$/\1/p' "$root/src/rag_offline/config.py")
    [[ "$model_revision" =~ ^[0-9a-f]{40}$ ]] || {
        echo '无法解析固定模型 revision；隔离验收停止。' >&2
        exit 2
    }
    [[ ! -L "$root/.model-cache" ]] || {
        echo '隔离模型缓存目录不能是符号链接；请保留并检查现有目录。' >&2
        exit 2
    }
    export RAG_MODEL_DIR="$root/.model-cache/bge-m3-${model_revision:0:12}"
    [[ ! -L "$RAG_MODEL_DIR" ]] || {
        echo '隔离模型快照目录不能是符号链接；请保留并检查现有目录。' >&2
        exit 2
    }
    mkdir -p -- "$RAG_MODEL_DIR"
    export RAG_OUTPUT_DIR="$work/rag"
    mkdir -p "$RAG_OUTPUT_DIR"
    if container_hot_reload_init "$root" "$work" "$COMPOSE_PROJECT_NAME" \
        "$CHATBI_DEV_COMPOSE_OVERRIDE"; then
        :
    else
        hot_reload_init_status=$?
        echo "热更新备份初始化失败；源码目录未写入，临时证据保留在：$hot_reload_root" >&2
        exit "$hot_reload_init_status"
    fi
    hot_backend=$HOT_RELOAD_BACKEND
    hot_style=$HOT_RELOAD_STYLE
    hot_reload_ready=true
    echo "隔离热更新副本及恢复备份：$hot_reload_root"
    cat >> "$work/compose.yml" <<YAML
  api:
    image: chatbi-result-export-v1:local
    volumes:
      - type: bind
        source: $hot_backend
        target: /workspace/src/query_api/app.py
        read_only: false
  web:
    image: chatbi-web-result-export-v1:local
    volumes:
      - type: bind
        source: $hot_style
        target: /workspace/frontend/src/style.css
        read_only: false
  qdrant:
    ports: !override []
YAML
fi
cat >> "$work/compose.yml" <<'YAML'
  tools:
    volumes:
      - type: bind
        source: ${LOCAL_WORKSPACE_FOLDER:-.}/tests
        target: /workspace/tests
        read_only: true
YAML
compose=(docker compose --project-directory "$root" --env-file "$CHATBI_DEV_ENV_FILE"
    -f docker-compose.yml -f docker-compose.dev.yml -f "$work/compose.yml")
tools() {
    tools_module -m tests.container_dev_support "$@"
}
tools_module() {
    "${compose[@]}" run --rm --no-deps -T --entrypoint python \
        -v "$host_root:$root:ro" "${git_mounts[@]}" \
        -e "GIT_DIR=$git_worktree" -e "GIT_WORK_TREE=$root" \
        "${git_environment[@]}" \
        -v "$CHATBI_CONTAINER_REPORT_DIR:/reports" \
        -v "$CHATBI_PUBLISHED_REPORT_DIR:/published-reports" \
        tools "$@"
}
verification_module() {
    docker run --rm --init --user "$CHATBI_DEV_UID:$CHATBI_DEV_GID" \
        --workdir "$root" --network none \
        -e PYTHONDONTWRITEBYTECODE=1 \
        -v "$host_root:$root:ro" "${git_mounts[@]}" \
        -e "GIT_DIR=$git_worktree" -e "GIT_WORK_TREE=$root" \
        "${git_environment[@]}" \
        -v "$CHATBI_PUBLISHED_REPORT_DIR:/published-reports" \
        --entrypoint python "$python_image" "$@"
}
business_step_start() {
    verification_module -m scripts.verification_report step-start \
        --reports-directory /published-reports/.verification-state \
        --run-id "$business_run_id" --name "$1"
}
business_step_finish() {
    local name=$1 exit_code=$2 machine_result=${3:-} forced_status=${4:-}
    local -a arguments=(
        -m scripts.verification_report step-finish
        --reports-directory /published-reports/.verification-state
        --run-id "$business_run_id" --name "$name" --exit-code "$exit_code"
    )
    if [[ -n "$machine_result" ]]; then
        arguments+=(--playwright "/reports/$machine_result" --counts-only)
    else
        arguments+=(--counts-not-applicable)
    fi
    if [[ -n "$forced_status" ]]; then
        arguments+=(--status "$forced_status")
    elif ((exit_code == 130 || exit_code == 143)); then
        arguments+=(--status interrupted)
    fi
    if [[ -n "$machine_result" ]]; then tools_module "${arguments[@]}"; else verification_module "${arguments[@]}"; fi
}
business_begin() {
    business_run_id=$(verification_module -m scripts.verification_report begin \
        --repository-root "$root" --reports-directory /published-reports/.verification-state \
        --kind business-acceptance --scope container-dev --runner dev-container \
        --runtime browser --mode "$mode" \
        --step prepare --step browser-initial --step restart-recovery \
        --step browser-restart --step exports --step cleanup \
        --counted-step browser-initial --counted-step browser-restart)
}
business_finish() {
    local result=$1 cleanup_status=$2 file
    local -a arguments=(
        -m scripts.verification_report finish
        --repository-root "$root" --reports-directory /published-reports/.verification-state
        --run-id "$business_run_id" --output-directory /published-reports/browser-real
        --artifact-root /published-reports --exit-code "$result"
        --cleanup-status "$cleanup_status"
    )
    for file in browser.json cleanup.json runtime.json images.jsonl export-verification.json \
        recovery.json hot-reload-recovery.json model-prepared.json test-summary-initial.json test-summary-restart.json \
        test-errors-initial.json test-errors-restart.json; do
        [[ ( "$file" != model-prepared.json && "$file" != hot-reload-recovery.json ) \
            || -f "$root/reports/browser-real-artifacts/$business_run_id/$file" ]] || continue
        arguments+=(--artifact "browser-real-artifacts/$business_run_id/$file")
    done
    if ((result == 130 || result == 143)); then arguments+=(--interrupted); fi
    if verification_module "${arguments[@]}"; then
        echo "业务验收报告：reports/browser-real/$business_run_id.json"
    else
        echo '业务验收总结未能安全发布；本次结果按失败 / 未确认处理。' >&2
        return 2
    fi
}
finish() {
    local result=$? cleanup_status=not_run cleanup_result=0 cleanup_step_status=not_run artifact_directory file label
    trap - EXIT
    trap '' INT TERM
    if [[ "$hot_reload_ready" == true ]]; then
        container_hot_reload_restore "$work/report" || result=1
    fi
    if [[ -n "$business_run_id" ]]; then business_step_start cleanup || cleanup_result=1; fi
    if [[ -f "$work/report/account.json" || -f "$work/report/account.pending.json" ]]; then
        tools cleanup || cleanup_result=1
    elif ((result == 0)); then
        cleanup_result=1
    fi
    if [[ "$mode" == isolated ]]; then
        # 只对本次新建project清理；检查project前缀和Compose实际名称，绝不使用日常项目。
        [[ "$COMPOSE_PROJECT_NAME" == chatbi-verify-* ]] || cleanup_result=1
        for volume in "${COMPOSE_PROJECT_NAME}_postgres_data" "${COMPOSE_PROJECT_NAME}_qdrant_data"; do
            if docker volume inspect "$volume" >/dev/null 2>&1; then
                label=$(docker volume inspect --format '{{index .Labels "com.docker.compose.project"}}' "$volume") || cleanup_result=1
                [[ "$label" == "$COMPOSE_PROJECT_NAME" ]] || cleanup_result=1
            fi
        done
        "${compose[@]}" down --volumes || cleanup_result=1
    fi
    rm -f "$work/report/credentials.env" || cleanup_result=1

    if [[ -n "$business_run_id" ]]; then
        artifact_directory="$root/reports/browser-real-artifacts/$business_run_id"
        if mkdir -m 700 -- "$artifact_directory"; then
            for file in browser.json cleanup.json runtime.json images.jsonl export-verification.json \
                recovery.json hot-reload-recovery.json model-prepared.json test-summary-initial.json test-summary-restart.json \
                test-errors-initial.json test-errors-restart.json; do
                if [[ -f "$work/report/$file" ]]; then
                    cp -- "$work/report/$file" "$artifact_directory/$file" || result=1
                fi
            done
            find "$work/report" -maxdepth 1 -type f -name 'r5-*' \
                -exec cp -- {} "$artifact_directory/" \; || result=1
        else
            echo "无法创建唯一业务证据目录：$artifact_directory" >&2
            result=1
        fi
    fi

    if ((cleanup_result == 0)); then
        if [[ -f "$work/report/account.json" || -f "$work/report/account.pending.json" ]]; then
            cleanup_status=passed
            cleanup_step_status=passed
        else
            cleanup_status=not_run
            cleanup_step_status=not_run
            ((result != 0)) || result=1
        fi
    else
        cleanup_status=failed
        cleanup_step_status=failed
        result=1
    fi
    if ((result == 0)); then
        if [[ "$work" == /tmp/chatbi-container-verify.* ]]; then
            rm -rf -- "$work" || {
                result=1
                cleanup_status=failed
                cleanup_result=1
                cleanup_step_status=failed
            }
        else
            result=1
            cleanup_status=failed
            cleanup_result=1
            cleanup_step_status=failed
        fi
    fi
    if [[ -n "$business_run_id" ]]; then
        business_step_finish cleanup "$cleanup_result" '' "$cleanup_step_status" || result=2
        business_finish "$result" "$cleanup_status" || result=2
    else
        echo '业务验收报告未能启动；验收未开始，且不生成通过结论。' >&2
    fi
    [[ ! -d "$work" ]] || echo "诊断暂存目录（含可恢复源码备份）：$work" >&2
    exit "$result"
}
trap finish EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
if ! "$root/dev" build; then
    echo '开发镜像准备失败；业务验收报告工具尚不可用，因此本次结果未确认。' >&2
    exit 1
fi
business_begin

prepare_business() {
    "$root/dev" infra && "$root/dev" migrate || return $?
    if [[ "$mode" == isolated ]]; then
        "${compose[@]}" run --rm --no-deps -T -e CHATBI_CONTAINER_ISOLATED=1 \
            --entrypoint python tools -m tests.container_dev_support admin || return $?
        "$root/dev" prepare-model > "$work/report/model-prepared.json" || return $?
        local started=$SECONDS
        "$root/dev" build-rag > "$work/report/rag-build.log" 2>&1 || return $?
        echo "CPU索引构建耗时：$((SECONDS-started))秒"
    fi
    "$root/dev" up || return $?
    tools prepare || return $?
    local container_output
    local -a containers=()
    container_output=$("${compose[@]}" ps -q api web) || return $?
    [[ -n "$container_output" ]] || return 1
    mapfile -t containers <<< "$container_output"
    docker inspect "${containers[@]}" --format '{{json .Image}}' > "$work/report/images.jsonl" || return $?
    "${compose[@]}" exec -T api python -c \
        'import json,os,hashlib,pathlib,urllib.parse; p=pathlib.Path(os.environ["RAG_MODEL_DIR"])/"config.json"; print(json.dumps({"llm_model":os.environ["LLM_MODEL"],"provider_host":urllib.parse.urlsplit(os.environ["LLM_BASE_URL"]).hostname,"embedding_device":os.environ["RAG_EMBEDDING_DEVICE"],"model_config_sha256":hashlib.sha256(p.read_bytes()).hexdigest()}))' \
        > "$work/report/runtime.json" || return $?
    docker build --target browser -f docker/node-dev.Dockerfile \
        --build-arg "NODE_BASE=${CHATBI_DEV_NODE_BASE:-node:24.21.0-bookworm-slim@sha256:0e0ff40c39bc087845bfb27465a0df4ea419520094bc35842ff83dd8cbe6f9b6}" \
        -t "$browser_image" . || return $?
    web_id=$("${compose[@]}" ps -q web) || return $?
    [[ -n "$web_id" ]]
}
run_browser() {
    local -a hot_reload_mounts=()
    local hot_reload_enabled=0
    if [[ "$mode" == isolated ]]; then
        hot_reload_enabled=1
        hot_reload_mounts=(
            -v "$hot_backend:/workspace/backend-src/query_api/app.py:rw"
            -v "$hot_style:/workspace/frontend/src/style.css:rw"
        )
    fi
    docker run --rm --network "container:$web_id" --user "$(id -u):$(id -g)" \
        --env-file "$work/report/credentials.env" \
        -e LANG=C.UTF-8 -e LC_ALL=C.UTF-8 -e CHATBI_CONTAINER_REAL_E2E=1 \
        -e "CHATBI_CONTAINER_HOT_RELOAD_ENABLED=$hot_reload_enabled" \
        -e "CHATBI_CONTAINER_RESTART_PHASE=${CHATBI_CONTAINER_RESTART_PHASE:-0}" \
        -e "CHATBI_CONTAINER_BASE_URL=http://127.0.0.1:${CHATBI_DEV_WEB_PORT:-5173}" \
        -e "CHATBI_CONTAINER_COMMIT=$(git rev-parse HEAD)" \
        -e "CHATBI_CONTAINER_GIT_DIRTY=$dirty" \
        -v "$work/report:/reports" \
        -v "$root/frontend/tests:/workspace/frontend/tests:ro" \
        -v "$root/frontend/src:/workspace/frontend/src:ro" \
        -v "$root/src:/workspace/backend-src:ro" \
        -v "$root/frontend/playwright.container.config.ts:/workspace/frontend/playwright.container.config.ts:ro" \
        -v "$root/frontend/playwright.container-reporter.ts:/workspace/frontend/playwright.container-reporter.ts:ro" \
        -v "$root/frontend/test-support:/workspace/frontend/test-support:ro" \
        "${hot_reload_mounts[@]}" \
        "$browser_image" npx playwright test --config playwright.container.config.ts "$@"
}
browser_initial() {
    local result=0
    run_browser --grep-invert '停止重启后读取长期快照、重登录、续聊与显式重查' || result=$?
    if [[ -f "$work/report/test-summary.json" ]]; then
        mv -- "$work/report/test-summary.json" "$work/report/test-summary-initial.json" || result=1
    elif ((result == 0)); then result=1; fi
    if [[ -f "$work/report/test-errors.json" ]]; then
        mv -- "$work/report/test-errors.json" "$work/report/test-errors-initial.json" || result=1
    fi
    return "$result"
}

restart_recovery() {
    local api_id
    "${compose[@]}" exec -T api python -c \
        'import os; assert not any("MIGRATOR" in k for k in os.environ); print("API迁移身份隔离通过。")' || return $?
    # 仅终止本验收 profile 的 API；PostgreSQL volume 保持不变。
    api_id=$("${compose[@]}" ps -q api) || return $?
    [[ -n "$api_id" ]] || return 1
    docker kill "$api_id" >/dev/null && "$root/dev" down && "$root/dev" up && \
        "$root/dev" status && tools execution-recovery && tools expire-analysis
}

browser_restart() {
    local result=0
    CHATBI_CONTAINER_RESTART_PHASE=1 run_browser --grep '停止重启后读取长期快照、重登录、续聊与显式重查' || result=$?
    if [[ -f "$work/report/test-summary.json" ]]; then
        mv -- "$work/report/test-summary.json" "$work/report/test-summary-restart.json" || result=1
    elif ((result == 0)); then result=1; fi
    if [[ -f "$work/report/test-errors.json" ]]; then
        mv -- "$work/report/test-errors.json" "$work/report/test-errors-restart.json" || result=1
    fi
    return "$result"
}

exports_and_workers() {
    tools persistence && tools verify-exports || return $?
    "${compose[@]}" exec -T api python - <<'PY'
import os
import pathlib
import tempfile

root = pathlib.Path(tempfile.gettempdir()) / "chatbi-result-exports"
entries = sorted(path.name for path in root.iterdir())
lock = root / ".runtime.lock"
assert entries == [".runtime.lock"]
assert lock.is_file() and not lock.is_symlink()
assert lock.stat().st_mode & 0o777 == 0o600
workers = []
for path in pathlib.Path("/proc").glob("[0-9]*/cmdline"):
    if path.parent.name == str(os.getpid()):
        continue
    try:
        if b"export_worker.py" in path.read_bytes():
            workers.append(path.parent.name)
    except OSError:
        continue
assert not workers, "导出 worker 仍在运行"
print("导出临时目录仅保留锁文件，未遗留 worker。")
PY
}

run_business_step() {
    local name=$1 machine_result=$2 runner=$3 step_result
    business_step_start "$name" || return 2
    if "$runner"; then step_result=0; else step_result=$?; fi
    business_step_finish "$name" "$step_result" "$machine_result" || return 2
    return "$step_result"
}

run_business_step prepare '' prepare_business || exit $?
run_business_step browser-initial test-summary-initial.json browser_initial || exit $?
run_business_step restart-recovery '' restart_recovery || exit $?
run_business_step browser-restart test-summary-restart.json browser_restart || exit $?
run_business_step exports '' exports_and_workers || exit $?
