# Remove Redundant Domain Context File

Status: 用户确认移除
Base: `5fb3b29ad0c01c52ebc43449191299d79bb00b18` (`master`, clean)

## Goal

Remove the root `CONTEXT.md` because its glossary and multi-turn behavior are already defined by the current Architecture and Specs, and its service-restart statement conflicts with the current history-restoration Contract.

## Scope

- Delete `CONTEXT.md`.
- Preserve its exact former contents as a clearly marked historical snapshot under this work item, so historical records retain their cited source without presenting it as current guidance.
- Update historical source links to point to that snapshot; do not alter their recorded decisions or Contract text.
- Keep `docs/agents/domain.md` unchanged; it explicitly treats `CONTEXT.md` as optional.
- Do not migrate duplicated behavior rules or change Architecture, Product Scope, Specs, implementation, or Roadmap.

## Acceptance

- No Markdown link points to the deleted root file; historical references resolve to the archived snapshot.
- Documentation/link checks pass.
- Diff contains only this Spec, the archived historical snapshot, link-target updates in historical records, and deletion of root `CONTEXT.md`.

## Authorization

User confirmed the removal recommendation on 2026-10-12. This is a documentation-only change.

## Verification and Review

- `uv run --python 3.11 --locked python -m scripts.check_documentation`: PASS.
- `git diff --check`: PASS.
- The archived body was compared with `git show HEAD:CONTEXT.md` and matches exactly.
- Manual implementation Review: PASS. The root entry is removed, historical citations resolve to a clearly marked archive, and current domain guidance remains optional. No code or current behavior Contract changed.
- Software tests were not run; this change only affects documentation links and historical records.
- Roadmap review: no product goal, dependency, acceptance, or completion fact changed.
