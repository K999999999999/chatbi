#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel 2>/dev/null)" || {
  printf '请从 ChatBI Git worktree 内运行此脚本。\n' >&2
  exit 1
}

if [[ ! -x "$repo_root/.githooks/pre-commit" ]]; then
  printf '缺少可执行 Hook：.githooks/pre-commit\n' >&2
  exit 1
fi

if hook_settings="$(git config --show-scope --get-all core.hooksPath 2>/dev/null)"; then
  persistent_setting=false
  while IFS=$'\t' read -r config_scope configured_path; do
    if [[ "$configured_path" != ".githooks" ]]; then
      printf '检测到既有 core.hooksPath；为保留现有 Hook 配置，未作修改。\n' >&2
      exit 1
    fi
    if [[ "$config_scope" != "command" ]]; then
      persistent_setting=true
    fi
  done <<< "$hook_settings"
  if [[ "$persistent_setting" == "true" ]]; then
    printf 'Git hooks 已持久指向 .githooks，无需修改配置。\n'
  else
    git config --local core.hooksPath .githooks
    printf '已将本仓库 core.hooksPath 持久设置为 .githooks。\n'
  fi
else
  config_status=$?
  if [[ "$config_status" -ne 1 ]]; then
    printf '无法读取 Git core.hooksPath 配置，未作修改。\n' >&2
    exit "$config_status"
  fi
  git config --local core.hooksPath .githooks
  printf '已将本仓库 core.hooksPath 设置为 .githooks。\n'
fi
