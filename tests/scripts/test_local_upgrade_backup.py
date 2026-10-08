"""local orchestration 的失败状态边界；不调用真实 stable Docker。"""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("backup_succeeds", [False, True])
def test_upgrade_backup_is_before_stop_and_failure_preserves_running_source(
    tmp_path, backup_succeeds
):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    for name in (
        "local_port.sh",
        "local_build_cache.sh",
        "local_deployment_state.sh",
        "local_backup.sh",
        "local_runtime_binding.sh",
    ):
        shutil.copyfile(ROOT / "scripts" / name, scripts / name)
    entry = tmp_path / "local-functions"
    entry.write_text((ROOT / "local").read_text().removesuffix('main "$@"\n'))
    active = tmp_path / "active"
    data = tmp_path / "data"
    active.write_text("old-api-running")
    data.write_bytes(b"old database contents")
    program = r"""
source "$1"
require_config() { :; }
read_config_value() { printf 8080; }
require_release() { :; }
require_docker() { :; }
prepare_host_directories() { :; }
check_compose_config() { :; }
verify_release_images() { :; }
run_manual_backup() {
    printf 'backup-old-active\n'
    [[ "$2_BACKUP_RESULT" == success ]]
}
start_infrastructure() { printf 'infra\n'; }
capture_running_release() {
    RUNNING_SOURCE_COMMIT=old
    RUNNING_API_IMAGE=old
    RUNNING_API_IMAGE_ID=old
    RUNNING_DATABASE_IMAGE=old
    RUNNING_DATABASE_IMAGE_ID=old
}
record_deployment_state() { :; }
compose() {
    if [[ "$1" == stop ]]; then printf stopped > "$ROOT/active"; fi
    printf '%s\n' "$*"
}
run_target_api() { printf new-api-running > "$ROOT/active"; }
start_backup_scheduler() { printf 'scheduler-start\n'; }
upgrade_release upgrade target
""".replace("$2_BACKUP_RESULT", "$TEST_BACKUP_RESULT")
    result = subprocess.run(
        ["bash", "-c", program, "test-upgrade", str(entry)],
        env={
            "PATH": os.environ["PATH"],
            "TEST_BACKUP_RESULT": "success" if backup_succeeds else "failure",
        },
        text=True,
        capture_output=True,
        check=False,
    )
    assert data.read_bytes() == b"old database contents"
    if backup_succeeds:
        assert result.returncode == 0, result.stderr
        assert active.read_text() == "new-api-running"
        assert result.stdout.index("backup-old-active") < result.stdout.index(
            "stop api"
        )
        assert result.stdout.index("backup-old-active") < result.stdout.index(
            "migrator"
        )
    else:
        assert result.returncode != 0
        assert "backup-old-active" in result.stdout
        assert active.read_text() == "old-api-running"
        assert "stop api" not in result.stdout
        assert "migrator" not in result.stdout
