"""RAG Offline Build（RAG 离线构建）模块公共入口。"""

from .documents import (
    COLUMN_COLLECTION,
    METRIC_COLLECTION,
    TABLE_COLLECTION,
    RetrievalDocument,
    build_documents,
)
from .sources import (
    DEFAULT_METRICS_PATH,
    DEFAULT_STRUCTURE_DIR,
    Facts,
    SourceLoadError,
    load_facts,
)

__all__ = [
    "COLUMN_COLLECTION",
    "DEFAULT_METRICS_PATH",
    "DEFAULT_STRUCTURE_DIR",
    "Facts",
    "METRIC_COLLECTION",
    "RetrievalDocument",
    "SourceLoadError",
    "TABLE_COLLECTION",
    "build_documents",
    "load_facts",
]
