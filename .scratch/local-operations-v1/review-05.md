# Ticket 05 Code Review

Date: 2026-10-08
Target: `feat/local-operations-v1` working diff based on `9f1e09e11272238f4400422b1cd6c6be00821b4f`
Reviewer: 当前主 Agent（按仓库规则在当前上下文只读复核，不启动独立 Agent）
Result: PASS

## Scope

Reviewed the restore resource binding and Compose integration, backup-to-candidate restore validation, safe PostgreSQL import and grants, full table fingerprints, session/epoch fencing, temporary login/history/result verification, plaintext staging cleanup, candidate registry, activation/recovery journal, and the affected `local` commands. Also reviewed the Runbook and roadmap status updates.

## Findings

No blocking or non-blocking findings remain in the reviewed Ticket 05 diff. The candidate remains isolated until explicitly activated; binding paths, image identity, volume labels, and registry state are validated before use. Database restore rejects unapproved roles, reapplies the approved grants, compares full table fingerprints, revokes restored sessions, and requires a new runtime epoch. Activation records its phases and requires an explicit `previous` or `candidate` choice after interruption. Failed post-decryption restore attempts clear the duplicate plaintext payload while retaining the restricted candidate record/configuration and isolated data volumes for diagnosis.

## Verification

- `.venv/bin/python -m pytest -q tests/scripts/test_local_*.py`: 118 passed.
- Ruff on the modified restore, binding, acceptance, and test files: passed.
- `git diff --check`: passed.
- `docker build --file docker/operations.Dockerfile` with the pinned PostgreSQL base and age v1.3.2: passed; restore modules and grant SQL were copied into the tool image.
- Real isolated restore from an encrypted known backup into dedicated empty PostgreSQL/Qdrant volumes: full table fingerprints, approved roles/grants, revoked sessions, epoch fencing, RAG readiness, temporary login, history and saved-result detail checks passed.
- An isolated stable clone completed candidate activation and explicit previous recovery. A forced post-decryption preflight failure returned nonzero, removed the duplicate plaintext payload, and retained the private candidate record/configuration.
- Stable and development container/image identities and health were checked before and after; they remained unchanged.

## Limits

This evidence is local and isolated. It does not initialize the actual stable backup key, activate the actual stable environment, or complete the R7 Ticket 07 failure/RTO matrix. The measured restore duration in the isolated run was within the 30-minute bound, but a single run is not a capacity or percentile claim. Ticket 06/07 and complete R7 runtime acceptance remain open.
