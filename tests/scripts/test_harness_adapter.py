from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


REPOSITORY = Path(__file__).resolve().parents[2]
PLUGIN_FIXTURE = REPOSITORY / "tests/fixtures/harness-plugin"
WORK_ITEM = "adapter-fixture"


def git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


def fixture_repo(parent: Path) -> Path:
    repo = parent / "chatbi-fixture"
    repo.mkdir()
    (repo / "scripts").mkdir()
    (repo / ".harness").mkdir()
    for relative in (
        "dev",
        "scripts/container_tasks.sh",
        "scripts/dev_environment.sh",
        "scripts/harness_container_adapter.sh",
        "scripts/harness_control.py",
        "scripts/check_harness_state.py",
        ".harness/project.json",
        ".harness/dynamic-files.json",
    ):
        target = repo / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPOSITORY / relative, target)
    subprocess.run(
        ["git", "-C", str(repo), "init", "-b", "master"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(repo), "add", "dev", "scripts", ".harness"], check=True
    )
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "-c",
            "user.name=Harness fixture",
            "-c",
            "user.email=harness@example.invalid",
            "commit",
            "-m",
            "fixture",
        ],
        check=True,
        capture_output=True,
    )
    common = Path(git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir"))
    status_dir = common / "harness/work-items" / WORK_ITEM
    status_dir.mkdir(parents=True)
    (status_dir / "status.md").write_text(
        f"# 状态\nID: {WORK_ITEM}\nStatus: in-progress\nStage: 实施中\nNext: fixture\n",
        encoding="utf-8",
    )
    return repo


def adapter_env(
    tmp_path: Path, *, image_missing: bool = False
) -> tuple[dict[str, str], Path]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    docker_log = tmp_path / "docker-args.log"
    docker = bin_dir / "docker"
    docker.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        'printf "%s\\0" "$@" >> "$HARNESS_ADAPTER_TEST_DOCKER_LOG"\n'
        'printf "\\n" >> "$HARNESS_ADAPTER_TEST_DOCKER_LOG"\n'
        "if [[ ${1:-} == image && ${HARNESS_ADAPTER_TEST_IMAGE_MISSING:-false} == true ]]; then exit 1; fi\n"
        'if [[ ${1:-} == image ]]; then printf "sha256:fixture\\n"; fi\n'
        'if [[ ${1:-} == run ]]; then exit "${HARNESS_ADAPTER_TEST_RUN_EXIT:-0}"; fi\n',
        encoding="utf-8",
    )
    docker.chmod(0o755)
    env = os.environ.copy()
    for name in (
        "LOCAL_WORKSPACE_FOLDER",
        "CHATBI_GIT_COMMON_DIR_HOST",
        "CHATBI_ENGINEERING_WORKFLOW_SOURCE_ROOT",
    ):
        env.pop(name, None)
    env["PATH"] = f"{bin_dir}{os.pathsep}{env['PATH']}"
    env["HARNESS_ADAPTER_TEST_DOCKER_LOG"] = str(docker_log)
    env["CHATBI_DEV_PYTHON_IMAGE"] = "fixture-python:local"
    env["CHATBI_DEV_ENV_FILE"] = str(tmp_path / "must-not-read.env")
    if image_missing:
        env["HARNESS_ADAPTER_TEST_IMAGE_MISSING"] = "true"
    return env, docker_log


def calls(log: Path) -> list[list[str]]:
    if not log.exists():
        return []
    result = []
    for part in log.read_bytes().split(b"\n"):
        if not part:
            continue
        argv = part.decode().split("\0")
        if argv[-1] == "":
            argv.pop()
        result.append(argv)
    return result


def run_dev(
    repo: Path, env: dict[str, str], *args: str
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(repo / "dev"), *args],
        cwd=repo,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_read_only_control_uses_fixture_source_and_read_only_mounts(
    tmp_path: Path,
) -> None:
    repo = fixture_repo(tmp_path)
    env, log = adapter_env(tmp_path)

    result = run_dev(
        repo,
        env,
        "harness",
        "control",
        "--plugin-source",
        str(PLUGIN_FIXTURE),
        "state",
        "--work-item",
        WORK_ITEM,
        "--json",
    )

    assert result.returncode == 0, result.stderr
    assert "不证明该包已安装或已加载到当前会话" in result.stderr
    recorded = calls(log)
    assert len(recorded) == 2
    run = recorded[1]
    assert run[0] == "run"
    assert "--network" in run and run[run.index("--network") + 1] == "none"
    assert "--read-only" in run
    assert f"type=bind,src={repo},dst={repo},readonly" in run
    plugin_root = PLUGIN_FIXTURE / "plugins/engineering-workflow"
    assert f"type=bind,src={plugin_root},dst=/opt/engineering-workflow,readonly" in run
    common = git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir")
    assert f"type=bind,src={common},dst={common},readonly" in run
    assert not any(
        value.startswith("type=bind,") and not value.endswith(",readonly")
        for value in run
    )
    assert "/var/run/docker.sock" not in run
    assert str(tmp_path / "must-not-read.env") not in run
    assert run[run.index("--entrypoint") + 1] == "python"
    assert run[run.index("--entrypoint") + 3 :] == [
        "-m",
        "scripts.harness_control",
        "--plugin-root",
        "/opt/engineering-workflow",
        "--project-root",
        str(repo),
        "--adapter",
        str(repo / ".harness/project.json"),
        "state",
        "--work-item",
        WORK_ITEM,
        "--json",
    ]


def test_harness_check_mounts_other_registered_worktrees_read_only(
    tmp_path: Path,
) -> None:
    repo = fixture_repo(tmp_path)
    linked = tmp_path / "another checkout"
    git(repo, "worktree", "add", "-b", "fix/other", str(linked))
    env, log = adapter_env(tmp_path)
    result = run_dev(repo, env, "harness", "check", "--json")
    assert result.returncode == 0, result.stderr
    run = calls(log)[0]
    assert f"type=bind,src={linked},dst={linked},readonly" in run


def test_missing_host_workspace_is_refused_before_any_docker_call(
    tmp_path: Path,
) -> None:
    repo = fixture_repo(tmp_path)
    env, log = adapter_env(tmp_path)
    missing = tmp_path / "removed-worktree"
    env["LOCAL_WORKSPACE_FOLDER"] = str(missing)
    result = run_dev(
        repo,
        env,
        "harness",
        "control",
        "--plugin-source",
        str(PLUGIN_FIXTURE),
        "state",
        "--work-item",
        WORK_ITEM,
    )
    assert result.returncode == 2
    assert not missing.exists()
    assert not log.exists()
    assert "bind source" in result.stderr


def test_write_mount_is_limited_to_existing_work_item_and_linked_common_dir(
    tmp_path: Path,
) -> None:
    primary = fixture_repo(tmp_path)
    linked = tmp_path / "linked-chatbi"
    subprocess.run(
        [
            "git",
            "-C",
            str(primary),
            "worktree",
            "add",
            "-b",
            "linked-fixture",
            str(linked),
        ],
        check=True,
        capture_output=True,
    )
    env, log = adapter_env(tmp_path)

    result = run_dev(
        linked,
        env,
        "harness",
        "control",
        "--plugin-source",
        str(PLUGIN_FIXTURE),
        "migrate",
        "--work-item",
        WORK_ITEM,
        "--expected-sha",
        "0" * 64,
    )

    assert result.returncode == 0, result.stderr
    run = calls(log)[1]
    common = git(linked, "rev-parse", "--path-format=absolute", "--git-common-dir")
    item_dir = Path(common) / "harness/work-items" / WORK_ITEM
    assert f"type=bind,src={common},dst={common},readonly" in run
    assert f"type=bind,src={item_dir},dst={item_dir}" in run
    writable_mounts = [
        arg
        for arg in run
        if arg.startswith("type=bind,") and not arg.endswith(",readonly")
    ]
    assert writable_mounts == [f"type=bind,src={item_dir},dst={item_dir}"]
    assert f"type=bind,src={linked},dst={linked},readonly" in run


def test_cancel_uses_the_existing_work_item_only_write_mount(tmp_path: Path) -> None:
    repo = fixture_repo(tmp_path)
    env, log = adapter_env(tmp_path)

    result = run_dev(
        repo,
        env,
        "harness",
        "control",
        "--plugin-source",
        str(PLUGIN_FIXTURE),
        "cancel",
        "--work-item",
        WORK_ITEM,
        "--reason",
        "user stopped work",
        "--confirmed-by",
        "user session",
        "--expected-sha",
        "0" * 64,
    )

    assert result.returncode == 0, result.stderr
    run = calls(log)[1]
    common = git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir")
    item_dir = Path(common) / "harness/work-items" / WORK_ITEM
    assert f"type=bind,src={common},dst={common},readonly" in run
    assert f"type=bind,src={item_dir},dst={item_dir}" in run
    writable_mounts = [
        arg
        for arg in run
        if arg.startswith("type=bind,") and not arg.endswith(",readonly")
    ]
    assert writable_mounts == [f"type=bind,src={item_dir},dst={item_dir}"]


def test_plugin_package_root_is_accepted_but_package_without_cli_fails_closed(
    tmp_path: Path,
) -> None:
    repo = fixture_repo(tmp_path)
    env, log = adapter_env(tmp_path)
    package_root = PLUGIN_FIXTURE / "plugins/engineering-workflow"

    result = run_dev(
        repo,
        env,
        "harness",
        "control",
        "--plugin-source",
        str(package_root),
        "state",
        "--work-item",
        WORK_ITEM,
    )

    assert result.returncode == 0, result.stderr
    assert (
        f"type=bind,src={package_root},dst=/opt/engineering-workflow,readonly"
        in calls(log)[1]
    )

    incomplete = tmp_path / "incomplete-package"
    shutil.copytree(package_root, incomplete)
    shutil.rmtree(incomplete / "tools")
    failed_env, failed_log = adapter_env(tmp_path / "missing-cli")
    failed = run_dev(
        repo,
        failed_env,
        "harness",
        "control",
        "--plugin-source",
        str(incomplete),
        "state",
        "--work-item",
        WORK_ITEM,
    )
    assert failed.returncode == 2
    assert "未包含 Harness CLI" in failed.stderr
    assert calls(failed_log) == []


@pytest.mark.parametrize(
    ("arguments", "expected"),
    [
        (
            ("harness", "control", "state", "--work-item", WORK_ITEM),
            "未指定 Plugin 源码根目录",
        ),
        (
            (
                "harness",
                "control",
                "--plugin-source",
                str(PLUGIN_FIXTURE),
                "state",
                "--adapter",
                "tests/fixtures/other.json",
                "--work-item",
                WORK_ITEM,
            ),
            "项目适配文件由适配器固定",
        ),
        (
            ("harness", "control", "--plugin-source", "/missing/plugin", "state"),
            "Plugin 源码路径不存在",
        ),
        (
            (
                "harness",
                "control",
                "--plugin-source",
                str(PLUGIN_FIXTURE),
                "onboard",
                "apply",
            ),
            "只允许写 Harness 状态目录",
        ),
        (
            (
                "harness",
                "control",
                "--plugin-source",
                str(PLUGIN_FIXTURE),
                "migrate",
                "--expected-sha",
                "0" * 64,
            ),
            "状态写入必须指定有效的 --work-item",
        ),
    ],
)
def test_invalid_or_unsupported_requests_fail_without_invoking_docker(
    tmp_path: Path, arguments: tuple[str, ...], expected: str
) -> None:
    repo = fixture_repo(tmp_path)
    env, log = adapter_env(tmp_path)

    result = run_dev(repo, env, *arguments)

    assert result.returncode == 2
    assert expected in result.stderr
    assert calls(log) == []


def test_bad_plugin_identity_and_missing_image_fail_without_legacy_fallback(
    tmp_path: Path,
) -> None:
    repo = fixture_repo(tmp_path)
    env, log = adapter_env(tmp_path)
    bad_source = tmp_path / "bad-plugin"
    shutil.copytree(PLUGIN_FIXTURE, bad_source)
    metadata = bad_source / "plugins/engineering-workflow/.codex-plugin/plugin.json"
    metadata.write_text('{"name": "different-plugin"}\n', encoding="utf-8")

    bad_plugin = run_dev(
        repo, env, "harness", "control", "--plugin-source", str(bad_source), "state"
    )
    assert bad_plugin.returncode == 2
    assert "元数据名称不匹配" in bad_plugin.stderr
    assert calls(log) == []

    missing_env, missing_log = adapter_env(
        tmp_path / "missing-image", image_missing=True
    )
    missing_image = run_dev(
        repo,
        missing_env,
        "harness",
        "control",
        "--plugin-source",
        str(PLUGIN_FIXTURE),
        "state",
    )
    assert missing_image.returncode == 2
    assert "没有联网安装，也没有回退到旧工具" in missing_image.stderr
    assert len(calls(missing_log)) == 1


def test_legacy_harness_check_still_calls_existing_read_only_module(
    tmp_path: Path,
) -> None:
    repo = fixture_repo(tmp_path)
    env, log = adapter_env(tmp_path)

    result = run_dev(repo, env, "harness", "check", "--repo", str(repo), "--json")

    assert result.returncode == 0, result.stderr
    assert "只读 Plugin 源码工作树" not in result.stderr
    run = calls(log)[0]
    assert run[run.index("--entrypoint") + 1] == "python"
    assert run[-5:] == [
        "-m",
        "scripts.check_harness_state",
        "--repo",
        str(repo),
        "--json",
    ]


def test_legacy_python_state_checker_remains_available_and_read_only(
    tmp_path: Path,
) -> None:
    repo = fixture_repo(tmp_path)
    common = Path(git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir"))
    shutil.rmtree(common / "harness")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.check_harness_state",
            "--repo",
            str(repo),
            "--json",
        ],
        cwd=REPOSITORY,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["records"] == 0
    assert any(item["code"] == "LOCAL_RECORDS_ABSENT" for item in report["findings"])


def test_project_profile_and_dynamic_manifest_reference_existing_authority(
    tmp_path: Path,
) -> None:
    adapter = json.loads(
        (REPOSITORY / ".harness/project.json").read_text(encoding="utf-8")
    )
    manifest_path = REPOSITORY / adapter["dynamic_file_manifest"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert adapter["repository"] == "github.com/K999999999999/chatbi"
    assert adapter["work_item_record_directory"] == "harness/work-items"
    assert "实施中" in adapter["workflow"]["stages"]
    assert any(
        edge["from"] == "实施中" and edge["to"] == "验证 / Review"
        for edge in adapter["workflow"]["transitions"]
    )
    assert manifest["delivery_required"] is True
    for item in manifest["files"]:
        assert (REPOSITORY / item["path"]).is_file()
        assert (REPOSITORY / item["history_path"]).is_file()
        assert item["triggers"]
