#!/usr/bin/env bash
# Isolated adapter for the optional engineering-workflow source checkout.
set -euo pipefail

root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
host_root=${LOCAL_WORKSPACE_FOLDER:-$root}
plugin_source=${CHATBI_ENGINEERING_WORKFLOW_SOURCE_ROOT:-}
while (($#)); do
    case "$1" in
        --plugin-source)
            (($# >= 2)) && [[ -n "$2" && "$2" != -* ]] || {
                echo '用法: ./dev harness control [--plugin-source PATH] <Harness命令及参数>' >&2
                exit 2
            }
            plugin_source=$2
            shift 2
            ;;
        *) break ;;
    esac
done

fail() {
    echo "$1" >&2
    exit 2
}

(($#)) || fail 'Harness 命令缺失；请显式指定 state、diff、diagnostic、closeout、maintenance 或 onboard 子命令。'
[[ -n "$plugin_source" ]] || fail '未指定 Plugin 源码根目录；使用 --plugin-source 或 CHATBI_ENGINEERING_WORKFLOW_SOURCE_ROOT。'
[[ -d "$plugin_source" ]] || fail 'Plugin 源码路径不存在或不是目录；未执行 Harness 命令。'
plugin_source=$(cd -- "$plugin_source" && pwd -P)
if [[ -f "$plugin_source/.codex-plugin/plugin.json" ]]; then
    plugin_root=$plugin_source
elif [[ -f "$plugin_source/plugins/engineering-workflow/.codex-plugin/plugin.json" ]]; then
    plugin_root="$plugin_source/plugins/engineering-workflow"
else
    fail '指定路径不是 engineering-workflow Plugin 根目录或源码仓库；未执行或回退到旧工具。'
fi
plugin_manifest="$plugin_root/.codex-plugin/plugin.json"
[[ -f "$plugin_manifest" && ! -L "$plugin_manifest" \
    && -f "$plugin_root/tools/harness.py" && ! -L "$plugin_root/tools/harness.py" \
    && -d "$plugin_root/tools/harness_lib" && ! -L "$plugin_root/tools/harness_lib" ]] \
    || fail '指定的 engineering-workflow Plugin 包未包含 Harness CLI；未执行或回退到旧工具。'
grep -Eq '"name"[[:space:]]*:[[:space:]]*"engineering-workflow"' "$plugin_manifest" \
    || fail 'Plugin 元数据名称不匹配；未执行 Harness 命令。'
[[ -f "$root/.harness/project.json" && ! -L "$root/.harness/project.json" ]] \
    || fail 'ChatBI .harness/project.json 缺失或不是普通文件；未执行 Harness 命令。'

tool_args=("$@")
tool_command=${tool_args[0]}
write_operation=false
case "$tool_command" in
    state|diff) ;;
    diagnostic)
        (($# >= 2)) || fail 'diagnostic 需要子命令。'
        case "${tool_args[1]}" in report) ;; start|record|wait|resume|alias|decision) write_operation=true ;; *) fail '不支持的 diagnostic 子命令。' ;; esac
        ;;
    closeout)
        (($# >= 2)) || fail 'closeout 需要子命令。'
        case "${tool_args[1]}" in check|recover) ;; record-file|finalize) write_operation=true ;; *) fail '不支持的 closeout 子命令。' ;; esac
        ;;
    maintenance)
        (($# >= 2)) || fail 'maintenance 需要子命令。'
        case "${tool_args[1]}" in list) ;; open|defer|close) write_operation=true ;; *) fail '不支持的 maintenance 子命令。' ;; esac
        ;;
    onboard)
        (($# >= 2)) || fail 'onboard 需要子命令。'
        case "${tool_args[1]}" in discover|plan|remote-check) ;;
            apply) fail 'onboard apply 会写入项目源码；此适配器只允许写 Harness 状态目录。' ;;
            *) fail '不支持的 onboard 子命令。' ;;
        esac
        ;;
    capture-baseline|attest-evidence|migrate|transition|set-runtime) write_operation=true ;;
    *) fail '不支持的 Harness 命令；未执行旧工具或替代检查。' ;;
esac

work_item=
work_item_seen=false
for ((index=0; index<${#tool_args[@]}; index++)); do
    case "${tool_args[index]}" in
        --project-root|--project-root=*) fail '项目根目录由适配器固定；不得通过 Harness 参数覆盖。' ;;
        --adapter|--adapter=*) fail '项目适配文件由适配器固定；不得通过 Harness 参数覆盖。' ;;
        --work-item)
            [[ "$work_item_seen" != true && $((index + 1)) -lt ${#tool_args[@]} ]] \
                || fail '--work-item 缺失、重复或格式错误。'
            work_item_seen=true
            work_item=${tool_args[index+1]}
            ((index += 1))
            ;;
        --work-item=*)
            [[ "$work_item_seen" != true ]] || fail '--work-item 不得重复。'
            work_item_seen=true
            work_item=${tool_args[index]#--work-item=}
            ;;
    esac
done

status_mount=()
if [[ "$write_operation" == true ]]; then
    [[ "$work_item_seen" == true && "$work_item" =~ ^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$ ]] \
        || fail '状态写入必须指定有效的 --work-item。'
    source "$root/scripts/dev_environment.sh"
    prepare_git_mounts
    common_dir=$(git -C "$root" rev-parse --path-format=absolute --git-common-dir) \
        || fail '无法核实 Git 公共目录；未写入状态。'
    [[ -d "$common_dir" && ! -L "$common_dir" ]] || fail 'Git 公共目录不是普通目录；未写入状态。'
    for path in "$common_dir/harness" "$common_dir/harness/work-items" \
        "$common_dir/harness/work-items/$work_item"; do
        [[ ! -L "$path" ]] || fail 'Harness 状态路径含符号链接；未写入状态。'
    done
    status_dir="$common_dir/harness/work-items/$work_item"
    [[ -d "$status_dir" && -f "$status_dir/status.md" && ! -L "$status_dir/status.md" ]] \
        || fail '工作项状态目录或 status.md 不存在；适配器不会创建或迁移旧记录。'
    if [[ -n ${CHATBI_GIT_COMMON_DIR_HOST:-} ]]; then
        host_common=$CHATBI_GIT_COMMON_DIR_HOST
    elif [[ "$common_dir" == "$root/"* ]]; then
        host_common="$host_root/${common_dir#"$root/"}"
    else
        host_common=$common_dir
    fi
    host_status_dir="$host_common/harness/work-items/$work_item"
    [[ -d "$host_status_dir" && ! -L "$host_status_dir" ]] \
        || fail '宿主无法定位 Git 公共目录中的工作项状态目录；未写入状态。'
    status_mount=(-v "$host_status_dir:$status_dir:rw")
else
    source "$root/scripts/dev_environment.sh"
    prepare_git_mounts
    common_dir=$(git -C "$root" rev-parse --path-format=absolute --git-common-dir) \
        || fail '无法核实 Git 公共目录。'
fi

python_image=${CHATBI_DEV_PYTHON_IMAGE:-chatbi-python-dev:local}
if ! image_id=$(docker image inspect --format '{{.Id}}' "$python_image" 2>/dev/null) \
    || [[ -z "$image_id" ]]; then
    fail "本地容器镜像 $python_image 不可用；没有联网安装，也没有回退到旧工具。"
fi

uid=$(id -u)
gid=$(id -g)
plugin_mount_root=/opt/engineering-workflow
docker_args=(
    run --rm --init --read-only --user "$uid:$gid" --workdir "$root"
    --network none --tmpfs /tmp:rw,noexec,nosuid,size=16m
    -v "$host_root:$root:ro"
    "${git_mounts[@]}"
    -v "$plugin_root:$plugin_mount_root:ro"
    "${status_mount[@]}"
    -e PYTHONDONTWRITEBYTECODE=1
    "${git_environment[@]}"
    --entrypoint python "$python_image"
    "$plugin_mount_root/tools/harness.py"
    --project-root "$root"
    --adapter "$root/.harness/project.json"
    "${tool_args[@]}"
)
echo 'Harness CLI 来源为显式指定的只读 Plugin 包；这不证明该包已安装或已加载到当前会话。' >&2
exec docker "${docker_args[@]}"
