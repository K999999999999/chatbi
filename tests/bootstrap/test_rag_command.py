"""RAG 命令重组保持参数、发布结果和临时资源释放。"""

from argparse import Namespace
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from src.bootstrap import rag
from src.rag_offline.config import OfflineBuildConfig


@pytest.fixture
def rag_command(monkeypatch, tmp_path):
    config = OfflineBuildConfig(output_dir=tmp_path)
    store = Mock()
    builder = Mock()
    monkeypatch.setattr(rag.OfflineBuildConfig, "from_environment", lambda: config)
    monkeypatch.setattr(rag, "BgeM3EmbeddingProvider", Mock())
    monkeypatch.setattr(rag.QdrantAssetStore, "connect", lambda **_: store)
    monkeypatch.setattr(rag, "build_offline_assets", builder)
    return store, builder


@pytest.mark.parametrize("published,exit_code", [(True, 0), (False, 1)])
def test_rag_command_reports_publication_and_releases_store(
    rag_command, published, exit_code, capsys
):
    store, builder = rag_command
    builder.return_value = SimpleNamespace(
        published=published, to_dict=lambda: {"published": published}
    )
    args = Namespace(
        structure_dir=None, metrics_path=None, output_dir=None, build_id="candidate"
    )
    assert rag.build_rag(args) == exit_code
    assert builder.call_args.kwargs["build_id"] == "candidate"
    assert '"published"' in capsys.readouterr().out
    store.close.assert_called_once()


def test_rag_command_preserves_original_failure_when_close_fails(rag_command, caplog):
    store, builder = rag_command
    builder.side_effect = RuntimeError("test build failure")
    store.close.side_effect = RuntimeError("sensitive-cleanup-text")
    args = Namespace(
        structure_dir=None, metrics_path=None, output_dir=None, build_id=None
    )
    with pytest.raises(RuntimeError, match="test build failure"):
        rag.build_rag(args)
    store.close.assert_called_once()
    assert "sensitive-cleanup-text" not in caplog.text
