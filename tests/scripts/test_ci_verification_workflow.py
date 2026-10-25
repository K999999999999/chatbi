"""CI coverage stays aligned with the local database and PDF suites."""

import re
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/ci.yml"


def postgres_job() -> str:
    lines = WORKFLOW.read_text(encoding="utf-8").splitlines()
    start = lines.index("  postgres-integration:")
    end = next(
        (
            index
            for index in range(start + 1, len(lines))
            if re.fullmatch(r"  [a-z][a-z0-9-]*:", lines[index])
        ),
        len(lines),
    )
    return "\n".join(lines[start:end])


def step(job: str, name: str) -> str:
    lines = job.splitlines()
    marker = f"      - name: {name}"
    start = lines.index(marker)
    end = next(
        (
            index
            for index in range(start + 1, len(lines))
            if lines[index].startswith("      - name: ")
        ),
        len(lines),
    )
    return "\n".join(lines[start:end])


@pytest.fixture(scope="module")
def job() -> str:
    return postgres_job()


def test_existing_postgres_job_runs_ci_database_profile_with_junit(job: str) -> None:
    assert "name: PostgreSQL integration" in job
    assert "image: postgres:16-alpine" in job
    assert "timeout-minutes: 60" in job
    assert "fetch-depth: 0" in step(job, "Check out repository")

    ci = step(job, "Run PostgreSQL CI profile")
    assert 'RUN_DATABASE_TESTS: "1"' in ci
    assert "tests/online_query/test_database_integration.py" in ci
    assert (
        "tests/online_query/test_service_integration.py::ServiceDatabaseIntegrationTest"
        in ci
    )
    assert "--junitxml=reports/ci/postgres-ci.xml" in ci
    assert "set -euo pipefail" in ci


def test_ci_evidence_records_tool_lock_and_actual_postgres_image_identity(
    job: str,
) -> None:
    identity = step(job, "Record PostgreSQL test environment identity")
    assert "uv python find 3.11" in identity
    assert "git rev-parse --verify HEAD" in identity
    assert "git_commit" in identity
    assert "uv --version" in identity
    assert "postgres_image_id" in identity
    assert "uv_lock_sha256" in identity
    assert "package_lock_sha256" in identity
    assert "LLM_API_KEY" not in job
    assert "LLM_BASE_URL" not in job
    assert "docker/app.Dockerfile" not in job
    assert "chatbi-app" not in job


def test_development_database_profile_uses_local_fixture_migration_and_selection(
    job: str,
) -> None:
    fixture = step(job, "Initialize development PostgreSQL fixture")
    assert "DROP DATABASE IF EXISTS chatbi_mvp WITH (FORCE)" in fixture
    assert "DROP ROLE IF EXISTS chatbi_app" in fixture
    assert "DROP ROLE IF EXISTS chatbi_control_user" in fixture
    assert "createdb" in fixture
    assert "database/init/10_chatbi_dev_environment.sh" in fixture
    assert "set -euo pipefail" in fixture
    assert (
        fixture.index("DROP DATABASE IF EXISTS chatbi_mvp WITH (FORCE)")
        < fixture.index("DROP ROLE IF EXISTS chatbi_app")
        < fixture.index("createdb")
    )

    development = step(job, "Run PostgreSQL development profile")
    assert 'RUN_DATABASE_TESTS: "1"' in development
    assert 'RUN_DEVELOPMENT_DATABASE_TESTS: "1"' in development
    assert "src.bootstrap migrate" in development
    assert "tests/online_query/test_database_integration.py" in development
    assert (
        "tests/online_query/test_service_integration.py::ServiceDatabaseIntegrationTest"
        in development
    )
    assert "tests/chatbi_control/test_postgres_dev_environment.py" in development
    assert "tests/chatbi_control/test_admin_recovery_postgres.py" in development
    assert "tests/chatbi_control/test_execution_postgres.py" in development
    assert "tests/chatbi_control/test_history_postgres.py" in development
    assert "tests/evaluation/common/test_database_fingerprint.py" in development
    assert "--junitxml=reports/ci/postgres-development.xml" in development
    assert "set -euo pipefail" in development


def test_postgres_job_runs_real_pdf_renderer_in_development_image(
    job: str,
) -> None:
    build = step(job, "Build PDF renderer test image")
    assert "docker/python-dev.Dockerfile" in build
    assert "chatbi-python-dev:ci" in build
    assert "set -euo pipefail" in build
    assert "python_dev_image_id" in build

    dockerfile = (ROOT / "docker/python-dev.Dockerfile").read_text(encoding="utf-8")
    assert re.search(
        r"^ARG PYTHON_BASE=.*@sha256:[0-9a-f]{64}$", dockerfile, re.MULTILINE
    )
    assert re.search(
        r"^ARG NODE_BASE=.*@sha256:[0-9a-f]{64}$", dockerfile, re.MULTILINE
    )

    renderer = step(job, "Run real PDF renderer tests")
    assert "CHATBI_DEV_PYTHON_IMAGE: chatbi-python-dev:ci" in renderer
    assert "./dev test renderer" in renderer
    assert "set -euo pipefail" in renderer


def test_postgres_job_always_uploads_available_test_evidence(job: str) -> None:
    upload = step(job, "Upload PostgreSQL and renderer evidence")
    assert "if: always()" in upload
    assert "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02" in upload
    assert "reports/ci/" in upload
    assert "reports/tests/" in upload
    assert "reports/evaluation/" not in upload
    assert "if-no-files-found: ignore" in upload
    assert job.index(
        "      - name: Upload PostgreSQL and renderer evidence"
    ) > job.index("      - name: Run real PDF renderer tests")

    for test_step in (
        "Run PostgreSQL CI profile",
        "Initialize development PostgreSQL fixture",
        "Run PostgreSQL development profile",
        "Build PDF renderer test image",
        "Run real PDF renderer tests",
    ):
        assert "continue-on-error: true" not in step(job, test_step)


def test_postgres_job_validates_required_report_evidence_before_upload(
    job: str,
) -> None:
    validation = step(job, "Validate PostgreSQL and renderer evidence")
    assert "if: always()" in validation
    assert "scripts.check_ci_test_evidence" in validation
    assert "--ci-reports reports/ci" in validation
    assert "--test-reports reports/tests" in validation
    assert job.index(
        "      - name: Validate PostgreSQL and renderer evidence"
    ) > job.index("      - name: Run real PDF renderer tests")
    assert job.index(
        "      - name: Upload PostgreSQL and renderer evidence"
    ) > job.index("      - name: Validate PostgreSQL and renderer evidence")
