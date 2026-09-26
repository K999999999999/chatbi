"""RAG Offline Build 命令行入口。"""

import argparse
import json
from pathlib import Path

from dotenv import load_dotenv

from .build import build_offline_assets
from .config import OfflineBuildConfig
from .embedding import BgeM3EmbeddingProvider
from .qdrant_store import QdrantAssetStore


def main() -> int:
    parser = argparse.ArgumentParser(description="构建 ChatBI RAG Offline 资产")
    parser.add_argument("--structure-dir", type=Path)
    parser.add_argument("--metrics-path", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--build-id")
    args = parser.parse_args()

    load_dotenv(override=False)
    settings = OfflineBuildConfig.from_environment()
    structure_dir = args.structure_dir or None
    metrics_path = args.metrics_path or None
    output_dir = args.output_dir or settings.output_dir

    embedding = BgeM3EmbeddingProvider(
        settings.model_name_or_path,
        batch_size=settings.embedding_batch_size,
        use_fp16=settings.embedding_use_fp16,
        devices=settings.embedding_device,
        model_revision=settings.model_revision,
    )
    store = QdrantAssetStore.connect(
        url=settings.qdrant_url,
        path=str(settings.qdrant_path) if settings.qdrant_path else None,
        api_key=settings.qdrant_api_key,
        timeout=settings.qdrant_timeout_seconds,
    )
    try:
        kwargs = {
            "embedding": embedding,
            "store": store,
            "output_dir": output_dir,
            "collection_prefix": settings.collection_prefix,
            "expected_dimension": settings.embedding_dimension,
            "build_id": args.build_id,
        }
        if structure_dir is not None:
            kwargs["structure_dir"] = structure_dir
        if metrics_path is not None:
            kwargs["metrics_path"] = metrics_path
        summary = build_offline_assets(**kwargs)
    finally:
        store.close()

    print(json.dumps(summary.to_dict(), ensure_ascii=False, indent=2))
    return 0 if summary.published else 1


if __name__ == "__main__":
    raise SystemExit(main())
