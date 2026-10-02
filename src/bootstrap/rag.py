"""RAG Offline Build 命令行入口。"""

import json
from argparse import Namespace
from contextlib import ExitStack

from src.rag_offline.build import build_offline_assets
from src.rag_offline.config import OfflineBuildConfig
from src.rag_offline.embedding import BgeM3EmbeddingProvider
from src.rag_offline.qdrant_store import QdrantAssetStore

from .lifecycle import register_cleanup


def build_rag(args: Namespace) -> int:
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
    with ExitStack() as resources:
        register_cleanup(resources, "rag_build_store", store.close)
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

    print(json.dumps(summary.to_dict(), ensure_ascii=False, indent=2))
    return 0 if summary.published else 1
