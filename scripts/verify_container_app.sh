#!/usr/bin/env bash
# 打包应用的空卷验收；不操作日常开发或旧Stable资源。
set -euo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
project="chatbi-app-verify-$(date +%s)-$$"
work=$(mktemp -d /tmp/chatbi-app-verify.XXXXXX)
chmod 700 "$work"
mkdir -p "$work/report"
port=${CHATBI_VERIFY_APP_PORT:-18280}
source_env=${CHATBI_APP_ENV_FILE:-$root/.env}
[[ -f "$source_env" ]] || { echo '真实验收缺少配置。' >&2; exit 2; }
source_env=$(cd -- "$(dirname -- "$source_env")" && pwd)/$(basename -- "$source_env")
dirty=false
[[ -z $(git -C "$root" status --porcelain) ]] || dirty=true
compose=(docker compose -p "$project" --project-directory "$root" --env-file "$work/config.env" -f "$root/docker-compose.app.yml")
tools() {
    "${compose[@]}" run --rm --no-deps -T --user "$(id -u):$(id -g)" \
        -v "$root/tests:/workspace/tests:ro" -v "$work/report:/reports" \
        -e CHATBI_CONTAINER_ISOLATED=1 --entrypoint python tools \
        -m tests.container_dev_support "$@"
}
finish() {
    result=$?
    trap - EXIT
    if [[ -f "$work/report/account.json" ]]; then tools cleanup || result=1; fi
    # Compose project标签验证后才删除此次新建资源。
    for name in postgres_data qdrant_data model_data rag_data; do
        volume="${project}_$name"
        if docker volume inspect "$volume" >/dev/null 2>&1; then
            [[ $(docker volume inspect --format '{{index .Labels "com.docker.compose.project"}}' "$volume") == "$project" ]] || exit 1
        fi
    done
    "${compose[@]}" down --volumes >/dev/null || result=1
    rm -f "$work/config.env" "$work/report/credentials.env"
    evidence="$root/reports/deployment-simplification/$project"
    mkdir -p "$evidence"
    cp -a "$work/report/." "$evidence/"
    rm -rf -- "$work"
    echo "标准容器验收结束：退出码 $result；证据 $evidence"
    exit "$result"
}

# 仅Docker内解析配置，白名单复制真实LLM参数；临时数据库凭据另行生成。
docker run --rm -i --user "$(id -u):$(id -g)" \
    -v "$root:$root:ro" -v "$source_env:/source.env:ro" -v "$work:$work" -w "$root" \
    --entrypoint python chatbi-python-dev:local - "$root" "$work" "$port" <<'PY'
import secrets, sys
from pathlib import Path
from dotenv import dotenv_values
root, work, port = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
source = dotenv_values('/source.env')
if not source.get('LLM_API_KEY'):
    raise SystemExit('真实容器验收缺少LLM配置。')
values = {key: value for key, value in source.items() if key.startswith('LLM_') and value is not None}
values.update(POSTGRES_DB='chatbi_mvp', POSTGRES_MIGRATOR_USER='chatbi_migrator',
              POSTGRES_APP_USER='chatbi_app', POSTGRES_CONTROL_DB='chatbi_control',
              POSTGRES_CONTROL_APP_USER='chatbi_control_user', CHATBI_APP_PORT=port)
for key in ('POSTGRES_MIGRATOR_PASSWORD','POSTGRES_APP_PASSWORD','POSTGRES_CONTROL_APP_PASSWORD',
            'QDRANT_API_KEY','CHATBI_ADMIN_SECRET_KEY'):
    values[key] = secrets.token_hex(32)
def quote(value):
    if '\n' in value or '\r' in value:
        raise SystemExit('配置不支持多行值。')
    return "'" + value.replace('\\', '\\\\').replace("'", "\\'") + "'"
path = work / 'config.env'
path.write_text('\n'.join(key+'='+quote(value) for key, value in values.items())+'\n')
path.chmod(0o600)
model = Path(source.get('RAG_MODEL_DIR') or '.model-cache/bge-m3-5617a9f61b02')
(work / 'model-path').write_text(str(model if model.is_absolute() else root / model))
PY
trap finish EXIT
"${compose[@]}" up -d postgres qdrant
"${compose[@]}" exec -T postgres sh /workspace/database/init/wait_for_base_initialization.sh
"${compose[@]}" run --rm --no-deps -T migrator
tools admin
"${compose[@]}" run --rm --no-deps -T tools --help >/dev/null
read -r model_path < "$work/model-path" || true
if [[ -f "$model_path/config.json" ]]; then
    docker run --rm -v "$model_path:/cache:ro" -v "${project}_model_data:/opt/chatbi-model" \
        --user 0:0 --entrypoint sh chatbi-app:local -c 'cp -a /cache/. /opt/chatbi-model/'
    "${compose[@]}" run --rm --no-deps -T -e HF_HUB_OFFLINE=1 tools prepare-model
else
    "${compose[@]}" run --rm --no-deps -T tools prepare-model
fi
"${compose[@]}" run --rm --no-deps -T tools build-rag
"${compose[@]}" run --rm --no-deps -T tools verify
"${compose[@]}" up -d --wait --wait-timeout 180 api
for ((i=0;i<60;i++)); do
    if "${compose[@]}" exec -T api python -c 'import urllib.request,json; assert json.load(urllib.request.urlopen("http://127.0.0.1:8000/ready",timeout=3))["status"]=="ready"' >/dev/null 2>&1; then break; fi
    sleep 1
done
"${compose[@]}" exec -T api python -c 'import urllib.request,json; assert json.load(urllib.request.urlopen("http://127.0.0.1:8000/ready",timeout=3))["status"]=="ready"'
tools prepare
browser() {
    docker run --rm --init --network host --user "$(id -u):$(id -g)" \
        --env-file "$work/report/credentials.env" -e CHATBI_CONTAINER_REAL_E2E=1 \
        -e CHATBI_CONTAINER_TARGET=compose-packaged-api -e "CHATBI_CONTAINER_BASE_URL=http://127.0.0.1:$port" \
        -e "CHATBI_CONTAINER_RESTART_PHASE=${1:-0}" -e "CHATBI_CONTAINER_COMMIT=$(git -C "$root" rev-parse HEAD)" \
        -e "CHATBI_CONTAINER_GIT_DIRTY=$dirty" -e LANG=C.UTF-8 -e LC_ALL=C.UTF-8 \
        -v "$work/report:/reports" -v "$root/frontend/tests:/workspace/frontend/tests:ro" \
        -v "$root/frontend/src:/workspace/frontend/src:ro" \
        -v "$root/frontend/test-support:/workspace/frontend/test-support:ro" \
        -v "$root/frontend/playwright.container.config.ts:/workspace/frontend/playwright.container.config.ts:ro" \
        -v "$root/frontend/playwright.container-reporter.ts:/workspace/frontend/playwright.container-reporter.ts:ro" \
        chatbi-browser-dev:local npx playwright test --config playwright.container.config.ts \
        --grep '实际 Compose 网页|停止重启'
}
browser 0
"${compose[@]}" kill api
"${compose[@]}" stop
"${compose[@]}" up -d --wait --wait-timeout 180
tools execution-recovery
tools expire-analysis
browser 1
tools persistence
docker run --rm -v "$root:$root:ro" -v "$work/report:/reports" -w "$root" \
    --entrypoint python chatbi-python-dev:local -m tests.container_dev_support verify-exports
