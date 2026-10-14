"""诊断只汇总安全状态，HTTP存活不替代ready，不进行LLM调用。"""

import json
from unittest.mock import Mock

from src.bootstrap import doctor


def test_doctor_ready_uses_existing_probes_and_reports_llm_not_probed(
    tmp_path, monkeypatch, capsys
):
    (tmp_path / "config.json").write_text("{}")
    monkeypatch.setenv("RAG_MODEL_DIR", str(tmp_path))
    monkeypatch.setenv("CHATBI_MAINTENANCE_TARGET", "dev")
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
