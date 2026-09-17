"""Online Retrieval（在线检索）的 Trace 辅助和有限候选证据。"""

from collections.abc import Iterable, Iterator, Mapping
from contextlib import contextmanager
from typing import Any

from src.observability.contracts import TraceRecorder
from src.rag_offline.qdrant_store import SearchHit

from ..contracts import JoinResolution


_TRACE_EVIDENCE_LIMIT = 10


@contextmanager
def safe_span(
    recorder: TraceRecorder | None,
    name: str,
    attributes: Mapping[str, object] | None = None,
) -> Iterator[Any]:
    """创建内部 Retrieval Span；记录器失败时保持业务异常和返回值不变。"""

    scope: Any = _NoopTraceScope()
    try:
        if recorder is not None:
            scope = recorder.span(name, attributes=attributes)
        scope.__enter__()
    except Exception:
        scope = _NoopTraceScope()
        scope.__enter__()

    try:
        yield scope
    except BaseException as exc:
        try:
            scope.__exit__(type(exc), exc, exc.__traceback__)
        except Exception:
            pass
        raise
    else:
        try:
            scope.__exit__(None, None, None)
        except Exception:
            pass


class _NoopTraceScope:
    def __enter__(self) -> "_NoopTraceScope":
        return self

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> bool:
        return False


def safe_enrich_current(
    recorder: TraceRecorder | None,
    attributes: Mapping[str, object],
) -> None:
    if recorder is None:
        return
    try:
        recorder.enrich_current(attributes=attributes)
    except Exception:
        pass


def candidate_trace_attributes(
    hits: Iterable[SearchHit],
    *,
    scope_table: str | None = None,
) -> dict[str, object]:
    """只提取有界的检索身份/排序证据，不读取正文或完整 Metadata。"""

    materialized = tuple(hits)
    evidence = materialized[:_TRACE_EVIDENCE_LIMIT]
    attributes: dict[str, object] = {
        "chatbi.retrieval.candidate_count": len(materialized),
    }
    if not evidence:
        return attributes

    attributes.update(
        {
            "chatbi.retrieval.candidate.document_ids": tuple(
                hit.document_id for hit in evidence
            ),
            "chatbi.retrieval.candidate.ranks": tuple(
                range(1, len(evidence) + 1)
            ),
            "chatbi.retrieval.candidate.scores": tuple(
                float(hit.score) for hit in evidence
            ),
        }
    )
    qualified_tables = tuple(
        dict.fromkeys(
            table
            for hit in evidence
            if (table := scope_table or qualified_table_from_hit(hit)) is not None
        )
    )
    if qualified_tables:
        attributes["chatbi.retrieval.candidate.qualified_tables"] = qualified_tables
    return attributes


def qualified_table_from_hit(hit: SearchHit) -> str | None:
    metadata = hit.payload.get("metadata")
    if not isinstance(metadata, Mapping):
        return None
    schema_name = metadata.get("schema_name")
    table_name = metadata.get("table_name")
    if not isinstance(schema_name, str) or not isinstance(table_name, str):
        return None
    if not schema_name.strip() or not table_name.strip():
        return None
    return f"{schema_name.strip()}.{table_name.strip()}"


def qualified_filter_table(
    filter_payload: Mapping[str, str] | None,
) -> str | None:
    if not isinstance(filter_payload, Mapping):
        return None
    schema_name = filter_payload.get("schema_name")
    table_name = filter_payload.get("table_name")
    if not isinstance(schema_name, str) or not isinstance(table_name, str):
        return None
    if not schema_name.strip() or not table_name.strip():
        return None
    return f"{schema_name.strip()}.{table_name.strip()}"


def join_trace_attributes(resolution: JoinResolution) -> dict[str, object]:
    paths = resolution.paths[:_TRACE_EVIDENCE_LIMIT]
    return {
        "chatbi.retrieval.join.edge_ids": tuple(
            edge.edge_id
            for edge in resolution.joins[:_TRACE_EVIDENCE_LIMIT]
        ),
        "chatbi.retrieval.join.path_ids": tuple(
            f"path:{index}"
            for index, _ in enumerate(paths, 1)
        ),
        "chatbi.retrieval.join.path_count": len(resolution.paths),
    }
