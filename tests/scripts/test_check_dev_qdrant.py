from unittest.mock import Mock
from urllib.error import HTTPError

import pytest

from scripts import check_dev_qdrant
from scripts.check_dev_qdrant import _check


def test_health_check_sends_the_api_key_header() -> None:
    response = Mock(status=200)
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    opener = Mock(return_value=response)

    _check("http://127.0.0.1:6333/", "local-api-key", opener=opener)

    request = opener.call_args.args[0]
    assert request.full_url == "http://127.0.0.1:6333/healthz"
    assert request.get_header("Api-key") == "local-api-key"


def test_health_check_rejects_an_invalid_key() -> None:
    opener = Mock(
        side_effect=HTTPError(
            "http://127.0.0.1:6333/healthz",
            401,
            "unauthorized",
            {},
            None,
        )
    )

    with pytest.raises(HTTPError):
        _check("http://127.0.0.1:6333", "wrong-key", opener=opener)


def test_unsafe_environment_file_is_rejected_without_reading_or_network_call(
    tmp_path, monkeypatch, capsys
):
    env_file = tmp_path / ".env"
    env_file.write_text("QDRANT_API_KEY=QDRANT_PERMISSION_CANARY\n")
    env_file.chmod(0o644)
    monkeypatch.setenv("CHATBI_DEV_ENV_FILE", str(env_file))
    monkeypatch.delenv("QDRANT_API_KEY", raising=False)
    monkeypatch.delenv("RAG_QDRANT_URL", raising=False)
    monkeypatch.setattr(
        check_dev_qdrant,
        "_check",
        lambda *_args: pytest.fail("不安全配置不能进入网络检查"),
    )

    assert check_dev_qdrant.main() == 2

    captured = capsys.readouterr()
    assert "chmod 600" in captured.err
    assert "QDRANT_PERMISSION_CANARY" not in captured.out + captured.err
