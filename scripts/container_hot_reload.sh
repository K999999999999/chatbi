#!/usr/bin/env bash
# Restricted writable copies used only by isolated container acceptance.

container_hot_reload_init() {
    local repository_root=$1 work_directory=$2 compose_project=$3 compose_override=$4 candidate
    HOT_RELOAD_ROOT="$work_directory/hot-reload"
    HOT_RELOAD_BACKEND="$HOT_RELOAD_ROOT/writable/backend/query_api/app.py"
    HOT_RELOAD_STYLE="$HOT_RELOAD_ROOT/writable/frontend/src/style.css"
    HOT_RELOAD_BACKEND_BACKUP="$HOT_RELOAD_ROOT/original/app.py"
    HOT_RELOAD_STYLE_BACKUP="$HOT_RELOAD_ROOT/original/style.css"

    mkdir -m 700 -p "$HOT_RELOAD_ROOT/original" \
        "$HOT_RELOAD_ROOT/writable/backend/query_api" \
        "$HOT_RELOAD_ROOT/writable/frontend/src" || return $?
    cp -- "$repository_root/src/query_api/app.py" "$HOT_RELOAD_BACKEND_BACKUP" || return $?
    cp -- "$repository_root/frontend/src/style.css" "$HOT_RELOAD_STYLE_BACKUP" || return $?
    cp -- "$HOT_RELOAD_BACKEND_BACKUP" "$HOT_RELOAD_BACKEND" || return $?
    cp -- "$HOT_RELOAD_STYLE_BACKUP" "$HOT_RELOAD_STYLE" || return $?

    HOT_RELOAD_BACKEND_SHA=$(sha256sum -- "$HOT_RELOAD_BACKEND_BACKUP" | cut -d ' ' -f1) || return $?
    HOT_RELOAD_STYLE_SHA=$(sha256sum -- "$HOT_RELOAD_STYLE_BACKUP" | cut -d ' ' -f1) || return $?
    candidate=$(git -C "$repository_root" rev-parse HEAD) || return $?
    cat > "$HOT_RELOAD_ROOT/recovery-manifest.txt" <<EOF || return $?
candidate=$candidate
compose_project=$compose_project
compose_project_directory=$repository_root
compose_file=$repository_root/docker-compose.yml
dev_compose_file=$repository_root/docker-compose.dev.yml
compose_override=$compose_override
environment_file=${CHATBI_DEV_ENV_FILE:-$repository_root/.env}
account_record_directory=$work_directory/report
model_cache=${RAG_MODEL_DIR:-}
source_backend=$repository_root/src/query_api/app.py
source_style=$repository_root/frontend/src/style.css
working_backend=$HOT_RELOAD_BACKEND
backup_backend=$HOT_RELOAD_BACKEND_BACKUP
original_backend_sha256=$HOT_RELOAD_BACKEND_SHA
working_style=$HOT_RELOAD_STYLE
backup_style=$HOT_RELOAD_STYLE_BACKUP
original_style_sha256=$HOT_RELOAD_STYLE_SHA
EOF
    chmod 600 "$HOT_RELOAD_ROOT/recovery-manifest.txt" || return $?
}

container_hot_reload_restore() {
    local report_directory=$1 status=restored backend_sha= style_sha=
    if [[ -f "$HOT_RELOAD_BACKEND_BACKUP" ]] \
        && [[ "$(sha256sum -- "$HOT_RELOAD_BACKEND_BACKUP" | cut -d ' ' -f1)" == "$HOT_RELOAD_BACKEND_SHA" ]]; then
        cp -- "$HOT_RELOAD_BACKEND_BACKUP" "$HOT_RELOAD_BACKEND" || status=failed
    else
        status=failed
    fi
    if [[ -f "$HOT_RELOAD_STYLE_BACKUP" ]] \
        && [[ "$(sha256sum -- "$HOT_RELOAD_STYLE_BACKUP" | cut -d ' ' -f1)" == "$HOT_RELOAD_STYLE_SHA" ]]; then
        cp -- "$HOT_RELOAD_STYLE_BACKUP" "$HOT_RELOAD_STYLE" || status=failed
    else
        status=failed
    fi

    if [[ -f "$HOT_RELOAD_BACKEND" ]]; then
        backend_sha=$(sha256sum -- "$HOT_RELOAD_BACKEND" | cut -d ' ' -f1)
    fi
    if [[ -f "$HOT_RELOAD_STYLE" ]]; then
        style_sha=$(sha256sum -- "$HOT_RELOAD_STYLE" | cut -d ' ' -f1)
    fi
    [[ "$backend_sha" == "$HOT_RELOAD_BACKEND_SHA" ]] || status=failed
    [[ "$style_sha" == "$HOT_RELOAD_STYLE_SHA" ]] || status=failed
    printf '{"status":"%s","backend":{"expected_sha256":"%s","restored_sha256":"%s"},"style":{"expected_sha256":"%s","restored_sha256":"%s"}}\n' \
        "$status" "$HOT_RELOAD_BACKEND_SHA" "$backend_sha" \
        "$HOT_RELOAD_STYLE_SHA" "$style_sha" > "$report_directory/hot-reload-recovery.json" || return $?
    if [[ "$status" != restored ]]; then
        echo "热更新副本恢复失败；备份保留在：$HOT_RELOAD_ROOT" >&2
        return 1
    fi
}
