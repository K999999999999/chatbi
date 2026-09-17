"""最终资源闭包和 QueryContext（查询上下文）组装。"""

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
import json
from types import MappingProxyType
from typing import Any

from .contracts import (
    ColumnHit,
    JoinConstraint,
    JoinResolution,
    MetricConstraint,
    MetricHit,
    QueryContext,
    RequestShape,
    TableHit,
)


@dataclass(frozen=True, slots=True)
class ContextAssembly:
    """一次检索请求的最终资源和上下文组装结果。"""

    final_tables: tuple[TableHit, ...]
    final_fields: tuple[ColumnHit, ...]
    dynamic_schema: str
    indicator_context: str
    query_context: QueryContext


def assemble_context(
    table_hits: tuple[TableHit, ...],
    column_hits: tuple[ColumnHit, ...],
    resolution: JoinResolution,
    *,
    metric: MetricHit | None = None,
    metrics: tuple[MetricHit, ...] = (),
    request_shape: RequestShape = RequestShape.BASELINE,
    metric_constraints: tuple[MetricConstraint, ...] = (),
    join_constraints: tuple[JoinConstraint, ...] = (),
) -> ContextAssembly:
    """完成最终资源闭包、提示上下文和 SQL 白名单组装。"""

    final_tables = _final_table_hits(table_hits, resolution)
    final_fields = _final_column_hits(
        column_hits,
        resolution,
        allowed_tables=frozenset(
            table.qualified_name for table in final_tables
        ),
    )
    dynamic_schema = _build_dynamic_schema(final_tables, final_fields, resolution)
    indicator_context = (
        _build_multi_indicator_context(metrics)
        if metrics
        else _build_indicator_context(metric)
    )
    query_context = QueryContext(
        prompt_context=_build_prompt_context(dynamic_schema, indicator_context),
        allowed_tables=frozenset(hit.qualified_name for hit in final_tables),
        allowed_columns=MappingProxyType(_allowed_columns(final_fields)),
        request_shape=request_shape,
        metric_constraints=metric_constraints,
        join_constraints=join_constraints,
    )
    return ContextAssembly(
        final_tables=final_tables,
        final_fields=final_fields,
        dynamic_schema=dynamic_schema,
        indicator_context=indicator_context,
        query_context=query_context,
    )


def _final_table_hits(
    table_hits: tuple[TableHit, ...],
    resolution: JoinResolution,
) -> tuple[TableHit, ...]:
    by_name = {hit.qualified_name: hit for hit in table_hits}
    names = {resolution.anchor_table} if resolution.anchor_table else set()
    for path in resolution.paths:
        names.update(path.tables)
    final: list[TableHit] = []
    for name in sorted(name for name in names if name):
        existing = by_name.get(name)
        if existing is None:
            raise ValueError(f"关系图返回了未被 TABLE 候选命中的表：{name}")
        final.append(existing)
    return tuple(final)


def _final_column_hits(
    column_hits: tuple[ColumnHit, ...],
    resolution: JoinResolution,
    *,
    allowed_tables: frozenset[str],
) -> tuple[ColumnHit, ...]:
    by_identity = {
        (hit.qualified_table, hit.column_name): hit for hit in column_hits
        if hit.qualified_table in allowed_tables
    }
    for edge in resolution.joins:
        if edge.direction == "forward":
            endpoints = (
                (edge.source_table, edge.source_columns),
                (edge.target_table, edge.target_columns),
            )
        else:
            endpoints = (
                (edge.target_table, edge.target_columns),
                (edge.source_table, edge.source_columns),
            )
        for table, columns in endpoints:
            if table not in allowed_tables:
                continue
            for column in columns:
                by_identity.setdefault(
                    (table, column),
                    _graph_join_column(table, column, edge.edge_id),
                )
    return tuple(
        sorted(
            by_identity.values(),
            key=lambda hit: (hit.qualified_table, hit.column_name, -hit.score),
        )
    )


def _graph_join_column(table: str, column: str, edge_id: str) -> ColumnHit:
    schema, table_name = table.split(".", maxsplit=1)
    return ColumnHit(
        document_id=f"graph:{table}.{column}",
        schema_name=schema,
        table_name=table_name,
        column_name=column,
        data_type="UNKNOWN",
        score=0.0,
        rank=0,
        metadata=MappingProxyType(
            {
                "doc_type": "COLUMN",
                "schema_name": schema,
                "table_name": table_name,
                "column_name": column,
                "data_type": "UNKNOWN",
                "relationship_edge_id": edge_id,
            }
        ),
        page_content=f"关系键字段：{table}.{column}",
    )


def _build_dynamic_schema(
    tables: tuple[TableHit, ...],
    fields: tuple[ColumnHit, ...],
    resolution: JoinResolution,
) -> str:
    value = {
        "tables": [
            {
                "schema_name": table.schema_name,
                "table_name": table.table_name,
                "table_role": table.table_role,
            }
            for table in tables
        ],
        "columns": [
            {
                "schema_name": field.schema_name,
                "table_name": field.table_name,
                "column_name": field.column_name,
                "data_type": field.data_type,
                "description": field.page_content,
            }
            for field in fields
        ],
        "joins": [
            {
                "edge_id": edge.edge_id,
                "source_table": edge.source_table,
                "source_columns": list(edge.source_columns),
                "target_table": edge.target_table,
                "target_columns": list(edge.target_columns),
                "direction": edge.direction,
            }
            for edge in resolution.joins
        ],
    }
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)


def _build_indicator_context(metric: MetricHit | None) -> str:
    if metric is None:
        return ""
    return json.dumps(
        _indicator_value(metric),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )


def _build_multi_indicator_context(metrics: tuple[MetricHit, ...]) -> str:
    value = {
        "requested_metrics": [_indicator_value(metric) for metric in metrics]
    }
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)


def _indicator_value(metric: MetricHit) -> dict[str, Any]:
    keys = (
        "metric_name",
        "aliases",
        "level",
        "definition",
        "formula",
        "data_source",
        "time_field",
        "filters",
        "depends_on",
        "notes",
    )
    return {
        key: _json_value(metric.metadata.get(key))
        for key in keys
        if key in metric.metadata
    }


def _build_prompt_context(dynamic_schema: str, indicator_context: str) -> str:
    parts = [f"Dynamic Schema:\n{dynamic_schema}"]
    if indicator_context:
        parts.append(f"Indicator Context:\n{indicator_context}")
    return "\n\n".join(parts)


def _allowed_columns(fields: tuple[ColumnHit, ...]) -> dict[str, frozenset[str]]:
    result: defaultdict[str, set[str]] = defaultdict(set)
    for field in fields:
        result[field.qualified_table].add(field.column_name)
    return {
        table: frozenset(columns)
        for table, columns in sorted(result.items())
    }


def _json_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value
