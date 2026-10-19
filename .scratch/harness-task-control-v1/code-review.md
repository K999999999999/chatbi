# Harness Task Control V1 Code Review

Review: PASS AFTER FIX
Date: 2026-10-19
ChatBI base: `2897302038fa42167e79a0b5ad483c2b628359b9`
Plugin base: `6681366453eedce45e36f989a082df8a78b85819`
Scope: ChatBI container adapter, project manifest / docs / fixture tests; Plugin packaged CLI, workflow / state / evidence / budget / closeout / onboarding / maintenance modules, Skill wiring, manifest, CI workflow and tests.

## Finding fixed

The ChatBI adapter fixed `--project-root`, but initially allowed a caller to pass a later `--adapter` option. Because the CLI accepts that option, a caller could make this command use a different stage graph or record-path configuration instead of ChatBI's declared `.harness/project.json`.

The adapter now rejects both `--adapter` and `--adapter=...`, just as it rejects project-root overrides. A parameterized regression case proves the command exits before invoking Docker. The ChatBI adapter suite passes 12 tests after this change.

## Review checks

- The Plugin CLI is distributed from one canonical package path: `plugins/engineering-workflow/tools/`; the repository-root path is absent. Skill references resolve to one shared integration guide.
- State writes use an expected record digest, exclusive lock and atomic replacement; legacy records remain read-only until explicit migration with a preserved backup.
- Candidate evidence binds the repository / work item and current candidate fingerprint. Sensitive or unreadable paths make a Diff incomplete; ignored files are not inspected.
- Diagnostic retries stop at the configured no-progress / time boundary, preserve prior attempts and require an explicit recorded decision to continue after escalation.
- Closeout binds dynamic-file reviews, validation, Code Review, Tickets, child work items, diagnostics and maintenance evidence to the current candidate. Local completion remains separate from remote delivery.
- Onboarding / remote checks do not call GitHub or write remote settings. ChatBI's adapter denies source-file onboarding writes and mounts only the named existing work-item status directory read-write.
- The container uses `--read-only`, `--network none`, no Docker socket and no `.env`; missing tools / image fail without falling back to the old checker.
- The Plugin workflow is source-controlled, uses read-only GitHub token permissions and pinned Actions, and runs standard-library tests. Its existence is not treated as a remote required-check rule.
- The change contains no ChatBI application or business-contract modifications. The Plugin source worktree and user 7z archive remain untouched.

## Verification and residual boundaries

- Plugin tests: 53/53 pass on Python 3.14.4 and Python 3.11.16; the Python 3.11 run used the existing container image, read-only source mount and disabled network.
- ChatBI adapter tests: 12/12 pass. Full `./dev test python`: 1118 passed, 0 failed, 0 errors, 61 skipped, 155 subtests; report marks the broader run `incomplete` because isolated PostgreSQL / renderer / real-LLM cases were skipped and Business Acceptance was not run.
- `./dev check docs`, Markdown-link validation and both repositories' `git diff --check` pass.
- Synthetic container end-to-end evidence is recorded in [acceptance.md](acceptance.md). GitHub Actions, PR publication, Marketplace installation / session loading, remote Ruleset changes and isolated failure injection remain unexecuted by authorization.

No unresolved code-review findings. This review covers the local candidate only; it does not certify remote CI or loaded Plugin behavior.
