"""RAG Offline Build（RAG 离线构建）模块公共入口。"""

from .documents import (
    COLUMN_COLLECTION,
    METRIC_COLLECTION,
    TABLE_COLLECTION,
    RetrievalDocument,
    build_documents,
)
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
    "COLUMN_COLLECTION",
    "DEFAULT_METRICS_PATH",
    "DEFAULT_STRUCTURE_DIR",
    "Facts",
    "METRIC_COLLECTION",
    "RelationshipGraph",
    "RelationshipGraphError",
    "RetrievalDocument",
    "SourceLoadError",
    "TABLE_COLLECTION",
    "build_documents",
    "build_relationship_graph",
    "load_facts",
]
