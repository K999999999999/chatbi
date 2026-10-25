"""Required CI test reports must contain complete, consistent evidence."""

import json
from pathlib import Path

import pytest

from scripts.check_ci_test_evidence import validate_ci_test_evidence


def junit_report(
    counts: dict[str, int] | None = None,
) -> str:
    counts = counts or {"total": 2, "passed": 2, "failed": 0, "errors": 0, "skipped": 0}
    cases = []
    for index in range(counts["passed"]):
        cases.append(f'<testcase classname="ci" name="passed-{index}"/>')
    for index in range(counts["failed"]):
        cases.append(
            f'<testcase classname="ci" name="failed-{index}"><failure/></testcase>'
        )
    for index in range(counts["errors"]):
        cases.append(
            f'<testcase classname="ci" name="error-{index}"><error/></testcase>'
        )
    for index in range(counts["skipped"]):
        cases.append(
            f'<testcase classname="ci" name="skipped-{index}"><skipped/></testcase>'
        )
    return f"<testsuites><testsuite>{''.join(cases)}</testsuite></testsuites>"


def write_postgres_reports(ci_reports: Path) -> None:
    ci_reports.mkdir(parents=True, exist_ok=True)
    for name in ("postgres-ci.xml", "postgres-development.xml"):
        (ci_reports / name).write_text(junit_report(), encoding="utf-8")
    (ci_reports / "environment.txt").write_text(
        "\n".join(
            (
                f"git_commit={'a' * 40}",
                f"uv_lock_sha256={'c' * 64}",
                f"postgres_image_id=sha256:{'e' * 64}",
                f"python_dev_image_id=sha256:{'d' * 64}",
            )
        ),
        encoding="utf-8",
    )


def renderer_evidence(
    counts: dict[str, int] | None = None,
) -> dict[str, object]:
    counts = counts or {"total": 2, "passed": 2, "failed": 0, "errors": 0, "skipped": 0}
    source = {
        "verified": True,
        "git_commit": "a" * 40,
        "git_dirty": False,
        "tracked_changes_hash": "b" * 64,
    }
    return {
        "schema_version": 1,
        "run_id": "renderer-run-123",
        "kind": "test",
        "scope": "renderer",
        "planned_steps": ["renderer"],
        "counted_steps": ["renderer"],
        "status": "passed",
        "exit_code": 0,
        "counts": counts,
        "steps": [
            {
                "name": "renderer",
                "status": "passed",
                "exit_code": 0,
                "counts": counts,
            }
        ],
        "artifacts": ["renderer-run-123/renderer.xml"],
        "missing_artifacts": [],
        "provenance": {
            "consistency": "stable",
            "source_start": source,
            "source_end": source,
        },
        "environment": {
            "runner": "dev-container",
            "runtime": "python",
            "python_version": "3.11.8",
            "lockfiles_verified": True,
            "lockfiles": {"uv": "c" * 64},
            "container_images": {"python": f"sha256:{'d' * 64}"},
        },
    }


def write_renderer_evidence(
    test_reports: Path,
    *,
    report: dict[str, object] | None = None,
    junit: str | None = None,
) -> None:
    test_reports.mkdir(parents=True, exist_ok=True)
    evidence = report or renderer_evidence()
    (test_reports / "renderer-run-123.json").write_text(
        json.dumps(evidence), encoding="utf-8"
    )
    junit_path = test_reports / "renderer-run-123" / "renderer.xml"
    junit_path.parent.mkdir(parents=True, exist_ok=True)
    junit_path.write_text(junit or junit_report(), encoding="utf-8")


def test_valid_postgres_and_renderer_evidence_passes(tmp_path: Path) -> None:
    ci_reports = tmp_path / "ci"
    test_reports = tmp_path / "tests"
    write_postgres_reports(ci_reports)
    write_renderer_evidence(test_reports)

    assert validate_ci_test_evidence(ci_reports, test_reports) == []


@pytest.mark.parametrize("profile", ["postgres-ci.xml", "postgres-development.xml"])
def test_each_postgres_profile_is_required(tmp_path: Path, profile: str) -> None:
    ci_reports = tmp_path / "ci"
    test_reports = tmp_path / "tests"
    write_postgres_reports(ci_reports)
    (ci_reports / profile).unlink()
    write_renderer_evidence(test_reports)

    errors = validate_ci_test_evidence(ci_reports, test_reports)

    assert any(profile in error for error in errors)


@pytest.mark.parametrize(
    "counts",
    [
        {"total": 0, "passed": 0, "failed": 0, "errors": 0, "skipped": 0},
        {"total": 2, "passed": 1, "failed": 1, "errors": 0, "skipped": 0},
        {"total": 2, "passed": 1, "failed": 0, "errors": 1, "skipped": 0},
        {"total": 2, "passed": 1, "failed": 0, "errors": 0, "skipped": 1},
    ],
)
def test_postgres_rejects_empty_or_nonpassing_junit(
    tmp_path: Path, counts: dict[str, int]
) -> None:
    ci_reports = tmp_path / "ci"
    test_reports = tmp_path / "tests"
    ci_reports.mkdir()
    (ci_reports / "postgres-ci.xml").write_text(junit_report(counts), encoding="utf-8")
    (ci_reports / "postgres-development.xml").write_text(
        junit_report(), encoding="utf-8"
    )
    write_renderer_evidence(test_reports)

    assert validate_ci_test_evidence(ci_reports, test_reports)


@pytest.mark.parametrize(
    "contents", ["<testsuites>", "<testsuites><testsuite/></testsuites>"]
)
def test_postgres_rejects_malformed_or_empty_junit(
    tmp_path: Path, contents: str
) -> None:
    ci_reports = tmp_path / "ci"
    test_reports = tmp_path / "tests"
    write_postgres_reports(ci_reports)
    (ci_reports / "postgres-ci.xml").write_text(contents, encoding="utf-8")
    write_renderer_evidence(test_reports)

    assert validate_ci_test_evidence(ci_reports, test_reports)


@pytest.mark.parametrize(
    "change",
    [
        lambda report: report.update(status="incomplete"),
        lambda report: report.update(exit_code=1),
        lambda report: report.update(
            counts={**report["counts"], "total": 0, "passed": 0}
        ),
        lambda report: report.update(missing_artifacts=["renderer.xml"]),
        lambda report: report["provenance"].update(consistency="unverified"),
        lambda report: report["environment"].update(lockfiles_verified=False),
    ],
)
def test_renderer_rejects_incomplete_or_untrusted_summary(
    tmp_path: Path, change
) -> None:
    ci_reports = tmp_path / "ci"
    test_reports = tmp_path / "tests"
    write_postgres_reports(ci_reports)
    report = renderer_evidence()
    change(report)
    write_renderer_evidence(test_reports, report=report)

    assert validate_ci_test_evidence(ci_reports, test_reports)


def test_renderer_requires_json_counts_to_match_junit(tmp_path: Path) -> None:
    ci_reports = tmp_path / "ci"
    test_reports = tmp_path / "tests"
    write_postgres_reports(ci_reports)
    write_renderer_evidence(
        test_reports,
        report=renderer_evidence(),
        junit=junit_report(
            {"total": 1, "passed": 1, "failed": 0, "errors": 0, "skipped": 0}
        ),
    )

    errors = validate_ci_test_evidence(ci_reports, test_reports)

    assert any("renderer" in error.lower() for error in errors)


@pytest.mark.parametrize(
    "artifact", ["missing-json", "missing-junit", "malformed-junit"]
)
def test_renderer_requires_readable_summary_and_junit(
    tmp_path: Path, artifact: str
) -> None:
    ci_reports = tmp_path / "ci"
    test_reports = tmp_path / "tests"
    write_postgres_reports(ci_reports)
    write_renderer_evidence(test_reports)
    if artifact == "missing-json":
        (test_reports / "renderer-run-123.json").unlink()
    elif artifact == "missing-junit":
        (test_reports / "renderer-run-123" / "renderer.xml").unlink()
    else:
        (test_reports / "renderer-run-123" / "renderer.xml").write_text(
            "<testsuites>", encoding="utf-8"
        )

    assert validate_ci_test_evidence(ci_reports, test_reports)


@pytest.mark.parametrize(
    "junit_counts",
    [
        {"total": 0, "passed": 0, "failed": 0, "errors": 0, "skipped": 0},
        {"total": 2, "passed": 1, "failed": 1, "errors": 0, "skipped": 0},
        {"total": 2, "passed": 1, "failed": 0, "errors": 1, "skipped": 0},
        {"total": 2, "passed": 1, "failed": 0, "errors": 0, "skipped": 1},
    ],
)
def test_renderer_rejects_zero_failed_errored_or_skipped_junit_counts(
    tmp_path: Path, junit_counts: dict[str, int]
) -> None:
    ci_reports = tmp_path / "ci"
    test_reports = tmp_path / "tests"
    write_postgres_reports(ci_reports)
    write_renderer_evidence(test_reports, junit=junit_report(junit_counts))

    assert validate_ci_test_evidence(ci_reports, test_reports)


def test_renderer_rejects_malformed_json_summary(tmp_path: Path) -> None:
    ci_reports = tmp_path / "ci"
    test_reports = tmp_path / "tests"
    write_postgres_reports(ci_reports)
    write_renderer_evidence(test_reports)
    (test_reports / "renderer-run-123.json").write_text("{", encoding="utf-8")

    errors = validate_ci_test_evidence(ci_reports, test_reports)

    assert any("JSON" in error for error in errors)


@pytest.mark.parametrize(
    ("identity_key", "replacement"),
    [
        ("git_commit", "f" * 40),
        ("uv_lock_sha256", "f" * 64),
        ("python_dev_image_id", f"sha256:{'f' * 64}"),
    ],
)
def test_renderer_identity_must_match_ci_environment_record(
    tmp_path: Path, identity_key: str, replacement: str
) -> None:
    ci_reports = tmp_path / "ci"
    test_reports = tmp_path / "tests"
    write_postgres_reports(ci_reports)
    write_renderer_evidence(test_reports)
    identity_path = ci_reports / "environment.txt"
    lines = identity_path.read_text(encoding="utf-8").splitlines()
    identity_path.write_text(
        "\n".join(
            f"{key}={replacement if key == identity_key else value}"
            for key, value in (line.split("=", maxsplit=1) for line in lines)
        ),
        encoding="utf-8",
    )

    errors = validate_ci_test_evidence(ci_reports, test_reports)

    assert any("身份" in error for error in errors)


def test_renderer_requires_ci_environment_identity_file(tmp_path: Path) -> None:
    ci_reports = tmp_path / "ci"
    test_reports = tmp_path / "tests"
    write_postgres_reports(ci_reports)
    write_renderer_evidence(test_reports)
    (ci_reports / "environment.txt").unlink()

    errors = validate_ci_test_evidence(ci_reports, test_reports)

    assert any("身份" in error for error in errors)


def test_renderer_rejects_step_counts_that_disagree_with_junit(tmp_path: Path) -> None:
    ci_reports = tmp_path / "ci"
    test_reports = tmp_path / "tests"
    write_postgres_reports(ci_reports)
    report = renderer_evidence()
    report["steps"][0]["counts"] = {
        "total": 1,
        "passed": 1,
        "failed": 0,
        "errors": 0,
        "skipped": 0,
    }
    write_renderer_evidence(test_reports, report=report)

    errors = validate_ci_test_evidence(ci_reports, test_reports)

    assert any("renderer 步骤计数" in error for error in errors)
