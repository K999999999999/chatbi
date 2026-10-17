"""隔离热更新副本恢复及可处理信号的故障注入。"""

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
HELPER = ROOT / "scripts/container_hot_reload.sh"


def source_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def invoke_helper(work: Path, body: str) -> subprocess.CompletedProcess[str]:
    script = "\n".join(
        (
            "set -euo pipefail",
            'source "$1"',
            'container_hot_reload_init "$2" "$3" isolated-test "$3/compose.yml"',
            body,
        )
    )
    return subprocess.run(
        ["bash", "-c", script, "hot-reload-test", str(HELPER), str(ROOT), str(work)],
        capture_output=True,
        text=True,
        check=False,
    )


def test_restore_after_browser_failure_keeps_original_sources_and_reports_hashes(
    tmp_path,
):
    backend = ROOT / "src/query_api/app.py"
    style = ROOT / "frontend/src/style.css"
    original_hashes = (source_hash(backend), source_hash(style))
    work = tmp_path / "work"
    (work / "report").mkdir(parents=True)
    result = invoke_helper(
        work,
        "printf '\\n# browser failure injection\\n' >> \"$HOT_RELOAD_BACKEND\"\n"
        "printf '\\n/* browser failure injection */\\n' >> \"$HOT_RELOAD_STYLE\"\n"
        'container_hot_reload_restore "$3/report"\n'
        "exit 17",
    )

    assert result.returncode == 17
    assert (source_hash(backend), source_hash(style)) == original_hashes
    report = json.loads((work / "report/hot-reload-recovery.json").read_text())
    assert report == {
        "status": "restored",
        "backend": {
            "expected_sha256": original_hashes[0],
            "restored_sha256": original_hashes[0],
        },
        "style": {
            "expected_sha256": original_hashes[1],
            "restored_sha256": original_hashes[1],
        },
    }
    manifest = (work / "hot-reload/recovery-manifest.txt").read_text()
    assert "compose_project=isolated-test" in manifest
    assert "original_backend_sha256=" + original_hashes[0] in manifest
    assert "original_style_sha256=" + original_hashes[1] in manifest


def test_exit_cleanup_recovers_write_failure_after_prepare_error(tmp_path):
    backend = ROOT / "src/query_api/app.py"
    style = ROOT / "frontend/src/style.css"
    original_hashes = (source_hash(backend), source_hash(style))
    work = tmp_path / "work"
    (work / "report").mkdir(parents=True)
    result = invoke_helper(
        work,
        'report_directory="$3/report"\n'
        'cleanup() { local code=$?; container_hot_reload_restore "$report_directory" || exit 1; exit "$code"; }\n'
        "trap cleanup EXIT\n"
        "printf '\\n# prepare failure injection\\n' >> \"$HOT_RELOAD_BACKEND\"\n"
        'rm -- "$HOT_RELOAD_STYLE"\n'
        "exit 23",
    )

    assert result.returncode == 23
    assert (source_hash(backend), source_hash(style)) == original_hashes
    report = json.loads((work / "report/hot-reload-recovery.json").read_text())
    assert report["status"] == "restored"
    assert report["style"]["restored_sha256"] == original_hashes[1]


@pytest.mark.parametrize(("signal", "exit_code"), [("INT", 130), ("TERM", 143)])
def test_handled_signal_restores_temporary_sources(signal, exit_code, tmp_path):
    backend = ROOT / "src/query_api/app.py"
    style = ROOT / "frontend/src/style.css"
    original_hashes = (source_hash(backend), source_hash(style))
    work = tmp_path / "work"
    (work / "report").mkdir(parents=True)
    result = invoke_helper(
        work,
        f"trap 'container_hot_reload_restore \"$3/report\" || exit 1; exit {exit_code}' {signal}\n"
        "printf '\\n# interrupted\\n' >> \"$HOT_RELOAD_BACKEND\"\n"
        f"kill -{signal} $$",
    )

    assert result.returncode == exit_code
    assert (source_hash(backend), source_hash(style)) == original_hashes
    report = json.loads((work / "report/hot-reload-recovery.json").read_text())
    assert report["status"] == "restored"


def test_corrupt_backup_is_reported_as_failed_without_touching_repository_sources(
    tmp_path,
):
    backend = ROOT / "src/query_api/app.py"
    style = ROOT / "frontend/src/style.css"
    original_hashes = (source_hash(backend), source_hash(style))
    work = tmp_path / "work"
    (work / "report").mkdir(parents=True)
    result = invoke_helper(
        work,
        "printf '\\n# corrupt backup\\n' >> \"$HOT_RELOAD_BACKEND_BACKUP\"\n"
        'if container_hot_reload_restore "$3/report"; then exit 0; else exit 19; fi',
    )

    assert result.returncode == 19
    assert (source_hash(backend), source_hash(style)) == original_hashes
    report = json.loads((work / "report/hot-reload-recovery.json").read_text())
    assert report["status"] == "failed"
