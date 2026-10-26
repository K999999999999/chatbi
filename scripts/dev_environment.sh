#!/usr/bin/env bash
# 共享宿主目标解析；调用方先验证命令和参数，再读取配置。
require_bind_source() {
    if [[ "$1" != /* || "$1" == *','* || "$1" == *$'\n'* || "$1" == *$'\r'* || ! -e "$1" ]]; then
        echo '宿主 bind source 不存在或当前调用方不可核实；未启动容器，不创建源码目录。请核对宿主映射并从可验证该路径的环境调用。' >&2
        return 2
    fi
}

docker_run_checked() {
    local previous= argument spec field source
    local -a fields=()
    for argument in "$@"; do
        spec=
        if [[ "$previous" == --mount ]]; then spec=$argument; previous=;
        elif [[ "$argument" == --mount ]]; then previous=--mount; continue;
        elif [[ "$argument" == --mount=* ]]; then spec=${argument#--mount=}; fi
        [[ "$spec" == type=bind,* ]] || continue
        IFS=, read -r -a fields <<< "$spec"
        source=
        for field in "${fields[@]}"; do
            case "$field" in src=*|source=*) source=${field#*=} ;; esac
        done
        [[ -n "$source" ]] || { echo 'bind source 缺失；未启动容器。' >&2; return 2; }
        require_bind_source "$source" || return 2
    done
    command docker run "$@"
}

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
    require_bind_source "$host_root" || return 2
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
    require_bind_source "$host_root" || return 2
    git_mounts=()
    local git_common git_worktree git_host_common git_host_worktree
    git_common=$(git -C "$root" rev-parse --path-format=absolute --git-common-dir) || return 1
    git_worktree=$(git -C "$root" rev-parse --absolute-git-dir) || return 1
    git_host_common=${CHATBI_GIT_COMMON_DIR_HOST:-$git_common}
    if [[ "$git_common" == "$root/"* ]]; then git_host_common="$host_root/${git_common#"$root/"}"; fi
    git_host_worktree=$git_worktree
    if [[ "$git_worktree" == "$git_common"* ]]; then git_host_worktree="$git_host_common${git_worktree#"$git_common"}"; fi
    require_bind_source "$git_host_common" || return 2
    require_bind_source "$git_host_worktree" || return 2
    git_mounts=(--mount "type=bind,src=$git_host_common,dst=$git_common,readonly")
    [[ "$git_worktree" == "$git_common" ]] || git_mounts+=(--mount "type=bind,src=$git_host_worktree,dst=$git_worktree,readonly")
    git_environment=(-e GIT_OPTIONAL_LOCKS=0 -e GIT_CONFIG_COUNT=1
        -e GIT_CONFIG_KEY_0=safe.directory -e "GIT_CONFIG_VALUE_0=$root")
}

# Harness 检查所有登记工作树；仅挂载现存登记，绝不创建缺失源码。
prepare_harness_worktree_mounts() {
    local repository=${1:-$root} entry checkout= prunable=false source fd reader
    exec {fd}< <(git -C "$repository" worktree list --porcelain -z)
    reader=$!
    while IFS= read -r -d '' entry <&"$fd"; do
        case "$entry" in
            'worktree '*) checkout=${entry#worktree }; prunable=false ;;
            prunable*) prunable=true ;;
            '')
                if [[ -n "$checkout" && "$checkout" != "$root" && "$checkout" != "$repository" && "$prunable" != true ]]; then
                    source=$(host_source_path "$checkout")
                    git_mounts+=(--mount "type=bind,src=$source,dst=$checkout,readonly")
                fi
                checkout= ;;
        esac
    done
    exec {fd}<&-
    wait "$reader"
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
