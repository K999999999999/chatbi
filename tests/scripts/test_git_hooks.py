import os
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
INSTALLER = ROOT / "scripts/install_git_hooks.sh"
HOOK = ROOT / ".githooks/pre-commit"


def git(repo: Path, *args: str, env: dict[str, str]) -> str:
    return subprocess.check_output(
        ["git", "-C", str(repo), *args], text=True, env=env
    ).strip()


@pytest.fixture
def repo(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    path = tmp_path / "repo"
    path.mkdir()
    env = os.environ.copy()
    env.update(
        {
            "GIT_CONFIG_GLOBAL": str(tmp_path / "global.config"),
            "GIT_CONFIG_SYSTEM": str(tmp_path / "system.config"),
            "GIT_CONFIG_NOSYSTEM": "0",
        }
    )
    Path(env["GIT_CONFIG_GLOBAL"]).touch()
    Path(env["GIT_CONFIG_SYSTEM"]).touch()
    git(path, "init", "-b", "master", env=env)
    git(
        path,
        "-c",
        "user.name=Harness test",
        "-c",
        "user.email=test@example.invalid",
        "commit",
        "--allow-empty",
        "-m",
        "baseline",
        env=env,
    )
    return path, env


def install(repo: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    copy_hook(repo)
    return subprocess.run(
        ["bash", str(INSTALLER)],
        cwd=repo,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def set_config(path: Path, scope: str, value: str, env: dict[str, str]) -> None:
    args = ["git", "-C", str(path), "config", f"--{scope}", "core.hooksPath", value]
    subprocess.run(args, env=env, check=True, capture_output=True, text=True)


def stage_file(repo: Path, env: dict[str, str]) -> None:
    (repo / "change.txt").write_text("change\n", encoding="utf-8")
    git(repo, "add", "change.txt", env=env)


def copy_hook(repo: Path) -> None:
    hooks = repo / ".githooks"
    hooks.mkdir(exist_ok=True)
    destination = hooks / "pre-commit"
    shutil.copy2(HOOK, destination)
    destination.chmod(destination.stat().st_mode | 0o111)


def commit(repo: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "-c",
            "user.name=Harness test",
            "-c",
            "user.email=test@example.invalid",
            "commit",
            "-m",
            "change",
        ],
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_installer_sets_local_path_and_is_idempotent(
    repo: tuple[Path, dict[str, str]],
) -> None:
    path, env = repo
    first = install(path, env)
    second = install(path, env)
    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr
    assert (
        git(path, "config", "--local", "--get", "core.hooksPath", env=env)
        == ".githooks"
    )


@pytest.mark.parametrize("scope", ["global", "system", "local", "worktree"])
def test_installer_preserves_existing_custom_path(
    repo: tuple[Path, dict[str, str]], scope: str
) -> None:
    path, env = repo
    if scope == "worktree":
        git(path, "config", "extensions.worktreeConfig", "true", env=env)
    set_config(path, scope, "custom-hooks", env)
    before = git(
        path, "config", "--show-origin", "--get-all", "core.hooksPath", env=env
    )
    result = install(path, env)
    after = git(path, "config", "--show-origin", "--get-all", "core.hooksPath", env=env)
    assert result.returncode != 0
    assert "既有 core.hooksPath" in result.stderr
    assert before == after
    local_config = subprocess.run(
        ["git", "-C", str(path), "config", "--local", "--get", "core.hooksPath"],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if scope == "local":
        assert local_config.stdout.strip() == "custom-hooks"
    else:
        assert local_config.returncode != 0


def test_installer_preserves_command_scoped_path(
    repo: tuple[Path, dict[str, str]],
) -> None:
    path, env = repo
    env.update(
        {
            "GIT_CONFIG_COUNT": "1",
            "GIT_CONFIG_KEY_0": "core.hooksPath",
            "GIT_CONFIG_VALUE_0": "custom-hooks",
        }
    )
    result = install(path, env)
    assert result.returncode != 0
    assert "既有 core.hooksPath" in result.stderr
    local_config = subprocess.run(
        ["git", "-C", str(path), "config", "--local", "--get", "core.hooksPath"],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert local_config.returncode != 0


def test_installer_persists_command_scoped_target_path(
    repo: tuple[Path, dict[str, str]],
) -> None:
    path, env = repo
    env.update(
        {
            "GIT_CONFIG_COUNT": "1",
            "GIT_CONFIG_KEY_0": "core.hooksPath",
            "GIT_CONFIG_VALUE_0": ".githooks",
        }
    )
    result = install(path, env)
    assert result.returncode == 0, result.stderr
    assert (
        git(path, "config", "--local", "--get", "core.hooksPath", env=env)
        == ".githooks"
    )


def test_installer_accepts_existing_target_path(
    repo: tuple[Path, dict[str, str]],
) -> None:
    path, env = repo
    set_config(path, "global", ".githooks", env)
    result = install(path, env)
    assert result.returncode == 0, result.stderr
    assert (
        subprocess.run(
            ["git", "-C", str(path), "config", "--local", "--get", "core.hooksPath"],
            env=env,
            capture_output=True,
            text=True,
            check=False,
        ).returncode
        != 0
    )


def test_installer_rejects_conflicting_values(
    repo: tuple[Path, dict[str, str]],
) -> None:
    path, env = repo
    subprocess.run(
        [
            "git",
            "-C",
            str(path),
            "config",
            "--global",
            "--add",
            "core.hooksPath",
            ".githooks",
        ],
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        [
            "git",
            "-C",
            str(path),
            "config",
            "--global",
            "--add",
            "core.hooksPath",
            "other-hooks",
        ],
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    before = git(
        path, "config", "--show-origin", "--get-all", "core.hooksPath", env=env
    )
    result = install(path, env)
    after = git(path, "config", "--show-origin", "--get-all", "core.hooksPath", env=env)
    assert result.returncode != 0
    assert before == after


def test_hook_rejects_master_and_detached_head(
    repo: tuple[Path, dict[str, str]],
) -> None:
    path, env = repo
    copy_hook(path)
    set_config(path, "local", ".githooks", env)
    stage_file(path, env)
    master_commit = commit(path, env)
    assert master_commit.returncode != 0
    assert "命名 Feature branch" in master_commit.stderr

    git(path, "switch", "--detach", "HEAD", env=env)
    detached_commit = commit(path, env)
    assert detached_commit.returncode != 0
    assert "命名 Feature branch" in detached_commit.stderr


def test_hook_allows_feature_branch(repo: tuple[Path, dict[str, str]]) -> None:
    path, env = repo
    copy_hook(path)
    set_config(path, "local", ".githooks", env)
    git(path, "switch", "-c", "docs/example", env=env)
    stage_file(path, env)
    result = commit(path, env)
    assert result.returncode == 0, result.stderr


def test_hook_is_executable_in_repository() -> None:
    assert HOOK.exists()
    assert os.access(HOOK, os.X_OK)
