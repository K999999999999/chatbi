from pathlib import Path
from unittest.mock import patch

from src.bootstrap import model as prepare_embedding_model
from src.rag_offline.config import DEFAULT_MODEL, DEFAULT_MODEL_REVISION


def test_prepare_downloads_the_pinned_model_revision_to_local_cache(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    model_directory = tmp_path / "bge-m3"
    monkeypatch.setenv("RAG_MODEL_DIR", str(model_directory))
    downloads = []

    def download(**kwargs) -> str:
        destination = Path(kwargs["local_dir"])
        destination.mkdir(parents=True, exist_ok=True)
        config = destination / "config.json"
        if not config.is_file():
            downloads.append(destination)
            config.write_text("{}", encoding="utf-8")
        return str(destination)

    with patch.object(
        prepare_embedding_model, "snapshot_download", side_effect=download
    ) as call:
        assert prepare_embedding_model.prepare_model() == 0
        assert prepare_embedding_model.prepare_model() == 0

    assert call.call_count == 2
    assert all(
        invocation.kwargs["repo_id"] == DEFAULT_MODEL
        and invocation.kwargs["revision"] == DEFAULT_MODEL_REVISION
        and invocation.kwargs["local_dir"] == model_directory
        for invocation in call.call_args_list
    )
    assert downloads == [model_directory]
    assert "onnx/*" in call.call_args.kwargs["ignore_patterns"]
    assert "imgs/*" in call.call_args.kwargs["ignore_patterns"]
    assert capsys.readouterr().out.count('"ready": true') == 2
