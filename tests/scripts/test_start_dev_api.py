"""容器启动时依赖延迟与失败的确定性回归；不访问真实数据库。"""

from unittest.mock import Mock

import pytest

from scripts import start_dev_api


def test_control_database_can_become_ready_after_unknown_and_failure(monkeypatch):
    probe = Mock(
        side_effect=[
            {"control_database": "unknown"},
            {"control_database": "not_ready"},
            {"control_database": "ready"},
        ]
    )
    monkeypatch.setattr(start_dev_api, "ProcessReadinessProbe", lambda: probe)
    monkeypatch.setattr("time.sleep", lambda _: None)
    assert start_dev_api.wait_for_control_database() is True


def test_startup_timeout_does_not_launch_api_or_expose_probe_details(
    monkeypatch, capsys
):
    probe = Mock(return_value={"control_database": "not_ready"})
    monkeypatch.setattr(start_dev_api, "ProcessReadinessProbe", lambda: probe)
    clock = iter((0, 0, 121))
    monkeypatch.setattr("time.monotonic", lambda: next(clock))
    monkeypatch.setattr("time.sleep", lambda _: None)
    launch = Mock()
    monkeypatch.setattr("os.execvp", launch)
    assert start_dev_api.main() == 1
    launch.assert_not_called()
    assert "控制库" in capsys.readouterr().err


def test_ready_database_launches_api_with_hot_reload(monkeypatch):
    probe = Mock(return_value={"control_database": "ready"})
    monkeypatch.setattr(start_dev_api, "ProcessReadinessProbe", lambda: probe)
    launch = Mock(side_effect=RuntimeError("exec replaced the process"))
    monkeypatch.setattr("os.execvp", launch)
    with pytest.raises(RuntimeError, match="exec replaced the process"):
        start_dev_api.main()
    executable, args = launch.call_args.args
    assert executable == "uvicorn"
    assert args[:2] == ["uvicorn", "src.query_api.main:app"]
    assert "--reload" in args
    assert "/workspace/src" in args and "/workspace/scripts" in args
