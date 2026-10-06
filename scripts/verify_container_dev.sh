#!/usr/bin/env bash
# 实际Compose链路验收；凭证仅存在于临时0600文件，退出时清理专用账号。
set -euo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd "$root"
mode=${1:-isolated}
if [[ "$mode" != isolated && "$mode" != real ]]; then
    echo '用法: scripts/verify_container_dev.sh {isolated|real}' >&2; exit 2
fi
browser_image=chatbi-browser-dev:local
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
mkdir -p "$work/report"
export CHATBI_DEV_ENV_FILE=${CHATBI_DEV_ENV_FILE:-$root/.env}
export CHATBI_DEV_COMPOSE_OVERRIDE="$work/compose.yml"
export CHATBI_DEV_UID=$(id -u) CHATBI_DEV_GID=$(id -g)
export CHATBI_CONTAINER_REPORT_DIR="$work/report"
printf 'services:\n' > "$work/compose.yml"
if [[ "$mode" == isolated ]]; then
    export COMPOSE_PROJECT_NAME="chatbi-verify-$(date +%s)-$$"
    export POSTGRES_PUBLISHED_PORT=${CHATBI_VERIFY_PG_PORT:-15433}
    export CHATBI_DEV_API_PORT=${CHATBI_VERIFY_API_PORT:-18080}
    export CHATBI_DEV_WEB_PORT=${CHATBI_VERIFY_WEB_PORT:-18173}
    browser_image=chatbi-browser-result-export-v1:local
    export RAG_OUTPUT_DIR="$work/rag"
    mkdir -p "$RAG_OUTPUT_DIR"
    cat >> "$work/compose.yml" <<'YAML'
  api:
    image: chatbi-result-export-v1:local
  web:
    image: chatbi-web-result-export-v1:local
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
      - type: bind
        source: ${CHATBI_CONTAINER_REPORT_DIR}
        target: /reports
        bind: {create_host_path: false}
YAML
compose=(docker compose --project-directory "$root" --env-file "$CHATBI_DEV_ENV_FILE"
    -f docker-compose.yml -f docker-compose.dev.yml -f "$work/compose.yml")
tools() {
    "${compose[@]}" run --rm --no-deps -T --entrypoint python tools \
        -m tests.container_dev_support "$@"
}
finish() {
    result=$?
    trap - EXIT
    evidence_root=
    if [[ -f "$work/report/account.json" ]]; then
        if ! tools cleanup; then
            echo "专用账号清理未通过，保留私有工作目录用于恢复：$work" >&2
            exit 1
        fi
    fi
    mkdir -p reports/browser-real
    if [[ -f "$work/report/browser.json" ]]; then
        cp "$work/report/browser.json" "reports/browser-real/container-$(date +%s)-${mode}.json"
    fi
    if [[ "$mode" == isolated ]]; then
        # 只对本次新建project清理；检查project前缀和Compose实际名称，绝不使用日常项目。
        [[ "$COMPOSE_PROJECT_NAME" == chatbi-verify-* ]] || exit 1
        for volume in "${COMPOSE_PROJECT_NAME}_postgres_data" "${COMPOSE_PROJECT_NAME}_qdrant_data"; do
            if docker volume inspect "$volume" >/dev/null 2>&1; then
                label=$(docker volume inspect --format '{{index .Labels "com.docker.compose.project"}}' "$volume")
                [[ "$label" == "$COMPOSE_PROJECT_NAME" ]] || exit 1
            fi
        done
        "${compose[@]}" down --volumes
    fi
    rm -f "$work/report/credentials.env"
    if [[ "$mode" == isolated && "$result" == 0 ]]; then
        [[ "$work" == /tmp/chatbi-container-verify.* ]] || exit 1
        evidence_root="reports/browser-real-artifacts/result-export-v1/compose-$(date +%s)"
        mkdir -p "$evidence_root"
        for file in browser.json export-verification.json cleanup.json runtime.json images.jsonl; do
            [[ -f "$work/report/$file" ]] && cp "$work/report/$file" "$evidence_root/$file"
        done
        find "$work/report" -maxdepth 1 -type f -name 'r5-*' -exec cp -- {} "$evidence_root/" \;
        rm -rf -- "$work"
    fi
    if ((result == 0)); then
        echo "容器验收通过：$mode；账号与资源清理已核实。运行记录：${evidence_root:-$work/report}"
    fi
    exit "$result"
}
trap finish EXIT
"$root/dev" build
"$root/dev" infra
"$root/dev" migrate
if [[ "$mode" == isolated ]]; then
    "${compose[@]}" run --rm --no-deps -T -e CHATBI_CONTAINER_ISOLATED=1 \
        --entrypoint python tools -m tests.container_dev_support admin
    start=$SECONDS
    "$root/dev" build-rag > "$work/report/rag-build.log" 2>&1
    echo "CPU索引构建耗时：$((SECONDS-start))秒"
fi
"$root/dev" up
tools prepare
docker inspect $("${compose[@]}" ps -q api web) --format '{{json .Image}}' > "$work/report/images.jsonl"
"${compose[@]}" exec -T api python -c \
    'import json,os,hashlib,pathlib,urllib.parse; p=pathlib.Path(os.environ["RAG_MODEL_DIR"])/"config.json"; print(json.dumps({"llm_model":os.environ["LLM_MODEL"],"provider_host":urllib.parse.urlsplit(os.environ["LLM_BASE_URL"]).hostname,"embedding_device":os.environ["RAG_EMBEDDING_DEVICE"],"model_config_sha256":hashlib.sha256(p.read_bytes()).hexdigest()}))' > "$work/report/runtime.json"
docker build --target browser -f docker/node-dev.Dockerfile \
    --build-arg "NODE_BASE=${CHATBI_DEV_NODE_BASE:-node:24.21.0-bookworm-slim@sha256:0e0ff40c39bc087845bfb27465a0df4ea419520094bc35842ff83dd8cbe6f9b6}" \
    -t "$browser_image" .
web_id=$("${compose[@]}" ps -q web)
run_browser() {
docker run --rm --network "container:$web_id" --user "$(id -u):$(id -g)" \
    --env-file "$work/report/credentials.env" \
    -e CHATBI_CONTAINER_REAL_E2E=1 \
    -e "CHATBI_CONTAINER_RESTART_PHASE=${CHATBI_CONTAINER_RESTART_PHASE:-0}" \
    -e "CHATBI_CONTAINER_BASE_URL=http://127.0.0.1:${CHATBI_DEV_WEB_PORT:-5173}" \
    -e "CHATBI_CONTAINER_COMMIT=$(git rev-parse HEAD)" \
    -e "CHATBI_CONTAINER_GIT_DIRTY=$dirty" \
    -v "$work/report:/reports" \
    -v "$root/frontend/tests:/workspace/frontend/tests:ro" \
    -v "$root/frontend/src:/workspace/frontend/src" \
    -v "$root/src:/workspace/backend-src" \
    -v "$root/frontend/playwright.container.config.ts:/workspace/frontend/playwright.container.config.ts:ro" \
    -v "$root/frontend/playwright.container-reporter.ts:/workspace/frontend/playwright.container-reporter.ts:ro" \
    "$browser_image" npx playwright test --config playwright.container.config.ts
}
"${compose[@]}" exec -T api python -c \
    'import os; assert not any("MIGRATOR" in k for k in os.environ); print("API迁移身份隔离通过。")'
run_browser
# Ticket 04 needs to prove recovery from a process that did not finish its worker.
# Kill only this profile's API container; the PostgreSQL named volume remains untouched.
api_id=$("${compose[@]}" ps -q api)
[[ -n "$api_id" ]] || { echo '找不到当前验收 API 容器。' >&2; exit 1; }
docker kill "$api_id" >/dev/null
"$root/dev" down
"$root/dev" up
"$root/dev" status
tools execution-recovery
tools expire-analysis
web_id=$("${compose[@]}" ps -q web)
CHATBI_CONTAINER_RESTART_PHASE=1 run_browser
tools persistence
tools verify-exports
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
