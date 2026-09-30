# 核验本机 Plugin 状态后再作判断

Status: done

## Goal

避免 Agent 仅凭对话记忆或局部线索，对 Skill Plugin 的来源、安装、启用、版本或同步状态作出未经核实的断言。

## Expected outcome

仓库入口规则要求 Agent 检查能证明相关状态的实际配置与文件；无法核实时，把结论标为未确认。

## Acceptance

- `AGENTS.md` 明确适用场景包括 Skill Plugin 来源、安装、启用、版本和同步状态。
- 规则明确要求先检查配置与文件，并禁止凭对话记忆或局部线索断言未核实状态。
- 变更仅更新 Agent 协作规则，不改变产品行为或 Plugin 安装配置。

## Verification

- 检查最终 Diff 仅包含本 Spec 与 `AGENTS.md`。
- `git diff --check` 通过。

## Result

已在 `AGENTS.md` 加入状态核验规则；没有修改 Plugin 安装或本机配置。
