# All host mutations remain under local's shared operation lock.
initialize_runtime_binding_defaults() {
    CHATBI_BOUND_POSTGRES_VOLUME=chatbi_stable_postgres_data
    CHATBI_BOUND_QDRANT_VOLUME=chatbi_stable_qdrant_data
    CHATBI_BOUND_RAG_DIR="$ROOT/.local/rag"
    CHATBI_BOUND_OPERATIONS_API_DIR="$ROOT/.local/operations/api"
    CHATBI_BOUND_OPERATIONS_API_RELATIVE=api
    CHATBI_BOUND_ENVIRONMENT_ID=legacy
    CHATBI_BOUND_DATABASE_IMAGE=''
    CHATBI_BOUND_DATABASE_IMAGE_ID=''
    export CHATBI_BOUND_POSTGRES_VOLUME CHATBI_BOUND_QDRANT_VOLUME CHATBI_BOUND_RAG_DIR \
        CHATBI_BOUND_OPERATIONS_API_DIR CHATBI_BOUND_OPERATIONS_API_RELATIVE \
        CHATBI_BOUND_DATABASE_IMAGE CHATBI_BOUND_DATABASE_IMAGE_ID
}

resolve_runtime_binding() {
    initialize_runtime_binding_defaults
    local binding="$ROOT/.local/runtime-binding.json" parsed key value
    if [[ -e "$binding" || -L "$binding" ]]; then
        require_operations_image
        [[ -f "$binding" && ! -L "$binding" ]] || fail '资源绑定文件类型未确认。'
        parsed="$(docker run --rm --user "$CHATBI_LOCAL_UID:$CHATBI_LOCAL_GID" \
            --mount "type=bind,source=$ROOT/.local/operations,target=/state/operations,readonly" \
            --mount "type=bind,source=$binding,target=/binding.json,readonly" \
            --entrypoint python3 "$CHATBI_OPERATIONS_IMAGE" -m scripts.local_runtime_binding resolve)" \
            || fail '活动资源绑定未确认；拒绝使用默认资源掩盖错误。'
        apply_binding_environment "$parsed"
    fi
    export CHATBI_BOUND_POSTGRES_VOLUME CHATBI_BOUND_QDRANT_VOLUME CHATBI_BOUND_RAG_DIR \
        CHATBI_BOUND_OPERATIONS_API_DIR CHATBI_BOUND_OPERATIONS_API_RELATIVE \
        CHATBI_BOUND_DATABASE_IMAGE CHATBI_BOUND_DATABASE_IMAGE_ID
}

apply_binding_environment() {
    local parsed="$1" key value
    while IFS='=' read -r key value; do
        case "$key" in
            CHATBI_BOUND_POSTGRES_VOLUME|CHATBI_BOUND_QDRANT_VOLUME|CHATBI_BOUND_ENVIRONMENT_ID|CHATBI_BOUND_DATABASE_IMAGE|CHATBI_BOUND_DATABASE_IMAGE_ID|CHATBI_BOUND_OPERATIONS_API_RELATIVE)
                printf -v "$key" '%s' "$value" ;;
            CHATBI_BOUND_RAG_DIR) CHATBI_BOUND_RAG_DIR="$ROOT/$value" ;;
            CHATBI_BOUND_OPERATIONS_API_DIR) CHATBI_BOUND_OPERATIONS_API_DIR="$ROOT/$value" ;;
            CHATBI_BOUND_CONFIG_FILE) CONFIG_FILE="$ROOT/$value" ;;
            CHATBI_BOUND_SECRET_FILE) SECRET_FILE="$ROOT/$value" ;;
            CHATBI_BOUND_RELEASE_FILE) RELEASE_FILE="$ROOT/$value" ;;
            *) fail '资源绑定输出包含未知字段。' ;;
        esac
    done <<< "$parsed"
}

verify_bound_volume() {
    local kind="$1" name logical metadata project_label volume_label
    if [[ "$kind" == postgres ]]; then name="$CHATBI_BOUND_POSTGRES_VOLUME"; else name="$CHATBI_BOUND_QDRANT_VOLUME"; fi
    logical="${kind}_data"
    metadata="$(docker volume inspect --format '{{json .}}' "$name" 2>/dev/null)" || return 1
    if [[ "$CHATBI_BOUND_ENVIRONMENT_ID" == legacy ]]; then
        project_label="$(docker volume inspect --format '{{index .Labels "com.docker.compose.project"}}' "$name")"
        volume_label="$(docker volume inspect --format '{{index .Labels "com.docker.compose.volume"}}' "$name")"
        [[ "$project_label" == "$PROJECT_NAME" && "$volume_label" == "$logical" ]] \
            || fail '同名卷不属于当前稳定环境；拒绝复用。'
    else
        printf '%s' "$metadata" | docker run --rm -i --user "$CHATBI_LOCAL_UID:$CHATBI_LOCAL_GID" \
            --mount "type=bind,source=$ROOT/.local/operations,target=/state/operations,readonly" \
            --mount "type=bind,source=$ROOT/.local/runtime-binding.json,target=/binding.json,readonly" \
            --entrypoint python3 "$CHATBI_OPERATIONS_IMAGE" -m scripts.local_runtime_binding volume --kind "$kind" \
            || fail '恢复卷归属未确认；拒绝复用。'
    fi
}

ensure_bound_volumes() {
    local kind name
    for kind in postgres qdrant; do
        if [[ "$kind" == postgres ]]; then name="$CHATBI_BOUND_POSTGRES_VOLUME"; else name="$CHATBI_BOUND_QDRANT_VOLUME"; fi
        if docker volume inspect "$name" >/dev/null 2>&1; then
            verify_bound_volume "$kind" || fail '活动卷无法核验。'
        elif [[ "$CHATBI_BOUND_ENVIRONMENT_ID" == legacy ]]; then
            docker volume create --label "com.docker.compose.project=$PROJECT_NAME" \
                --label "com.docker.compose.volume=${kind}_data" --label com.chatbi.product=chatbi-engine \
                "$name" >/dev/null
            verify_bound_volume "$kind" || fail '新建卷无法核验。'
        else
            fail '已登记的恢复卷不存在；不会新建空卷替代已恢复数据。'
        fi
    done
    verify_bound_single_writer
}

verify_bound_existing_resources() {
    local kind name
    for kind in postgres qdrant; do
        if [[ "$kind" == postgres ]]; then name="$CHATBI_BOUND_POSTGRES_VOLUME"; else name="$CHATBI_BOUND_QDRANT_VOLUME"; fi
        if docker volume inspect "$name" >/dev/null 2>&1; then
            verify_bound_volume "$kind" || fail '活动卷无法核验。'
        fi
    done
    verify_bound_single_writer
}

verify_bound_single_writer() {
    local container project service containers count=0
    containers="$(docker ps --quiet --filter "volume=$CHATBI_BOUND_POSTGRES_VOLUME")" \
        || fail '无法核对PG卷的运行占用；拒绝继续。'
    while IFS= read -r container; do
        [[ -n "$container" ]] || continue
        count=$((count + 1))
        (( count <= 1 )) || fail '同一PG卷存在多个运行容器；拒绝继续。'
        project="$(docker inspect --format '{{index .Config.Labels "com.docker.compose.project"}}' "$container")"
        service="$(docker inspect --format '{{index .Config.Labels "com.docker.compose.service"}}' "$container")"
        [[ "$project" == "$PROJECT_NAME" && "$service" == postgres ]] \
            || fail '活动PG卷被其他运行容器占用；拒绝启动另一个writer。'
    done <<< "$containers"
}

verify_bound_database_image() {
    [[ -z "$CHATBI_BOUND_DATABASE_IMAGE" && -z "$CHATBI_BOUND_DATABASE_IMAGE_ID" ]] && return 0
    [[ "$CHATBI_BOUND_DATABASE_IMAGE" =~ ^chatbi-local-postgres:[A-Za-z0-9_.-]+$ \
        && "$CHATBI_BOUND_DATABASE_IMAGE_ID" =~ ^sha256:[0-9a-f]{64}$ ]] \
        || fail '活动数据库镜像绑定无效。'
    local actual
    actual="$(docker image inspect --format '{{.Id}}' "$CHATBI_BOUND_DATABASE_IMAGE" 2>/dev/null)" \
        || fail '活动数据库镜像不存在；拒绝以 release 文件中的其他镜像替代。'
    [[ "$actual" == "$CHATBI_BOUND_DATABASE_IMAGE_ID" ]] \
        || fail '活动数据库镜像 ID 与资源绑定不一致。'
}
