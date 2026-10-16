#!/usr/bin/env bash
# 共享宿主目标解析；调用方先验证命令和参数，再读取配置。
validate_env_file_permissions() {
    local path=$1 metadata owner mode mode_bits
    if [[ ! -f "$path" ]]; then
        echo '缺少本地配置；复制 .env.example 并填写配置后重试。' >&2
        return 2
    fi
    metadata=$(stat -c '%u:%a' -- "$path" 2>/dev/null) || metadata=
    owner=${metadata%%:*}
    mode=${metadata#*:}
    if [[ "$metadata" == *:* && "$mode" =~ ^[0-7]{3,4}$ ]]; then
        mode_bits=$((8#$mode))
        if [[ "$owner" == "$(id -u)" ]] \
            && (( (mode_bits & 0400) != 0 && (mode_bits & ~0600) == 0 )); then
            return 0
        fi
    fi
    echo '本地配置必须由当前用户拥有且仅当前用户可读；请检查属主并执行 chmod 600 <配置文件> 后重试。' >&2
    return 2
}

initialize_environment() {
    if (($# != 1)) || [[ "$1" != dev ]]; then
        echo '维护目标无效；当前只支持 dev。' >&2
        return 2
    fi
    target=dev
    host_root=${LOCAL_WORKSPACE_FOLDER:-$root}
    env_file=${CHATBI_DEV_ENV_FILE:-$root/.env}
    override=${CHATBI_DEV_COMPOSE_OVERRIDE:-}
    compose_files=(-f "$root/docker-compose.yml" -f "$root/docker-compose.dev.yml")
    services=(api web postgres qdrant)
    validate_env_file_permissions "$env_file" || return 2
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
