"""诊断只汇总安全状态，HTTP存活不替代ready，不进行LLM调用。"""

import json
from unittest.mock import Mock

from src.bootstrap import doctor


def test_doctor_ready_uses_existing_probes_and_reports_llm_not_probed(
    tmp_path, monkeypatch, capsys
):
    (tmp_path / "config.json").write_text("{}")
    monkeypatch.setenv("RAG_MODEL_DIR", str(tmp_path))
    monkeypatch.setattr(
        doctor,
        "ProcessReadinessProbe",
        lambda **kwargs: (
            lambda: dict.fromkeys(
                ("control_database", "business_database", "qdrant", "assets"), "ready"
            )
        ),
    )
    probe = Mock()
    monkeypatch.setattr("scripts.check_dev_qdrant._check", probe)
    monkeypatch.setattr(doctor, "http_status", lambda *args, **kwargs: "ready")
    assert doctor.main() == 0
    result = json.loads(capsys.readouterr().out)
    assert result["llm"] == "not_probed"
    assert all(value == "ready" for value in result["checks"].values())
    probe.assert_called_once()


def test_retired_app_doctor_target_is_rejected_before_probes(monkeypatch, capsys):
    probe = Mock(side_effect=AssertionError("不能访问数据库或服务"))
    monkeypatch.setenv("CHATBI_MAINTENANCE_TARGET", "app")
    monkeypatch.setattr(doctor, "ProcessReadinessProbe", probe)

    assert doctor.main() == 2
    assert "只支持 dev" in capsys.readouterr().err
    probe.assert_not_called()


def test_http_health_does_not_make_malformed_readiness_ready(monkeypatch, capsys):
    response = Mock(status=200)
    response.read.return_value = b'{"status":"unknown"}'
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=None)
    monkeypatch.setattr(doctor, "urlopen", Mock(return_value=response))
    assert doctor.http_status("http://api/health") == "ready"
    assert doctor.http_status("http://api/ready", ready=True) == "not_ready"
    monkeypatch.setattr(
        doctor, "urlopen", Mock(side_effect=RuntimeError("sensitive-error-payload"))
    )
    assert doctor.http_status("http://api/ready", ready=True) == "not_ready"
    assert "sensitive-error-payload" not in capsys.readouterr().out


def test_http_probe_refuses_non_http_schemes_without_opening(monkeypatch):
    opener = Mock(side_effect=AssertionError("non-http resource opened"))
    monkeypatch.setattr(doctor, "urlopen", opener)
    for url in ("file:///private/config", "ftp://api/config", "/private/config"):
        assert doctor.http_status(url) == "not_ready"
    opener.assert_not_called()


def test_web_probe_uses_vite_allowed_host_inside_compose(tmp_path, monkeypatch):
    (tmp_path / "config.json").write_text("{}")
    monkeypatch.setenv("RAG_MODEL_DIR", str(tmp_path))
    monkeypatch.setattr(
        doctor,
        "ProcessReadinessProbe",
        lambda **kwargs: (
            lambda: dict.fromkeys(
                ("control_database", "business_database", "qdrant", "assets"), "ready"
            )
        ),
    )
    monkeypatch.setattr("scripts.check_dev_qdrant._check", Mock())
    requests = []

    def open_request(request, *, timeout):
        requests.append(request)
        response = Mock(status=200)
        response.read.return_value = b'{"status":"ready"}'
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=None)
        return response

    monkeypatch.setattr(doctor, "urlopen", open_request)

    result = doctor.diagnose()

    web_request = next(
        request for request in requests if request.full_url == "http://web:5173"
    )
    assert web_request.get_header("Host") == "localhost"
    assert result["web"] == "ready"
