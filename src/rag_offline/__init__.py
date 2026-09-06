"""RAG Offline Build（RAG 离线构建）模块公共入口。"""

from .build import (
    BuildSummary,
    PublishedAsset,
    PublishedAssetError,
    build_offline_assets,
    load_published_asset,
)
from .config import (
    DEFAULT_ASSET_DIR,
    OfflineBuildConfig,
    OfflineBuildConfigError,
)
from .documents import (
    COLUMN_COLLECTION,
    METRIC_COLLECTION,
    TABLE_COLLECTION,
    RetrievalDocument,
    build_documents,
)
from .embedding import (
    BgeM3EmbeddingProvider,
    EmbeddedText,
    EmbeddingError,
    EmbeddingProvider,
    SparseEmbedding,
)
from .evaluation import (
    RetrievalCase,
    RetrievalCaseResult,
    RetrievalEvaluationError,
    RetrievalEvaluationSummary,
    default_retrieval_cases,
    evaluate_retrieval,
)
from .qdrant_store import QdrantAssetStore, QdrantStoreError, SearchHit
from .relationships import (
    RelationshipGraph,
    RelationshipGraphError,
    build_relationship_graph,
)
from .sources import (
    DEFAULT_METRICS_PATH,
    DEFAULT_STRUCTURE_DIR,
    Facts,
    SourceLoadError,
    load_facts,
)

__all__ = [
    "BgeM3EmbeddingProvider",
    "BuildSummary",
    "COLUMN_COLLECTION",
    "DEFAULT_ASSET_DIR",
    "DEFAULT_METRICS_PATH",
    "DEFAULT_STRUCTURE_DIR",
    "EmbeddedText",
    "EmbeddingError",
    "EmbeddingProvider",
    "Facts",
    "METRIC_COLLECTION",
    "OfflineBuildConfig",
    "OfflineBuildConfigError",
    "PublishedAsset",
    "PublishedAssetError",
    "QdrantAssetStore",
    "QdrantStoreError",
    "RelationshipGraph",
    "RelationshipGraphError",
    "RetrievalDocument",
    "SourceLoadError",
    "SearchHit",
    "SparseEmbedding",
    "TABLE_COLLECTION",
    "build_documents",
    "build_offline_assets",
    "build_relationship_graph",
    "default_retrieval_cases",
    "evaluate_retrieval",
    "load_facts",
    "load_published_asset",
    "RetrievalCase",
    "RetrievalCaseResult",
    "RetrievalEvaluationError",
    "RetrievalEvaluationSummary",
]
