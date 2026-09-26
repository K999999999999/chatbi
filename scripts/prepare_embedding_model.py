"""Download the pinned BGE-M3 snapshot into the ignored local model cache."""

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from huggingface_hub import snapshot_download

from src.rag_offline.config import (
    DEFAULT_MODEL,
    DEFAULT_MODEL_DIR,
    DEFAULT_MODEL_REVISION,
    PROJECT_ROOT,
)


def _model_directory() -> Path:
    configured = os.getenv("RAG_MODEL_DIR", "").strip()
    if not configured:
        return DEFAULT_MODEL_DIR
    path = Path(configured)
    return path if path.is_absolute() else PROJECT_ROOT / path


def main() -> int:
    load_dotenv(override=False)
    destination = _model_directory()
    try:
        resolved = snapshot_download(
            repo_id=DEFAULT_MODEL,
            revision=DEFAULT_MODEL_REVISION,
            local_dir=destination,
            ignore_patterns=[
                "flax_model.msgpack",
                "rust_model.ot",
                "tf_model.h5",
                "onnx/*",
                "imgs/*",
            ],
        )
    except Exception as error:  # noqa: BLE001 - CLI reports without credentials
        print(
            "Embedding 模型下载失败。检查 Hugging Face 网络访问和本地磁盘空间；"
            f"错误类型：{type(error).__name__}",
            file=sys.stderr,
        )
        return 1

    print(
        json.dumps(
            {
                "model": DEFAULT_MODEL,
                "revision": DEFAULT_MODEL_REVISION,
                "cache_path": str(resolved),
                "ready": (destination / "config.json").is_file(),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if (destination / "config.json").is_file() else 1


if __name__ == "__main__":
    raise SystemExit(main())
