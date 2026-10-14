#!/usr/bin/env bash
# 宿主Docker编排；JSON校验和业务规则在容器内，业务进程不取得socket。
set -euo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
operation=$1; target=$2; shift 2
source "$root/scripts/dev_environment.sh"
initialize_environment "$target" || exit 1
work=$(mktemp -d /tmp/chatbi-maintenance.XXXXXX)
chmod 700 "$work"
cleanup() {
    local result=$?
    trap - EXIT
    if [[ -n ${doctor_name:-} ]] && docker container inspect "$doctor_name" >/dev/null 2>&1; then
        if [[ $(docker inspect --format '{{index .Config.Labels "com.docker.compose.project"}}/{{index .Config.Labels "com.docker.compose.service"}}' "$doctor_name") == "$project/maintenance" ]]; then
            docker rm -f "$doctor_name" >/dev/null || result=1
        else
            echo '诊断容器归属不符，未清理未知资源。' >&2
            result=1
        fi
    fi
    rm -rf -- "$work"
    exit "$result"
}
trap cleanup EXIT
trap 'echo "维护失败；未确认完成，不会扩大操作范围或自动重试。" >&2' ERR
json_tool() {
    docker run --rm -i --network none --user "$(id -u):$(id -g)" \
        -v "$host_root:/workspace:ro" -w /workspace --entrypoint python \
        --pull never "$python_image" -m scripts.dev_compose "$@"
}
# 未插值结构可能仍含用户override中的字面Secret，只保存在0700临时目录。
"${compose[@]}" --profile tools config --no-interpolate --format json > "$work/config.json" 2>/dev/null
chmod 600 "$work/config.json"
# 使用目标tools镜像解析配置，标准应用不额外要求开发镜像。
raw_image=$("${compose[@]}" --profile tools config --no-interpolate --format yaml 2>/dev/null | awk '
    /^  tools:$/ { selected=1; next }
    selected && /^  [^ ]+:$/ { selected=0 }
    selected && /^    image:/ { sub(/^    image: /, ""); print; selected=0 }
')
[[ -n "$raw_image" ]] || { echo '无法核实工具镜像。' >&2; exit 1; }
printf 'services:\n  helper:\n    image: %s\n' "$raw_image" > "$work/image.yml"
python_image=$(docker compose --project-directory "$root" --env-file "$env_file" -f "$work/image.yml" config --images 2>/dev/null)
[[ -n "$python_image" && "$python_image" != *$'\n'* ]] && docker image inspect "$python_image" >/dev/null 2>&1 || { echo '缺少目标工具镜像，请先显式build。' >&2; exit 1; }
project=$(json_tool project < "$work/config.json")
volume_identity() { json_tool volume --key "$1" < "$work/config.json"; }
verify_volume() {
    docker volume inspect "$volume" 2>/dev/null | json_tool validate-volume --project "$project" --volume "$volume" --key "$key"
}
select_postgres() {
    read -r project volume < <(volume_identity postgres_data) || return 1
    key=postgres_data
    verify_volume || return 1
    pg=$(docker ps -q --filter "label=com.docker.compose.project=$project" --filter label=com.docker.compose.service=postgres --filter status=running)
    [[ -n "$pg" && "$pg" != *$'\n'* ]] || { echo '目标Control DB没有唯一运行容器。' >&2; return 1; }
    docker inspect "$pg" | json_tool validate-container --project "$project" --service postgres --volume "$volume" --target "$target" || return 1
}
prepare_service() {
    select_postgres || return 1
    json_tool template --operation "$operation" --container "$pg" --target "$target" --local-root "$root" --host-root "$host_root" < "$work/config.json" > "$work/service.json" || return 1
    chmod 600 "$work/service.json"
    maintenance=(docker compose --project-directory "$root" --env-file "$env_file" -f "$work/service.json")
    "${maintenance[@]}" config --format json > "$work/expanded.json" 2>/dev/null || return 1
    chmod 600 "$work/expanded.json"
    json_tool map-paths --local-root "$root" --host-root "$host_root" < "$work/expanded.json" > "$work/runtime.json" || return 1
    chmod 600 "$work/runtime.json"
    maintenance=(docker compose --project-directory "$root" --env-file "$env_file" -f "$work/runtime.json")
    image=$("${maintenance[@]}" config --images 2>/dev/null)
    [[ -n "$image" && "$image" != *$'\n'* ]] && docker image inspect "$image" >/dev/null 2>&1 || { echo '缺少匹配的工具镜像，请先显式build。' >&2; return 1; }
}
case "$operation" in
    recover)
        username=$1
        prepare_service
        if ! "${maintenance[@]}" run --rm --no-deps --pull never -T maintenance -c \
            'from src.bootstrap.admin_recovery import recover_admin; from src.authorization.auth_service import AuthService; assert callable(AuthService.recover_admin); from src.bootstrap.commands import main; main(["recover-admin", "--help"])' >/dev/null 2>&1; then
            echo '工具镜像缺少匹配恢复代码，请先显式build；未修改账号。' >&2
            exit 1
        fi
        echo "目标环境：$target；Compose项目：$project"
        if "${maintenance[@]}" run --rm --no-deps --pull never maintenance -m src.bootstrap recover-admin \
            --username "$username" --environment "$target" --project "$project"; then
            exit 0
        else
            result=$?
            if [[ "$result" == 2 || "$result" == 130 ]]; then exit "$result"; fi
            echo '恢复资源或事务失败；未确认成功，不会自动重试。' >&2
            exit 1
        fi ;;
    doctor)
        echo "诊断目标：$target；Compose项目：$project（只读，无LLM请求）"
        "${compose[@]}" --profile tools config --services --no-interpolate >/dev/null 2>&1
        if ! prepare_service; then echo '依赖：not_ready；无法装配诊断，不会启动服务。' >&2; exit 1; fi
        if [[ "$target" == app ]]; then
            for asset_key in model_data rag_data; do
                read -r asset_project asset_volume < <(volume_identity "$asset_key")
                docker volume inspect "$asset_volume" 2>/dev/null | json_tool validate-volume --project "$project" --volume "$asset_volume" --key "$asset_key" || { echo '必要资产卷缺失或归属不符；不会新建。' >&2; exit 1; }
            done
        fi
        doctor_name="$project-doctor-$$-$RANDOM"
        timeout --kill-after=5s 40s "${maintenance[@]}" run --rm --name "$doctor_name" --no-deps --pull never -T maintenance -m src.bootstrap.doctor 2> "$work/diagnostic-error" ;;
    metadata)
        output=$1
        prepare_service
        mkdir -p -- "$output"
        output=$(cd -- "$output" && pwd)
        output_host=$output
        if [[ "$output" == "$root/"* ]]; then output_host="$host_root/${output#"$root/"}"; fi
        "${maintenance[@]}" run --rm --no-deps --pull never -T --user "$(id -u):$(id -g)" \
            -v "$output_host:/metadata-output" maintenance -m scripts.metadata.export_schema \
            --runtime-environment --output-dir /metadata-output ;;
    reset)
        service=$1; confirmed=${2:-}
        key="${service}_data"
        read -r project volume < <(volume_identity "$key")
        if ! docker volume inspect "$volume" > "$work/volume.json" 2> "$work/volume-error"; then
            error=$(<"$work/volume-error")
            if [[ "$error" == *"no such volume"* || "$error" == *"No such volume"* ]]; then
                echo '目标开发卷不存在；没有需要重置的数据。'
                exit 0
            fi
            echo '无法核实目标开发卷，拒绝重置。' >&2
            exit 1
        fi
        verify_volume
        for current in api web "$service"; do
            for existing in $(docker ps -aq --filter "label=com.docker.compose.project=$project" --filter "label=com.docker.compose.service=$current"); do
                docker inspect "$existing" | json_tool validate-container --project "$project" --service "$current" --target dev
            done
        done
        original_created=$(docker volume inspect --format '{{.CreatedAt}}' "$volume")
        echo "开发重置目标：$project；卷：$volume"
        if [[ "$service" == postgres ]]; then
            phrase='DELETE POSTGRES DATA'
            echo '将删除Sales Mart、Control DB账号/Session/历史/成果；不自动创建管理员。'
        else
            phrase='DELETE QDRANT DATA'
            echo '将删除Qdrant集合和索引；之后需要显式build-rag。'
        fi
        if [[ "$confirmed" != --confirm ]]; then
            read -r -p "输入 $phrase 确认删除: " answer || answer=
            [[ "$answer" == "$phrase" ]] || { echo '已取消；没有删除数据。'; exit 0; }
        fi
        "${compose[@]}" stop api web "$service"
        for current in api web "$service"; do
            ids=$(docker ps -q --filter "label=com.docker.compose.project=$project" --filter "label=com.docker.compose.service=$current" --filter status=running)
            [[ -z "$ids" ]] || { echo '相关服务仍在运行，拒绝删除。' >&2; exit 1; }
        done
        "${compose[@]}" rm --force "$service"
        verify_volume
        [[ $(docker volume inspect --format '{{.CreatedAt}}' "$volume") == "$original_created" ]] || { echo '卷身份在确认后变化，拒绝删除。' >&2; exit 1; }
        users=$(docker ps -aq --filter "volume=$volume")
        [[ -z "$users" ]] || { echo '目标卷仍被容器使用，拒绝删除。' >&2; exit 1; }
        docker volume rm "$volume"
        if [[ "$service" == postgres ]]; then
            "$root/dev" migrate
        else
            "${compose[@]}" up --no-build -d qdrant
        fi
        echo '重置完成；API/Web保持停止。请按初始化步骤显式up。' ;;
    *) exit 2 ;;
esac
