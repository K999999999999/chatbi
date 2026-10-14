"""质量入口使用私有可写缓存并保持CI退出码。"""

from pathlib import Path

from scripts import python_quality


def test_quality_cache_is_private_temporary_and_removed_after_command(monkeypatch):
    observed = []

    def run(command, *, cwd, env):
        assert command == ["bash", "scripts/check_python_quality.sh"]
        assert cwd == Path(python_quality.__file__).resolve().parents[1]
        uv_cache, ruff_cache = Path(env["UV_CACHE_DIR"]), Path(env["RUFF_CACHE_DIR"])
        assert uv_cache.parent == ruff_cache.parent
        assert uv_cache.parent.is_dir()
        assert uv_cache.parent.stat().st_mode & 0o077 == 0
        observed.append(uv_cache.parent)
        return 37

    monkeypatch.setattr(python_quality.subprocess, "call", run)
    assert python_quality.main() == 37
    assert len(observed) == 1
    assert not observed[0].exists()
