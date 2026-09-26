from pathlib import Path
from unittest.mock import patch

from scripts import prepare_embedding_model
from src.rag_offline.config import DEFAULT_MODEL, DEFAULT_MODEL_REVISION


def test_prepare_downloads_the_pinned_model_revision_to_local_cache(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    model_directory = tmp_path / "bge-m3"
    monkeypatch.setenv("RAG_MODEL_DIR", str(model_directory))
    monkeypatch.setattr(prepare_embedding_model, "load_dotenv", lambda **_: None)

    def download(**kwargs) -> str:
        destination = Path(kwargs["local_dir"])
        destination.mkdir(parents=True)
        (destination / "config.json").write_text("{}", encoding="utf-8")
        return str(destination)

    with patch.object(
        prepare_embedding_model, "snapshot_download", side_effect=download
    ) as call:
        assert prepare_embedding_model.main() == 0

    assert call.call_args.kwargs["repo_id"] == DEFAULT_MODEL
    assert call.call_args.kwargs["revision"] == DEFAULT_MODEL_REVISION
    assert call.call_args.kwargs["local_dir"] == model_directory
    assert "onnx/*" in call.call_args.kwargs["ignore_patterns"]
    assert "imgs/*" in call.call_args.kwargs["ignore_patterns"]
    assert '"ready": true' in capsys.readouterr().out
