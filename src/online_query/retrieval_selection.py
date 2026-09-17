"""Online Retrieval 的候选范围、分组提示和 Anchor 选择。"""

import re

from .contracts import MetricHit, TableHit
from .query_understanding import ValidatedSemanticQuery
from .resource_retrieval import _TimeField, _metric_data_source
from .retrieval_errors import (
    RequiredCandidateUnavailableError,
    RetrievalContractError,
)


_GENERIC_GROUPING_TERMS = frozenset(
    {"类型", "属性", "业务", "数据", "信息", "记录", "完成", "订单", "金额", "统计"}
)


def select_anchor(
    metric: MetricHit | None,
    table_hits: tuple[TableHit, ...],
) -> tuple[str, str]:
    """按照指标数据源或最高 TABLE 候选选择关系图 Anchor。"""

    if metric is not None:
        return _metric_data_source(metric), "metric_data_source"
    if not table_hits:
        raise RetrievalContractError("无法选择 Anchor：TABLE 候选为空")
    return table_hits[0].qualified_name, "highest_table_score"


def target_tables(
    candidate_tables: tuple[TableHit, ...],
    metric_table: str | None,
    time_field: _TimeField | None,
) -> tuple[str, ...]:
    """收集关系图必须覆盖的候选表集合。"""

    tables = {hit.qualified_name for hit in candidate_tables}
    if metric_table is not None:
        tables.add(metric_table)
    if time_field is not None:
        tables.add(time_field.target_table)
    return tuple(sorted(tables))


def candidate_table_hits(
    dimensions: tuple[str, ...],
    table_hits: tuple[TableHit, ...],
    metric_table: str | None,
    time_field: _TimeField | None,
) -> tuple[TableHit, ...]:
    """确定 COLUMN 和 Join 的最小候选表范围。"""

    names: set[str] = set()
    if metric_table is not None:
        names.add(metric_table)
    elif table_hits:
        names.add(table_hits[0].qualified_name)
    if time_field is not None:
        names.add(time_field.target_table)

    grouping_names = grouping_table_names(
        dimensions,
        table_hits,
        metric_table,
    )
    if dimensions and not grouping_names:
        raise RequiredCandidateUnavailableError(
            "用户请求的分组维度没有被 TABLE 候选命中"
        )
    names.update(grouping_names)

    by_name = {hit.qualified_name: hit for hit in table_hits}
    candidates: list[TableHit] = []
    for name in sorted(names):
        existing = by_name.get(name)
        if existing is None:
            raise RequiredCandidateUnavailableError(
                f"必需表没有被 TABLE 候选命中：{name}"
            )
        if is_intermediate_table(existing):
            raise RequiredCandidateUnavailableError(f"V1 不支持中间表或桥接表：{name}")
        candidates.append(existing)
    return tuple(candidates)


def is_intermediate_table(table: TableHit) -> bool:
    role = table.table_role.strip().casefold().replace("-", "_")
    return role in {
        "bridge",
        "bridge_table",
        "intermediate",
        "intermediate_table",
        "relationship_bridge",
    }


def grouping_table_names(
    dimensions: tuple[str, ...],
    table_hits: tuple[TableHit, ...],
    metric_table: str | None,
) -> frozenset[str]:
    if not dimensions:
        return frozenset()
    return frozenset(
        hit.qualified_name
        for hit in table_hits
        if hit.qualified_name != metric_table
        and any(
            table_content_matches(dimension, hit.page_content)
            for dimension in dimensions
        )
    )


def grouping_text_from_dimensions(dimensions: tuple[str, ...]) -> str:
    return "、".join(dimension.strip() for dimension in dimensions if dimension.strip())


def requires_date_context(query: ValidatedSemanticQuery) -> bool:
    """只有结构化查询存在已标准化时间条件时才启用指标 time_field。"""

    return query.time is not None


def table_content_matches(question: str, page_content: str) -> bool:
    normalized_content = normalize_text(page_content)
    return any(term in normalized_content for term in cjk_bigrams(question))


def cjk_bigrams(value: str) -> tuple[str, ...]:
    terms: set[str] = set()
    for run in re.findall(r"[\u4e00-\u9fff]{2,}", value):
        terms.update(
            term
            for index in range(len(run) - 1)
            if (term := run[index : index + 2]) not in _GENERIC_GROUPING_TERMS
        )
    return tuple(sorted(terms))


def normalize_text(value: str) -> str:
    return "".join(
        char
        for char in value.casefold()
        if char.isalnum() or "\u4e00" <= char <= "\u9fff"
    )
