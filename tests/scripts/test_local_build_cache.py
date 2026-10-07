from __future__ import annotations

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CACHE_HELPER = ROOT / "scripts" / "local_build_cache.sh"


def make_commit(repository: Path, filename: str, content: str, message: str) -> str:
    (repository / filename).write_text(content, encoding="utf-8")
    subprocess.run(["git", "-C", str(repository), "add", filename], check=True)
    subprocess.run(
        ["git", "-C", str(repository), "commit", "-m", message],
        check=True,
        capture_output=True,
        text=True,
    )
    return subprocess.run(
        ["git", "-C", str(repository), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def run_cache_selector(
    repository: Path,
    current_commit: str,
    base_commit: str,
    *,
    current_cache_commit: str = "",
) -> subprocess.CompletedProcess[str]:
    script = r'''
set -Eeuo pipefail
source "$1"
repository="$2"
current_commit="$3"
docker() {
    if [[ "$1" == image && "$2" == ls ]]; then
        printf '%s\n' 'chatbi-local-api:new' 'chatbi-local-api:old'
    elif [[ "$1" == image && "$2" == inspect ]]; then
        case "$4" in
            *com.chatbi.build-cache-commit*)
                if [[ "$5" == *:new ]]; then printf '%s\n' "$CURRENT_CACHE_COMMIT"; else printf '<no value>\n'; fi
                ;;
            *org.opencontainers.image.revision*)
                if [[ "$5" == *:new ]]; then printf '%s\n' "$CURRENT_COMMIT"; else printf '%s\n' "$BASE_COMMIT"; fi
                ;;
        esac
    fi
}
select_build_cache_commit "$current_commit" "$repository"
'''
    environment = os.environ | {
        "CURRENT_COMMIT": current_commit,
        "BASE_COMMIT": base_commit,
        "CURRENT_CACHE_COMMIT": current_cache_commit,
    }
    return subprocess.run(
        [
            "bash",
            "-c",
            script,
            "test-build-cache",
            str(CACHE_HELPER),
            str(repository),
            current_commit,
        ],
        capture_output=True,
        check=False,
        text=True,
        env=environment,
    )


def make_repository(path: Path) -> tuple[str, str]:
    subprocess.run(["git", "init", "--quiet", str(path)], check=True)
    subprocess.run(
        ["git", "-C", str(path), "config", "user.name", "Test"], check=True
    )
    subprocess.run(
        ["git", "-C", str(path), "config", "user.email", "test@example.invalid"],
        check=True,
    )
    base_commit = make_commit(path, "base.txt", "base\n", "base")
    current_commit = make_commit(path, "next.txt", "next\n", "next")
    return base_commit, current_commit


def test_uses_the_recorded_layer_cache_commit_not_image_revision(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repo"
    repository.mkdir()
    base_commit, current_commit = make_repository(repository)

    result = run_cache_selector(
        repository,
        current_commit,
        base_commit,
        current_cache_commit=base_commit,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == base_commit, (
        "the cache key must come from the layer-cache label, not the newer "
        f"image revision; expected {base_commit}, got {result.stdout.strip()}"
    )


def test_legacy_images_fall_back_to_the_oldest_cached_ancestor(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repo"
    repository.mkdir()
    base_commit, current_commit = make_repository(repository)

    result = run_cache_selector(repository, current_commit, base_commit)

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == base_commit, (
        "legacy images lack a layer-cache label; select the oldest cached "
        f"ancestor, expected {base_commit}, got {result.stdout.strip()}"
    )
