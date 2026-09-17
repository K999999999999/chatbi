"""指标语义查询和必需物理字段推导。"""

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
import re
from types import MappingProxyType

from sqlglot import exp, parse_one
from sqlglot.errors import SqlglotError

from ..contracts import ColumnHit, MetricHit
from ..query_understanding import ValidatedSemanticQuery


class ResourceRetrievalContractError(RuntimeError):
    """候选资源或指标必需字段不满足在线 Contract。"""


_TIME_FIELD_PATTERN = re.compile(
    r"^\s*(?P<source>[^\s]+)\s*->\s*(?P<target>[^\s]+)\s*$"
)


@dataclass(frozen=True, slots=True)
class _TimeField:
    source_table: str
    source_column: str
    target_table: str
    filter_column: str
    edge_id: str = ""


def _metric_data_source(metric: MetricHit) -> str:
    return _required_metadata_text(metric.metadata, "data_source", metric.document_id)


def _column_query(query: ValidatedSemanticQuery, metric: MetricHit | None) -> str:
    base_query = _semantic_query_text(
        (
            *query.dimensions,
            *(item.field_text for item in query.filters),
            *query.subjects,
        )
    )
    formula = metric.metadata.get("formula", "") if metric else ""
    time_field = metric.metadata.get("time_field", "") if metric else ""
    return "\n".join(
        value
        for value in (
            base_query,
            metric.page_content if metric else "",
            str(formula),
            str(time_field),
        )
        if value
    )


def _multi_column_query(
    query: ValidatedSemanticQuery,
    metrics: tuple[MetricHit, ...],
) -> str:
    """合并全部指标的语义文本和认证字段事实，形成一次 COLUMN 查询。"""

    values: list[str] = [
        _semantic_query_text(
            (
                *query.dimensions,
                *(item.field_text for item in query.filters),
                *query.subjects,
            )
        )
    ]
    for metric in metrics:
        values.extend(
            (
                metric.page_content,
                str(metric.metadata.get("formula", "")),
                str(metric.metadata.get("time_field", "")),
            )
        )
    return "\n".join(dict.fromkeys(value for value in values if value))


def _parse_time_field(metric: MetricHit | None) -> _TimeField | None:
    if metric is None:
        return None
    raw = metric.metadata.get("time_field")
    if not isinstance(raw, str) or not raw.strip():
        raise ResourceRetrievalContractError(
            f"指标 {metric.metric_name} 缺少有效 time_field"
        )
    match = _TIME_FIELD_PATTERN.fullmatch(raw)
    if match is None:
        raise ResourceRetrievalContractError(
            f"指标 {metric.metric_name} 的 time_field 格式无效"
        )
    source_table, source_column = _split_field_ref(match.group("source"), metric)
    target_table, filter_column = _split_field_ref(match.group("target"), metric)
    return _TimeField(source_table, source_column, target_table, filter_column)


def _split_field_ref(value: str, metric: MetricHit) -> tuple[str, str]:
    parts = value.split(".")
    if len(parts) == 2:
        return f"{_metric_schema(metric)}.{parts[0]}", parts[1]
    if len(parts) == 3:
        return f"{parts[0]}.{parts[1]}", parts[2]
    raise ResourceRetrievalContractError(
        f"指标 {metric.metric_name} 的字段引用格式无效：{value}"
    )


def _metric_schema(metric: MetricHit) -> str:
    source = _metric_data_source(metric).split(".")
    if len(source) != 2:
        raise ResourceRetrievalContractError(
            f"指标 {metric.metric_name} 的 data_source 格式无效"
        )
    return source[0]


def _required_columns(
    metric: MetricHit | None,
    time_field: _TimeField | None,
) -> Mapping[str, frozenset[str]]:
    if metric is None:
        return MappingProxyType({})
    formula = metric.metadata.get("formula")
    if not isinstance(formula, str) or not formula.strip():
        raise ResourceRetrievalContractError(
            f"指标 {metric.metric_name} 缺少有效 formula"
        )
    try:
        expression = parse_one(f"SELECT {formula}", read="postgres")
    except (SqlglotError, ValueError, TypeError) as exc:
        raise ResourceRetrievalContractError(
            f"指标 {metric.metric_name} 的 formula 无法确定性解析"
        ) from exc
    result: dict[str, set[str]] = defaultdict(set)
    data_source = _metric_data_source(metric)
    for column in expression.find_all(exp.Column):
        if not column.name or column.name == "*":
            raise ResourceRetrievalContractError(
                f"指标 {metric.metric_name} 的 formula 存在无法解析的字段引用"
            )
        result[data_source].add(column.name)
    filters = metric.metadata.get("filters", ())
    if not isinstance(filters, (list, tuple)):
        raise ResourceRetrievalContractError(
            f"指标 {metric.metric_name} 的 filters 格式无效"
        )
    for index, filter_expression in enumerate(filters, 1):
        if not isinstance(filter_expression, str) or not filter_expression.strip():
            raise ResourceRetrievalContractError(
                f"指标 {metric.metric_name} 的第 {index} 个 filter 无效"
            )
        try:
            filter_ast = parse_one(
                f"SELECT {filter_expression}",
                read="postgres",
            )
        except (SqlglotError, ValueError, TypeError) as exc:
            raise ResourceRetrievalContractError(
                f"指标 {metric.metric_name} 的 filter 无法确定性解析"
            ) from exc
        for column in filter_ast.find_all(exp.Column):
            if not column.name or column.name == "*":
                raise ResourceRetrievalContractError(
                    f"指标 {metric.metric_name} 的 filter 存在无法解析的字段引用"
                )
            result[data_source].add(column.name)
    if time_field is not None:
        result[time_field.source_table].add(time_field.source_column)
        result[time_field.target_table].add(time_field.filter_column)
    return MappingProxyType(
        {table: frozenset(columns) for table, columns in result.items()}
    )


def _required_columns_many(
    metrics: tuple[MetricHit, ...],
    time_field: _TimeField | None,
) -> Mapping[str, frozenset[str]]:
    """合并全部指标公式、过滤条件及公共时间关系要求的字段。"""

    merged: defaultdict[str, set[str]] = defaultdict(set)
    for metric in metrics:
        for table, columns in _required_columns(metric, time_field).items():
            merged[table].update(columns)
    return MappingProxyType(
        {table: frozenset(columns) for table, columns in sorted(merged.items())}
    )


def _contains_required_columns(
    column_hits: tuple[ColumnHit, ...],
    required: Mapping[str, frozenset[str]],
) -> bool:
    by_table: defaultdict[str, set[str]] = defaultdict(set)
    for hit in column_hits:
        by_table[hit.qualified_table].add(hit.column_name)
    return all(
        required_columns <= by_table.get(table, set())
        for table, required_columns in required.items()
    )


def _missing_required_column_details(
    metrics: tuple[MetricHit, ...],
    time_field: _TimeField | None,
    column_hits: tuple[ColumnHit, ...],
) -> tuple[str, ...]:
    """记录每个缺失物理字段及依赖它的请求指标。"""

    available = {(hit.qualified_table, hit.column_name) for hit in column_hits}
    dependents: defaultdict[tuple[str, str], set[str]] = defaultdict(set)
    for metric in metrics:
        for table, columns in _required_columns(metric, time_field).items():
            for column in columns:
                if (table, column) not in available:
                    dependents[(table, column)].add(metric.metric_name)
    return tuple(
        f"缺失字段 {table}.{column}；影响指标：{'、'.join(sorted(names))}"
        for (table, column), names in sorted(dependents.items())
    )


def _semantic_query_text(values: tuple[str, ...]) -> str:
    return "、".join(value.strip() for value in values if value.strip())


def _required_metadata_text(
    metadata: Mapping[str, object],
    key: str,
    document_id: str,
) -> str:
    value = metadata.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ResourceRetrievalContractError(f"{document_id} 缺少有效 {key}")
    return value.strip()
