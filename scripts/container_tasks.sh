#!/usr/bin/env bash
# 宿主只调用Docker；Python、Node和测试依赖在容器内运行。
set -euo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
task=${1:-help}
shift || true
python_image=${CHATBI_DEV_PYTHON_IMAGE:-chatbi-python-dev:local}
browser_image=${CHATBI_DEV_BROWSER_IMAGE:-chatbi-browser-dev:local}
node_image=${CHATBI_DEV_NODE_IMAGE:-chatbi-node-dev:local}
uid=$(id -u)
gid=$(id -g)

python_run() {
    docker run --rm --init --user "$uid:$gid" --workdir "$root" \
        -v "$root:$root:ro" -e PYTHONDONTWRITEBYTECODE=1 \
        -e GIT_CONFIG_COUNT=1 -e GIT_CONFIG_KEY_0=safe.directory -e "GIT_CONFIG_VALUE_0=$root" \
        "${python_options[@]}" --entrypoint python "$python_image" "$@"
}
python_options=()

# 配置结构测试需Compose CLI，但不取得Docker socket或daemon权限。
compose_cli_mounts() {
    local cli compose_plugin
    cli=$(command -v docker)
    compose_plugin=$(docker info --format '{{range .ClientInfo.Plugins}}{{if eq .Name "compose"}}{{.Path}}{{end}}{{end}}')
    [[ -n "$compose_plugin" ]] || { echo 'Docker Compose CLI不可用。' >&2; return 2; }
    python_options+=(-v "$cli:/usr/local/bin/docker:ro" \
        -v "$compose_plugin:/usr/local/lib/docker/cli-plugins/docker-compose:ro")
}

node_run() {
    docker run --rm --init --user "$uid:$gid" --workdir /workspace/frontend \
        -v "$root/frontend/src:/workspace/frontend/src:ro" \
        -v "$root/frontend/tests:/workspace/frontend/tests:ro" \
        -v "$root/frontend/test-support:/workspace/frontend/test-support:ro" \
        -v "$root/frontend/tsconfig.json:/workspace/frontend/tsconfig.json:ro" \
        -v "$root/frontend/vite.config.ts:/workspace/frontend/vite.config.ts:ro" \
        -v "$root/frontend/vite.export.config.ts:/workspace/frontend/vite.export.config.ts:ro" \
        -v "$root/frontend/export.html:/workspace/frontend/export.html:ro" \
        -v "$root/frontend/index.html:/workspace/frontend/index.html:ro" \
        -v "$root/frontend/package.json:/workspace/frontend/package.json:ro" \
        -v "$root/frontend/playwright.config.ts:/workspace/frontend/playwright.config.ts:ro" \
        -v "$root/frontend/playwright.dev.config.ts:/workspace/frontend/playwright.dev.config.ts:ro" \
        "${node_options[@]}" "$node_image" "$@"
}
node_options=()

database_tests() (
    local project="chatbi-test-db-$$-$RANDOM" work profile
    work=$(mktemp -d)
    cleanup() {
        local result=$?
        trap - EXIT
        if docker container inspect "$project" >/dev/null 2>&1; then
            [[ $(docker inspect --format '{{index .Config.Labels "com.chatbi.test"}}' "$project") == "$project" ]] || exit 1
            docker rm -f -v "$project" >/dev/null || result=1
        fi
        [[ $(docker network inspect --format '{{index .Labels "com.chatbi.test"}}' "$project") == "$project" ]] || exit 1
        docker network rm "$project" >/dev/null || result=1
        rm -rf -- "$work"
        exit "$result"
    }
    docker network create --label "com.chatbi.test=$project" "$project" >/dev/null
    trap cleanup EXIT
    for profile in ci development; do
        cat > "$work/postgres.env" <<'EOF'
POSTGRES_USER=chatbi_migrator
POSTGRES_PASSWORD=temporary-test-migrator
POSTGRES_DB=chatbi_mvp
POSTGRES_APP_USER=chatbi_app
POSTGRES_APP_PASSWORD=ci-app-password
POSTGRES_CONTROL_DB=chatbi_control
POSTGRES_CONTROL_APP_USER=chatbi_control_user
POSTGRES_CONTROL_APP_PASSWORD=temporary-test-control
POSTGRES_CONTROL_MIGRATOR_USER=chatbi_migrator
EOF
        args=()
        if [[ "$profile" == development ]]; then
            args+=(-v "$root/database/init/10_chatbi_dev_environment.sh:/docker-entrypoint-initdb.d/10_chatbi_dev_environment.sh:ro")
        fi
        docker run -d --name "$project" --network "$project" --network-alias postgres \
            --label "com.chatbi.test=$project" --env-file "$work/postgres.env" \
            -v "$root/database:/workspace/database:ro" "${args[@]}" postgres:16-alpine >/dev/null
        ready=false
        for ((i=0;i<60;i++)); do
            if docker exec "$project" pg_isready -U chatbi_migrator -d chatbi_mvp >/dev/null 2>&1; then ready=true; break; fi
            sleep 1
        done
        [[ "$ready" == true ]] || { echo '隔离PostgreSQL启动超时。' >&2; exit 1; }
        cat > "$work/test.env" <<'EOF'
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=chatbi_mvp
POSTGRES_APP_USER=chatbi_app
POSTGRES_APP_PASSWORD=ci-app-password
RUN_DATABASE_TESTS=1
EOF
        suites=(tests/online_query/test_database_integration.py tests/online_query/test_service_integration.py::ServiceDatabaseIntegrationTest)
        if [[ "$profile" == ci ]]; then
            docker exec "$project" psql -U chatbi_migrator -d chatbi_mvp -v ON_ERROR_STOP=1 -f /workspace/database/ci/bootstrap.sql >/dev/null
        else
            docker exec "$project" sh /workspace/database/init/wait_for_base_initialization.sh
            cat >> "$work/test.env" <<'EOF'
POSTGRES_CONTROL_DB=chatbi_control
POSTGRES_CONTROL_APP_USER=chatbi_control_user
POSTGRES_CONTROL_APP_PASSWORD=temporary-test-control
POSTGRES_MIGRATOR_USER=chatbi_migrator
POSTGRES_MIGRATOR_PASSWORD=temporary-test-migrator
POSTGRES_CONTROL_MIGRATOR_USER=chatbi_migrator
POSTGRES_CONTROL_BOOTSTRAP_DB=postgres
RUN_DEVELOPMENT_DATABASE_TESTS=1
EOF
            suites+=(tests/chatbi_control/test_postgres_dev_environment.py tests/chatbi_control/test_execution_postgres.py tests/chatbi_control/test_history_postgres.py tests/evaluation/common/test_database_fingerprint.py)
        fi
        python_options=(--network "$project" --env-file "$work/test.env")
        if [[ "$profile" == development ]]; then python_run -m src.bootstrap migrate; fi
        echo "数据库集成测试：$profile"
        python_run -m pytest -q -p no:cacheprovider "${suites[@]}"
        docker rm -f -v "$project" >/dev/null
    done
)

web_tests() (
    docker build --target browser -f "$root/docker/node-dev.Dockerfile" -t "$browser_image" "$root"
    local project="chatbi-test-web-$$-$RANDOM" api work
    api="$project-api"
    work=$(mktemp -d)
    mkdir -p "$work/dist" "$work/results"
    cleanup() {
        local result=$?
        trap - EXIT
        if docker inspect "$api" >/dev/null 2>&1; then
            [[ $(docker inspect --format '{{index .Config.Labels "com.chatbi.test"}}' "$api") == "$project" ]] || exit 1
            docker rm -f "$api" >/dev/null || result=1
        fi
        [[ $(docker network inspect --format '{{index .Labels "com.chatbi.test"}}' "$project") == "$project" ]] || exit 1
        docker network rm "$project" >/dev/null || result=1
        mkdir -p "$root/reports/tests"
        cp -a "$work/results" "$root/reports/tests/$project"
        rm -rf -- "$work"
        exit "$result"
    }
    docker network create --label "com.chatbi.test=$project" "$project" >/dev/null
    trap cleanup EXIT
    node_options=(-v "$work/dist:/workspace/frontend/dist" -v "$work/results:/reports")
    node_run npm run build -- --configLoader runner
    for suite in packaged dev; do
        origin=http://127.0.0.1:18001
        [[ "$suite" == dev ]] && origin=http://127.0.0.1:5173
        docker run -d --name "$api" --network "$project" --network-alias api \
            --label "com.chatbi.test=$project" --user "$uid:$gid" --workdir "$root" \
            -v "$root:$root:ro" -e CHATBI_RESULT_EXPORT_BROWSER_TEST=1 \
            -v "$work/dist:$root/frontend/dist:ro" \
            -e "CHATBI_BROWSER_TEST_ORIGIN=$origin" --entrypoint python "$python_image" \
            -m uvicorn tests.browser_support:create_browser_app --factory --host 0.0.0.0 --port 18001 >/dev/null
        ready=false
        for ((i=0;i<60;i++)); do
            if docker exec "$api" python -c 'import urllib.request; urllib.request.urlopen("http://127.0.0.1:18001/health",timeout=1)' >/dev/null 2>&1; then ready=true; break; fi
            sleep 1
        done
        [[ "$ready" == true ]] || { docker logs "$api"; exit 1; }
        node_options=(--network "container:$api" -e "CHATBI_BROWSER_TEST_EXTERNAL_API=http://127.0.0.1:18001" -e CHATBI_DEV_API_TARGET=http://127.0.0.1:18001 \
            -v "$work/results:/reports")
        node_image=$browser_image
        if [[ "$suite" == packaged ]]; then
            node_run npx playwright test --config playwright.config.ts --output /reports/packaged "$@"
        else
            node_run npx playwright test --config playwright.dev.config.ts --output /reports/dev
        fi
        docker rm -f "$api" >/dev/null
    done
)

case "$task" in
    python) compose_cli_mounts; python_run -m pytest -q -p no:cacheprovider "$@" ;;
    database) database_tests ;;
    web) web_tests "$@" ;;
    renderer)
        python_options=(--security-opt "seccomp=$root/docker/third-party/playwright-seccomp-profile.json" -e CHATBI_EXPORT_PDF_RENDER_TEST=1)
        python_run -m pytest -q -p no:cacheprovider tests/query_api/test_result_export_pdf_renderer.py "$@" ;;
    check)
        docker run --rm --user "$uid:$gid" -v "$root/pyproject.toml:/workspace/pyproject.toml:ro" \
            -v "$root/uv.lock:/workspace/uv.lock:ro" -e UV_CACHE_DIR=/tmp/chatbi-uv-cache --entrypoint uv "$python_image" lock --check
        python_run -m scripts.check_documentation
        python_run -m scripts.check_module_boundaries
        python_run -m ruff format --no-cache --check src evaluation tests
        python_run -m ruff check --no-cache --select E4,E7,E9,F src evaluation tests
        work=$(mktemp -d)
        trap 'rm -rf -- "$work"' EXIT
        mkdir -p "$work/dist" "$work/dist-export"
        node_options=(-v "$work/dist:/workspace/frontend/dist" -v "$work/dist-export:/workspace/frontend/dist-export")
        node_run npm run build -- --configLoader runner
        node_run npm run build:export -- --configLoader runner ;;
    evaluate)
        [[ -f "${CHATBI_DEV_ENV_FILE:-$root/.env}" ]] || { echo '缺少评测配置。' >&2; exit 2; }
        mkdir -p "$root/reports/evaluation"
        # 评测沿用dev内部连接和模型路径，不把宿主回环地址当作容器地址。
        "$root/dev" evaluate-tools "$@" ;;
    *) echo '用法: ./dev test [python|database|web|renderer|all]；./dev check；./dev evaluate [参数]' >&2; exit 2 ;;
esac
