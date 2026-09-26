from unittest.mock import Mock
from urllib.error import HTTPError

import pytest

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
