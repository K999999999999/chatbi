"""指标意图、查询文本和必需物理字段处理。"""

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
import re
from types import MappingProxyType
from typing import Any

from sqlglot import exp, parse_one
from sqlglot.errors import SqlglotError

from ..contracts import ColumnHit, MetricHit


class ResourceRetrievalContractError(RuntimeError):
    """候选资源或指标必需字段不满足在线 Contract。"""


_METRIC_INTENT_TERMS = (
    "已完成订单数",
    "已完成订单数量",
    "完成订单数",
    "销售额",
    "净销售额",
    "营收",
    "销售成本",
    "人民币成本",
    "毛利率",
    "毛利润率",
    "毛利",
    "毛利润",
    "成本",
    "金额",
    "数量",
    "总额",
    "平均值",
    "占比",
    "统计",
)
_METRIC_INTENT_PATTERN = re.compile(
    r"(?:数量|金额|总额|均价|单价|成本|利润|占比|率|数|额)"
)
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


def _has_metric_intent(question: str) -> bool:
    """判断是否需要进入 METRIC 路线，不把普通实体查询误判为指标查询。"""

    normalized_question = _normalize(question)
    if any(
        _contains_normalized(normalized_question, term)
        for term in _METRIC_INTENT_TERMS
    ):
        return True
    return _METRIC_INTENT_PATTERN.search(normalized_question) is not None


def _metric_data_source(metric: MetricHit) -> str:
    value = metric.metadata.get("data_source")
    if not isinstance(value, str) or not value.strip():
        raise ResourceRetrievalContractError(
            f"{metric.document_id} 缺少有效 data_source"
        )
    return value.strip()


def _column_query(question: str, metric: MetricHit | None) -> str:
    if metric is None:
        return question
    formula = metric.metadata.get("formula", "")
    time_field = metric.metadata.get("time_field", "")
    return "\n".join(
        value
        for value in (question, metric.page_content, str(formula), str(time_field))
        if value
    )


def _multi_column_query(question: str, metrics: tuple[MetricHit, ...]) -> str:
    """合并全部指标的语义文本和认证字段事实，形成一次 COLUMN 查询。"""

    values: list[str] = [question]
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
        raise ResourceRetrievalContractError(f"指标 {metric.metric_name} 缺少有效 time_field")
    match = _TIME_FIELD_PATTERN.fullmatch(raw)
    if match is None:
        raise ResourceRetrievalContractError(f"指标 {metric.metric_name} 的 time_field 格式无效")
    source_table, source_column = _split_field_ref(match.group("source"), metric)
    target_table, filter_column = _split_field_ref(match.group("target"), metric)
    return _TimeField(source_table, source_column, target_table, filter_column)


def _split_field_ref(value: str, metric: MetricHit) -> tuple[str, str]:
    parts = value.split(".")
    if len(parts) == 2:
        return f"{_metric_schema(metric)}.{parts[0]}", parts[1]
    if len(parts) == 3:
        return f"{parts[0]}.{parts[1]}", parts[2]
    raise ResourceRetrievalContractError(f"指标 {metric.metric_name} 的字段引用格式无效：{value}")


def _metric_schema(metric: MetricHit) -> str:
    source = _metric_data_source(metric).split(".")
    if len(source) != 2:
        raise ResourceRetrievalContractError(f"指标 {metric.metric_name} 的 data_source 格式无效")
    return source[0]


def _required_columns(
    metric: MetricHit | None,
    time_field: _TimeField | None,
) -> Mapping[str, frozenset[str]]:
    if metric is None:
        return MappingProxyType({})
    formula = metric.metadata.get("formula")
    if not isinstance(formula, str) or not formula.strip():
        raise ResourceRetrievalContractError(f"指标 {metric.metric_name} 缺少有效 formula")
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
        raise ResourceRetrievalContractError(f"指标 {metric.metric_name} 的 filters 格式无效")
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
        {
            table: frozenset(columns)
            for table, columns in sorted(merged.items())
        }
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

    available = {
        (hit.qualified_table, hit.column_name)
        for hit in column_hits
    }
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


def _normalize(value: str) -> str:
    return "".join(
        char
        for char in value.casefold()
        if char.isalnum() or "\u4e00" <= char <= "\u9fff"
    )


def _contains_normalized(text: str, candidate: str) -> bool:
    normalized = _normalize(candidate)
    return bool(normalized) and normalized in text
