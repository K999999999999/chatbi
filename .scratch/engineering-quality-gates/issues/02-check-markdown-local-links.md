# Ticket 02：在 CI 检查 Markdown 本地链接

Status: done

## Owner

ChatBI 仓库维护者负责验收；当前实施 Agent 负责实现。

## Blocked by

None (can start immediately)

## Change Profile

- Lifetime: 长期维护的文档质量门禁。
- Size: 小到中等，新增确定性检查并接入 CI。
- Risk: 低；只读仓库文档，不访问外部服务。
- Evidence: checker 的正反例测试和 CI 运行结果。
- Delivery: 与同一 Feature 的其他 Ticket 使用同一 branch 和 PR。

## What to build

在普通 CI 中检查所有受版本控制的 Markdown 文件里的仓库内相对路径和本地锚点。外部 HTTP(S) 链接不联网验证；忽略 fenced code block 中的示例文本，避免把命令或示例误识别为文档链接。

## Acceptance criteria

- 有效的仓库内文件路径和锚点通过。
- 失效的本地路径或锚点使检查失败，并指出来源 Markdown 文件和目标。
- 外部 HTTP(S) 链接不触发网络请求，也不因第三方服务状态导致 CI 失败。
- 仓库示例代码块中的路径或 URL 不作为 Markdown 链接处理。
- 正反例均有确定性测试，检查在普通 CI 的 Push / Pull Request 路径运行。
- 不添加与链接检查无关的 Markdown 风格或文案门禁。

## Owned files

- `.github/workflows/ci.yml`
- `scripts/check_markdown_links.py`
- `tests/scripts/test_check_markdown_links.py`

## Verification evidence

- 测试有效相对链接、本地锚点、损坏路径、损坏锚点、外部链接和代码块内容。
- 在普通 CI 中执行检查；不联网验证外部链接。

## Migration / Rollback

无数据或运行时 Migration。若误报真实文档链接，修正解析边界或误报规则；回退时移除此门禁，不更改用户文档 Contract。

## Done When

受版本控制的 Markdown 文件通过本地链接检查，反例测试能稳定失败，且 CI 在 PR 与 Push 路径运行该检查。

## Result

已在普通 CI 的 Push / Pull Request 检查中运行本地路径和 Markdown 锚点校验。检查包含 fenced code block、外链、重复标题、Setext 标题及仓库路径越界处理；全仓当前 Markdown 链接检查通过，相关确定性测试通过。

## Comments

None.
