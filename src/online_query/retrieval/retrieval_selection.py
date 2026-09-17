"""Online Retrieval 的候选范围、分组提示和 Anchor 选择。"""

import re

from ..contracts import MetricHit, TableHit
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
    question: str,
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

    grouping_text = grouping_text_from_question(question)
    grouping_names = grouping_table_names(
        grouping_text,
        table_hits,
        metric_table,
    )
    if grouping_text and not grouping_names:
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
            raise RequiredCandidateUnavailableError(
                f"V1 不支持中间表或桥接表：{name}"
            )
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
    grouping_text: str,
    table_hits: tuple[TableHit, ...],
    metric_table: str | None,
) -> frozenset[str]:
    if not grouping_text:
        return frozenset()
    return frozenset(
        hit.qualified_name
        for hit in table_hits
        if hit.qualified_name != metric_table
        and table_content_matches(grouping_text, hit.page_content)
    )


def grouping_text_from_question(question: str) -> str:
    match = re.search(
        r"按(?P<grouping>.+?)(?:统计|分析|比较|查询|查看|的)",
        question,
    )
    return match.group("grouping").strip() if match is not None else ""


def requires_date_context(question: str) -> bool:
    """只有问题明确涉及日期过滤或分组时才启用指标 time_field。"""

    return re.search(
        r"(?:20\d{2}\s*年|\d{1,2}\s*月|第[一二三四1-4]\s*季度|"
        r"日期|时间|今年|去年|本月|上月|今日|昨天|截止)",
        question,
    ) is not None


def table_content_matches(question: str, page_content: str) -> bool:
    normalized_content = normalize_text(page_content)
    return any(
        term in normalized_content
        for term in cjk_bigrams(question)
    )


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
