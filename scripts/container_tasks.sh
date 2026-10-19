#!/usr/bin/env bash
# 宿主只调用Docker；Python、Node和测试依赖在容器内运行。
set -euo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
task=${1:-help}
shift || true
python_image=${CHATBI_DEV_PYTHON_IMAGE:-chatbi-python-dev:local}
browser_image=${CHATBI_DEV_BROWSER_IMAGE:-chatbi-browser-dev:local}
node_image=${CHATBI_DEV_NODE_IMAGE:-chatbi-node-dev:local}
host_root=${LOCAL_WORKSPACE_FOLDER:-$root}
source "$root/scripts/dev_environment.sh"
prepare_git_mounts
uid=$(id -u)
gid=$(id -g)
verification_reports="$root/reports/tests"
verification_reports_host=
verification_host_directory=
verification_run_id=
verification_active=false
verification_cleanup_status=not_applicable
verification_report_mounts=()
verification_node_mounts=()
verification_steps=()
verification_counted_steps=()
verification_extra_artifacts=()
check_work=
check_work_host=

python_run() {
    docker run --rm --init --user "$uid:$gid" --workdir "$root" \
        -v "$host_root:$root:ro" "${git_mounts[@]}" -e PYTHONDONTWRITEBYTECODE=1 \
        "${git_environment[@]}" "${verification_report_mounts[@]}" \
        "${python_options[@]}" --entrypoint python "$python_image" "$@"
}
python_options=(--network none)

verification_begin() {
    local kind=$1 scope=$2 runner=$3 runtime=$4 filtered=${5:-false}
    local -a arguments=(
        -m scripts.verification_report begin
        --repository-root "$root"
        --reports-directory /reports/tests
        --kind "$kind"
        --scope "$scope"
        --runner "$runner"
        --runtime "$runtime"
    )
    mkdir -p -- "$verification_reports"
    verification_cleanup_status=not_applicable
    verification_extra_artifacts=()
    verification_reports_host=$(host_source_path "$verification_reports")
    verification_report_mounts=(-v "$verification_reports_host:/reports/tests")
    verification_node_mounts=(-v "$verification_reports_host:/verification")
    for step in "${verification_steps[@]}"; do arguments+=(--step "$step"); done
    for step in "${verification_counted_steps[@]}"; do arguments+=(--counted-step "$step"); done
    [[ "$filtered" != true ]] || arguments+=(--filtered)
    if verification_run_id=$(python_run "${arguments[@]}"); then
        :
    else
        local result=$?
        echo '本地验证报告无法启动；本次命令未执行。' >&2
        return "$result"
    fi
    verification_host_directory="$verification_reports_host/$verification_run_id"
    verification_active=true
}

verification_step_start() {
    python_run -m scripts.verification_report step-start \
        --reports-directory /reports/tests --run-id "$verification_run_id" \
        --name "$1"
}

verification_step_finish() {
    local name=$1 exit_code=$2
    shift 2
    local -a arguments=(
        -m scripts.verification_report step-finish
        --reports-directory /reports/tests
        --run-id "$verification_run_id"
        --name "$name"
        --exit-code "$exit_code"
    )
    ((exit_code != 130 && exit_code != 143)) || arguments+=(--status interrupted)
    arguments+=("$@")
    python_run "${arguments[@]}"
}

verification_finish() {
    local exit_code=$1 cleanup_status=${2:-not_applicable} artifact
    local -a arguments=(
        -m scripts.verification_report finish
        --repository-root "$root"
        --reports-directory /reports/tests
        --run-id "$verification_run_id"
        --exit-code "$exit_code"
        --cleanup-status "$cleanup_status"
    )
    local need_node=false need_browser=false need_postgres=false image_name image_ref image_id
    for step in "${verification_steps[@]}"; do
        case "$step" in
            database-ci|database-development) need_postgres=true ;;
            browser-image-build|web-packaged|web-dev) need_browser=true ;;
            web-build|export-build) need_node=true ;;
        esac
    done
    for image_name in python node postgres browser; do
        image_ref=
        case "$image_name" in
            python) image_ref=$python_image ;;
            node)
                if [[ "$need_node" == true ]]; then image_ref=$node_image; fi
                ;;
            postgres)
                if [[ "$need_postgres" == true ]]; then image_ref=postgres:16-alpine; fi
                ;;
            browser)
                if [[ "$need_browser" == true ]]; then image_ref=$browser_image; fi
                ;;
        esac
        [[ -n "$image_ref" ]] || continue
        if image_id=$(docker image inspect --format '{{.Id}}' "$image_ref" 2>/dev/null) \
            && [[ "$image_id" =~ ^sha256:[0-9a-f]{64}$ ]]; then
            arguments+=(--container-image "$image_name=$image_id")
        fi
    done
    for artifact in "${verification_extra_artifacts[@]}"; do
        arguments+=(--artifact "$artifact")
    done
    ((exit_code != 130 && exit_code != 143)) || arguments+=(--interrupted)
    if ! python_run "${arguments[@]}"; then
        verification_active=false
        echo '本地验证结果未能写入报告；按失败处理。' >&2
        return 2
    fi
    echo "本地验证报告：reports/tests/$verification_run_id.json"
    verification_active=false
}

run_reported_step() {
    local name=$1 output_option=$2
    shift 2
    verification_step_start "$name" || return 2
    local exit_code
    if "$@"; then exit_code=0; else exit_code=$?; fi
    local -a report_args=()
    if [[ -n "$output_option" ]]; then
        report_args+=("$output_option")
    else
        report_args+=(--counts-not-applicable)
    fi
    verification_step_finish "$name" "$exit_code" "${report_args[@]}" || return 2
    return "$exit_code"
}

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
        -v "$host_root/frontend/src:/workspace/frontend/src:ro" \
        -v "$host_root/frontend/tests:/workspace/frontend/tests:ro" \
        -v "$host_root/frontend/test-support:/workspace/frontend/test-support:ro" \
        -v "$host_root/frontend/tsconfig.json:/workspace/frontend/tsconfig.json:ro" \
        -v "$host_root/frontend/vite.config.ts:/workspace/frontend/vite.config.ts:ro" \
        -v "$host_root/frontend/vite.export.config.ts:/workspace/frontend/vite.export.config.ts:ro" \
        -v "$host_root/frontend/export.html:/workspace/frontend/export.html:ro" \
        -v "$host_root/frontend/index.html:/workspace/frontend/index.html:ro" \
        -v "$host_root/frontend/package.json:/workspace/frontend/package.json:ro" \
        -v "$host_root/frontend/playwright.config.ts:/workspace/frontend/playwright.config.ts:ro" \
        -v "$host_root/frontend/playwright.dev.config.ts:/workspace/frontend/playwright.dev.config.ts:ro" \
        "${node_options[@]}" "${verification_node_mounts[@]}" "$node_image" "$@"
}
node_options=()

python_tests() {
    local filtered=false exit_code report_code own_report=false
    (($# == 0)) || filtered=true
    if [[ "$verification_active" != true ]]; then
        own_report=true
        verification_steps=(python)
        verification_counted_steps=(python)
    if verification_begin test python dev-container python "$filtered"; then :; else return $?; fi
    fi
    if compose_cli_mounts; then
        if run_reported_step python "--junit=/reports/tests/$verification_run_id/python.xml" \
            python_run -m pytest -q -p no:cacheprovider "$@" \
            "--junitxml=/reports/tests/$verification_run_id/python.xml"; then
            exit_code=0
        else
            exit_code=$?
        fi
    else
        exit_code=$?
    fi
    if [[ "$own_report" == true ]]; then
        if verification_finish "$exit_code"; then report_code=0; else report_code=$?; fi
        ((report_code == 0)) || return "$report_code"
    fi
    return "$exit_code"
}

python_tests_for_all() {
    # These suites run below with isolated PostgreSQL/Chromium; the real-LLM
    # integration case is covered by the separately required AI evaluations.
    python_tests \
        --ignore=tests/chatbi_control/test_admin_recovery_postgres.py \
        --ignore=tests/chatbi_control/test_execution_postgres.py \
        --ignore=tests/chatbi_control/test_history_postgres.py \
        --ignore=tests/chatbi_control/test_postgres_dev_environment.py \
        --ignore=tests/evaluation/common/test_database_fingerprint.py \
        --ignore=tests/online_query/test_database_integration.py \
        --ignore=tests/online_query/test_service_integration.py \
        --ignore=tests/query_api/test_result_export_pdf_renderer.py
}

renderer_tests() {
    local filtered=false exit_code report_code own_report=false
    (($# == 0)) || filtered=true
    if [[ "$verification_active" != true ]]; then
        own_report=true
        verification_steps=(renderer)
        verification_counted_steps=(renderer)
        if verification_begin test renderer dev-container python "$filtered"; then :; else return $?; fi
    fi
    python_options=(--security-opt "seccomp=$root/docker/third-party/playwright-seccomp-profile.json" -e CHATBI_EXPORT_PDF_RENDER_TEST=1)
    if run_reported_step renderer "--junit=/reports/tests/$verification_run_id/renderer.xml" \
        python_run -m pytest -q -p no:cacheprovider \
        tests/query_api/test_result_export_pdf_renderer.py "$@" \
        "--junitxml=/reports/tests/$verification_run_id/renderer.xml"; then
        exit_code=0
    else
        exit_code=$?
    fi
    if [[ "$own_report" == true ]]; then
        if verification_finish "$exit_code"; then report_code=0; else report_code=$?; fi
        ((report_code == 0)) || return "$report_code"
    fi
    return "$exit_code"
}

database_tests() (
    local project="chatbi-test-db-$$-$RANDOM" work profile network_created=false
    work=$(create_temporary_directory) || exit 1
    work_host=$(host_source_path "$work")
    cleanup() {
        local result=$?
        local cleanup_result=0 label
        trap - EXIT
        docker info >/dev/null 2>&1 || cleanup_result=1
        if docker container inspect "$project" >/dev/null 2>&1; then
            label=$(docker inspect --format '{{index .Config.Labels "com.chatbi.test"}}' "$project" 2>/dev/null || true)
            if [[ "$label" == "$project" ]]; then
                docker rm -f -v "$project" >/dev/null || cleanup_result=1
            else
                cleanup_result=1
            fi
        fi
        if [[ "$network_created" == true ]]; then
            label=$(docker network inspect --format '{{index .Labels "com.chatbi.test"}}' "$project" 2>/dev/null || true)
            if [[ "$label" == "$project" ]]; then
                docker network rm "$project" >/dev/null || cleanup_result=1
            else
                cleanup_result=1
            fi
        fi
        rm -rf -- "$work" || cleanup_result=1
        if ((cleanup_result == 0)); then
            : > "$verification_host_directory/database-cleanup-passed"
        else
            : > "$verification_host_directory/database-cleanup-failed"
            result=1
        fi
        exit "$result"
    }
    trap cleanup EXIT
    if docker network create --label "com.chatbi.test=$project" "$project" >/dev/null; then
        network_created=true
    else
        exit $?
    fi
    for profile in ci development; do
        cat > "$work/postgres.env" <<'EOF' || exit 1
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
            args+=(-v "$host_root/database/init/10_chatbi_dev_environment.sh:/docker-entrypoint-initdb.d/10_chatbi_dev_environment.sh:ro")
        fi
        if docker run -d --name "$project" --network "$project" --network-alias postgres \
            --label "com.chatbi.test=$project" --env-file "$work/postgres.env" \
            -v "$host_root/database:/workspace/database:ro" "${args[@]}" postgres:16-alpine >/dev/null; then
            :
        else
            exit $?
        fi
        ready=false
        for ((i=0;i<60;i++)); do
            # 官方 Postgres 镜像初始化时会短暂启动仅 Unix socket 可连的临时实例；
            # 通过 TCP 探测，避免把该实例误判为 CI / development 服务已就绪。
            if docker exec "$project" pg_isready -h 127.0.0.1 -U chatbi_migrator -d chatbi_mvp >/dev/null 2>&1; then ready=true; break; fi
            sleep 1
        done
        [[ "$ready" == true ]] || { echo '隔离PostgreSQL启动超时。' >&2; exit 1; }
        cat > "$work/test.env" <<'EOF' || exit 1
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=chatbi_mvp
POSTGRES_APP_USER=chatbi_app
POSTGRES_APP_PASSWORD=ci-app-password
RUN_DATABASE_TESTS=1
EOF
        suites=(tests/online_query/test_database_integration.py tests/online_query/test_service_integration.py::ServiceDatabaseIntegrationTest)
        if [[ "$profile" == ci ]]; then
            if docker exec "$project" psql -U chatbi_migrator -d chatbi_mvp -v ON_ERROR_STOP=1 -f /workspace/database/ci/bootstrap.sql >/dev/null; then :; else exit $?; fi
        else
            if docker exec "$project" sh /workspace/database/init/wait_for_base_initialization.sh; then :; else exit $?; fi
            cat >> "$work/test.env" <<'EOF' || exit 1
POSTGRES_CONTROL_DB=chatbi_control
POSTGRES_CONTROL_APP_USER=chatbi_control_user
POSTGRES_CONTROL_APP_PASSWORD=temporary-test-control
POSTGRES_MIGRATOR_USER=chatbi_migrator
POSTGRES_MIGRATOR_PASSWORD=temporary-test-migrator
POSTGRES_CONTROL_MIGRATOR_USER=chatbi_migrator
POSTGRES_CONTROL_BOOTSTRAP_DB=postgres
RUN_DEVELOPMENT_DATABASE_TESTS=1
EOF
            suites+=(tests/chatbi_control/test_postgres_dev_environment.py tests/chatbi_control/test_admin_recovery_postgres.py tests/chatbi_control/test_execution_postgres.py tests/chatbi_control/test_history_postgres.py tests/evaluation/common/test_database_fingerprint.py)
        fi
        python_options=(--network "$project" --env-file "$work/test.env")
        if [[ "$profile" == development ]]; then
            if python_run -m src.bootstrap migrate; then :; else exit $?; fi
        fi
        echo "数据库集成测试：$profile"
        step_name=database-ci
        [[ "$profile" != development ]] || step_name=database-development
        junit_path="/reports/tests/$verification_run_id/$step_name.xml"
        if run_reported_step "$step_name" "--junit=$junit_path" \
            python_run -m pytest -q -p no:cacheprovider "${suites[@]}" \
            "--junitxml=$junit_path"; then
            :
        else
            exit $?
        fi
        docker rm -f -v "$project" >/dev/null
    done
)

database_task() {
    local own_report=false exit_code report_code cleanup_status=failed
    if [[ "$verification_active" != true ]]; then
        own_report=true
        verification_steps=(database-ci database-development)
        verification_counted_steps=(database-ci database-development)
        if verification_begin test database dev-container python false; then :; else return $?; fi
    fi
    if database_tests; then exit_code=0; else exit_code=$?; fi
    if [[ -f "$verification_host_directory/database-cleanup-passed" ]]; then
        cleanup_status=passed
    elif [[ -f "$verification_host_directory/database-cleanup-failed" ]]; then
        cleanup_status=failed
    fi
    verification_cleanup_status=$cleanup_status
    if [[ "$own_report" == true ]]; then
        if verification_finish "$exit_code" "$cleanup_status"; then report_code=0; else report_code=$?; fi
        ((report_code == 0)) || return "$report_code"
    fi
    return "$exit_code"
}

web_tests() (
    # clean clone也需已有子挂载点；不覆盖或删除原有网页产物。
    mkdir -p -- "$root/frontend/dist" || exit 1
    local project="chatbi-test-web-$$-$RANDOM" api work
    local network_created=false
    api="$project-api"
    work=$(create_temporary_directory) || exit 1
    work_host=$(host_source_path "$work")
    mkdir -p "$work/dist" "$work/results" || exit 1
    cleanup() {
        local result=$?
        local cleanup_result=0 label support_artifacts
        trap - EXIT
        docker info >/dev/null 2>&1 || cleanup_result=1
        if docker inspect "$api" >/dev/null 2>&1; then
            label=$(docker inspect --format '{{index .Config.Labels "com.chatbi.test"}}' "$api" 2>/dev/null || true)
            if [[ "$label" == "$project" ]]; then
                docker rm -f "$api" >/dev/null || cleanup_result=1
            else
                cleanup_result=1
            fi
        fi
        if [[ "$network_created" == true ]]; then
            label=$(docker network inspect --format '{{index .Labels "com.chatbi.test"}}' "$project" 2>/dev/null || true)
            if [[ "$label" == "$project" ]]; then
                docker network rm "$project" >/dev/null || cleanup_result=1
            else
                cleanup_result=1
            fi
        fi
        support_artifacts="$verification_host_directory/support-results"
        if [[ ! -e "$support_artifacts" ]]; then
            mkdir -- "$support_artifacts" || cleanup_result=1
        else
            cleanup_result=1
        fi
        if [[ -d "$support_artifacts" ]]; then
            cp -a "$work/results/." "$support_artifacts/" || cleanup_result=1
        fi
        rm -rf -- "$work" || cleanup_result=1
        if ((cleanup_result == 0)); then
            : > "$verification_host_directory/web-cleanup-passed"
        else
            : > "$verification_host_directory/web-cleanup-failed"
            result=1
        fi
        exit "$result"
    }
    node_options=(-v "$work_host/dist:/workspace/frontend/dist" -v "$work_host/results:/reports")
    trap cleanup EXIT
    if run_reported_step browser-image-build --counts-not-applicable \
        docker build --target browser -f "$root/docker/node-dev.Dockerfile" \
        -t "$browser_image" "$root"; then
        :
    else
        exit $?
    fi
    if docker network create --label "com.chatbi.test=$project" "$project" >/dev/null; then
        network_created=true
    else
        exit $?
    fi
    if run_reported_step web-build --counts-not-applicable \
        node_run npm run build -- --configLoader runner; then
        :
    else
        exit $?
    fi
    for suite in packaged dev; do
        origin=http://127.0.0.1:18001
        [[ "$suite" == dev ]] && origin=http://127.0.0.1:5173
        if docker run -d --name "$api" --network "$project" --network-alias api \
            --label "com.chatbi.test=$project" --user "$uid:$gid" --workdir "$root" \
            -v "$host_root:$root:ro" "${git_mounts[@]}" -e CHATBI_RESULT_EXPORT_BROWSER_TEST=1 \
            -v "$work_host/dist:$root/frontend/dist:ro" \
            -e "CHATBI_BROWSER_TEST_ORIGIN=$origin" --entrypoint python "$python_image" \
            -m uvicorn tests.browser_support:create_browser_app --factory --host 0.0.0.0 --port 18001 >/dev/null; then
            :
        else
            exit $?
        fi
        ready=false
        for ((i=0;i<60;i++)); do
            if docker exec "$api" python -c 'import urllib.request; urllib.request.urlopen("http://127.0.0.1:18001/health",timeout=1)' >/dev/null 2>&1; then ready=true; break; fi
            sleep 1
        done
        [[ "$ready" == true ]] || { docker logs "$api"; exit 1; }
        node_options=(--network "container:$api" -e "CHATBI_BROWSER_TEST_EXTERNAL_API=http://127.0.0.1:18001" -e CHATBI_DEV_API_TARGET=http://127.0.0.1:18001 \
            -v "$work_host/results:/reports")
        node_image=$browser_image
        step_name="web-$suite"
        playwright_output="$verification_host_directory/$step_name.json"
        playwright_results="/verification/$verification_run_id/artifacts/$suite"
        if [[ "$suite" == packaged ]]; then
            if run_reported_step "$step_name" "--playwright=/reports/tests/$verification_run_id/$step_name.json" \
                node_run npx playwright test --config playwright.config.ts \
                --output "$playwright_results" "$@" --reporter=json > "$playwright_output"; then
                :
            else
                exit $?
            fi
        else
            if run_reported_step "$step_name" "--playwright=/reports/tests/$verification_run_id/$step_name.json" \
                node_run npx playwright test --config playwright.dev.config.ts \
                --output "$playwright_results" --reporter=json > "$playwright_output"; then
                :
            else
                exit $?
            fi
        fi
        if docker rm -f "$api" >/dev/null; then :; else exit $?; fi
    done
)

web_task() {
    local own_report=false exit_code report_code cleanup_status=failed filtered=false
    (($# == 0)) || filtered=true
    if [[ "$verification_active" != true ]]; then
        own_report=true
        verification_steps=(browser-image-build web-build web-packaged web-dev)
        verification_counted_steps=(web-packaged web-dev)
        if verification_begin test web dev-container node "$filtered"; then :; else return $?; fi
    fi
    if web_tests "$@"; then exit_code=0; else exit_code=$?; fi
    if [[ -f "$verification_host_directory/web-cleanup-passed" ]]; then
        cleanup_status=passed
    elif [[ -f "$verification_host_directory/web-cleanup-failed" ]]; then
        cleanup_status=failed
    fi
    verification_cleanup_status=$cleanup_status
    verification_extra_artifacts=("$verification_run_id/support-results")
    if [[ "$own_report" == true ]]; then
        if verification_finish "$exit_code" "$cleanup_status"; then report_code=0; else report_code=$?; fi
        ((report_code == 0)) || return "$report_code"
    fi
    return "$exit_code"
}

test_all() {
    local exit_code=0 report_code
    verification_steps=(
        python
        database-ci
        database-development
        browser-image-build
        web-build
        web-packaged
        web-dev
        renderer
    )
    verification_counted_steps=(
        python database-ci database-development web-packaged web-dev renderer
    )
    if verification_begin test all dev-container python false; then :; else return $?; fi
    for suite in python database web renderer; do
        case "$suite" in
            python) task_runner=python_tests_for_all ;;
            database) task_runner=database_task ;;
            web) task_runner=web_task ;;
            renderer) task_runner=renderer_tests ;;
        esac
        if "$task_runner"; then
            :
        else
            exit_code=$?
            break
        fi
    done
    if verification_finish "$exit_code" "$verification_cleanup_status"; then
        report_code=0
    else
        report_code=$?
    fi
    ((report_code == 0)) || return "$report_code"
    return "$exit_code"
}

check_lock() {
    docker run --rm --user "$uid:$gid" \
        -v "$host_root/pyproject.toml:/workspace/pyproject.toml:ro" \
        -v "$host_root/uv.lock:/workspace/uv.lock:ro" \
        -e UV_CACHE_DIR=/tmp/chatbi-uv-cache --entrypoint uv "$python_image" lock --check
}

check_docs() { python_run -m scripts.check_documentation; }
check_boundaries() { python_run -m scripts.check_module_boundaries; }
check_python_quality() {
    python_options=(--network bridge)
    python_run -m scripts.python_quality
}

check_web_build() {
    if [[ -z "$check_work" ]]; then
        check_work=$(create_temporary_directory)
        check_work_host=$(host_source_path "$check_work")
        mkdir -p "$check_work/dist" "$check_work/dist-export"
    fi
    node_options=(
        -v "$check_work_host/dist:/workspace/frontend/dist"
        -v "$check_work_host/dist-export:/workspace/frontend/dist-export"
    )
    node_run npm run build -- --configLoader runner
}

check_export_build() {
    node_run npm run build:export -- --configLoader runner
}

check_task() {
    local scope=${1:-all} exit_code=0 report_code cleanup_status=not_applicable
    case "$scope" in
        all)
            verification_steps=(lock docs boundaries python web-build export-build)
            ;;
        docs|boundaries|python)
            verification_steps=("$scope")
            ;;
        *)
            echo '用法: ./dev check [docs|python|boundaries]' >&2
            return 2
            ;;
    esac
    verification_counted_steps=()
    if verification_begin check "$scope" dev-container python false; then :; else return $?; fi
    if [[ "$scope" == all ]]; then
        for step in lock docs boundaries python web-build export-build; do
            case "$step" in
                lock) runner=check_lock ;;
                docs) runner=check_docs ;;
                boundaries) runner=check_boundaries ;;
                python) runner=check_python_quality ;;
                web-build) runner=check_web_build ;;
                export-build) runner=check_export_build ;;
            esac
            if run_reported_step "$step" "" "$runner"; then
                :
            else
                exit_code=$?
                break
            fi
        done
    else
        case "$scope" in
            docs) runner=check_docs ;;
            boundaries) runner=check_boundaries ;;
            python) runner=check_python_quality ;;
        esac
        if run_reported_step "$scope" "" "$runner"; then
            :
        else
            exit_code=$?
        fi
    fi
    if [[ -n "$check_work" ]]; then
        if rm -rf -- "$check_work"; then
            cleanup_status=passed
        else
            cleanup_status=failed
            ((exit_code != 0)) || exit_code=1
        fi
        check_work=
        check_work_host=
    fi
    if verification_finish "$exit_code" "$cleanup_status"; then report_code=0; else report_code=$?; fi
    ((report_code == 0)) || return "$report_code"
    return "$exit_code"
}

# 只读文件参数可位于仓库外；不隐式创建报告或目标worktree。
mount_readonly_arguments() {
    local previous= arg path directory host_path common
    for arg in "$@"; do
        if [[ -n "$previous" ]]; then
            path=$arg
            previous=
        else
            case "$arg" in
                --repo|--report|--report-dir|--cases) previous=$arg; continue ;;
                --repo=*|--report=*|--report-dir=*|--cases=*) path=${arg#*=} ;;
                *) continue ;;
            esac
        fi
        [[ -e "$path" ]] || continue
        if [[ -d "$path" ]]; then directory=$(cd -- "$path" && pwd); else directory=$(cd -- "$(dirname -- "$path")" && pwd); fi
        [[ "$directory" == "$root" || "$directory" == "$root/"* ]] && continue
        host_path=$directory
        python_options+=(-v "$host_path:$directory:ro")
        if common=$(git -C "$directory" rev-parse --path-format=absolute --git-common-dir 2>/dev/null); then
            [[ "$common" == "$directory/"* ]] || python_options+=(-v "$common:$common:ro")
        fi
    done
}
case "$task" in
    python) python_tests "$@" ;;
    database) database_task "$@" ;;
    web) web_task "$@" ;;
    renderer) renderer_tests "$@" ;;
    harness-control) exec bash "$root/scripts/harness_container_adapter.sh" "$@" ;;
    all)
        (($# == 0)) || { echo '用法: ./dev test all' >&2; exit 2; }
        test_all ;;
    check)
        scope=${1:-all}
        if (($#)); then shift; fi
        (($# == 0)) || { echo '用法: ./dev check [docs|python|boundaries]' >&2; exit 2; }
        check_task "$scope" ;;
    harness) mount_readonly_arguments "$@"; python_run -m scripts.check_harness_state "$@" ;;
    evaluate-validate) mount_readonly_arguments "$@"; python_run -m evaluation.common.real_e2e_acceptance "$@" ;;
    evaluate)
        [[ -f "${CHATBI_DEV_ENV_FILE:-$root/.env}" ]] || { echo '缺少评测配置。' >&2; exit 2; }
        mkdir -p "$root/reports/evaluation"
        # 评测沿用dev内部连接和模型路径，不把宿主回环地址当作容器地址。
        "$root/dev" evaluate-tools "$@" ;;
    *) echo '用法: ./dev test [python|database|web|renderer|all]；./dev check；./dev evaluate [参数]' >&2; exit 2 ;;
esac
