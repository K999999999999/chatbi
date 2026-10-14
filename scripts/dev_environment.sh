#!/usr/bin/env bash
# 共享宿主目标解析；调用方先验证命令和参数，再读取配置。
initialize_environment() {
    target=$1
    host_root=${LOCAL_WORKSPACE_FOLDER:-$root}
    if [[ "$target" == app ]]; then
        env_file=${CHATBI_APP_ENV_FILE:-$root/.env}
        override=${CHATBI_APP_COMPOSE_OVERRIDE:-}
        compose_files=(-f "$root/docker-compose.app.yml")
        services=(api postgres qdrant)
    else
        env_file=${CHATBI_DEV_ENV_FILE:-$root/.env}
        override=${CHATBI_DEV_COMPOSE_OVERRIDE:-}
        compose_files=(-f "$root/docker-compose.yml" -f "$root/docker-compose.dev.yml")
        services=(api web postgres qdrant)
    fi
    [[ -f "$env_file" ]] || { echo '缺少本地配置；复制 .env.example 并填写配置后重试。' >&2; return 2; }
    export CHATBI_DEV_UID=${CHATBI_DEV_UID:-$(id -u)}
    export CHATBI_DEV_GID=${CHATBI_DEV_GID:-$(id -g)}
    export CHATBI_DEV_SECCOMP_PROFILE=${CHATBI_DEV_SECCOMP_PROFILE:-$root/docker/third-party/playwright-seccomp-profile.json}
    if [[ "$target" == dev && "$host_root" != "$root" ]]; then
        export CHATBI_DEV_PROJECT_NAME="$(basename -- "$host_root")"
        compose_files+=(-f "$root/docker/dev-project-name.yml")
    fi
    compose=(docker compose --project-directory "$root" --env-file "$env_file" "${compose_files[@]}")
    [[ -z "$override" ]] || compose+=(-f "$override")
}

# 在容器中保持真实worktree和Git公共目录身份；挂载只读。
prepare_git_mounts() {
    git_mounts=()
    local git_common git_worktree git_host_common git_host_worktree
    git_common=$(git -C "$root" rev-parse --path-format=absolute --git-common-dir) || return 1
    git_worktree=$(git -C "$root" rev-parse --absolute-git-dir) || return 1
    git_host_common=${CHATBI_GIT_COMMON_DIR_HOST:-$git_common}
    if [[ "$git_common" == "$root/"* ]]; then git_host_common="$host_root/${git_common#"$root/"}"; fi
    git_host_worktree=$git_worktree
    if [[ "$git_worktree" == "$git_common"* ]]; then git_host_worktree="$git_host_common${git_worktree#"$git_common"}"; fi
    git_mounts=(-v "$git_host_common:$git_common:ro")
    [[ "$git_worktree" == "$git_common" ]] || git_mounts+=(-v "$git_host_worktree:$git_worktree:ro")
    git_environment=(-e GIT_OPTIONAL_LOCKS=0 -e GIT_CONFIG_COUNT=1
        -e GIT_CONFIG_KEY_0=safe.directory -e "GIT_CONFIG_VALUE_0=$root")
}

host_source_path() {
    local path=$1
    if [[ "$path" == "$root" ]]; then printf '%s\n' "$host_root";
    elif [[ "$path" == "$root/"* ]]; then printf '%s/%s\n' "$host_root" "${path#"$root/"}";
    else printf '%s\n' "$path"; fi
}
local_source_path() {
    local path=$1
    if [[ "$path" == "$host_root" ]]; then printf '%s\n' "$root";
    elif [[ "$path" == "$host_root/"* ]]; then printf '%s/%s\n' "$root" "${path#"$host_root/"}";
    else printf '%s\n' "$path"; fi
}
create_temporary_directory() {
    mkdir -p -- "$root/.local/dev-tools"
    mktemp -d "$root/.local/dev-tools/task.XXXXXX"
}
