"""Multi-Metric Retrieval（多指标检索）的确定性请求规划。"""

from dataclasses import dataclass
import re

from sqlglot import exp, parse_one
from sqlglot.errors import SqlglotError

from .contracts import (
    FallbackPolicy,
    MetricConstraint,
    MetricMention,
    MetricRequestPlan,
    MetricPlanStatus,
    RequestShape,
    RetrievalRequest,
)
from .rag_runtime import MetricCatalog, MetricCatalogEntry


_ACTION_PATTERN = re.compile(r"统计|查询|查看|比较|分析")
_SEPARATOR_PATTERN = re.compile(r"、|，|,|以及|和|及|与")
_METRIC_ENDING_PATTERN = re.compile(
    r"(?:数量|金额|利润|毛利率|占比|均价|单价|总额|成本|毛利|数|额|率)$"
)
_UNSUPPORTED_MULTI_MARKERS = ("不要", "不查", "不统计", "排除", "分别")
_TEXT_MATCH_MARKERS = (
    "名称中包含",
    "描述中包含",
    "文本中包含",
    "字段中包含",
    "字符串中包含",
)
_TRIM_CHARS = " 。！？；;：:"


@dataclass(frozen=True, slots=True)
class _ListItem:
    text: str
    start: int
    end: int


def build_retrieval_request(question: str) -> RetrievalRequest:
    """在读取发布资产前确定请求形态和技术失败回退策略。"""

    if not isinstance(question, str) or not question.strip():
        raise ValueError("检索问题不能为空")
    normalized = question.strip()
    shape = classify_request_shape(normalized)
    policy = (
        FallbackPolicy.ALLOW_STATIC
        if shape == RequestShape.BASELINE
        else FallbackPolicy.FAIL_CLOSED
    )
    return RetrievalRequest(
        question=normalized,
        request_shape=shape,
        fallback_policy=policy,
    )


def classify_request_shape(question: str) -> RequestShape:
    """仅用有限句法预判是否存在明确多指标列举。"""

    if any(marker in question for marker in _TEXT_MATCH_MARKERS):
        return RequestShape.BASELINE
    segment, _ = _metric_segment(question)
    items = _list_items(segment)
    metric_like = tuple(item for item in items if _looks_like_metric(item.text))
    if len(metric_like) < 2:
        return RequestShape.BASELINE
    if any(marker in question for marker in _UNSUPPORTED_MULTI_MARKERS):
        return RequestShape.POSSIBLE_MULTI
    if _has_separate_item_dates(metric_like):
        return RequestShape.POSSIBLE_MULTI
    return RequestShape.EXPLICIT_MULTI


def plan_multi_metric_request(
    request: RetrievalRequest,
    catalog: MetricCatalog,
) -> MetricRequestPlan:
    """把明确指标列举映射为有序认证指标约束。"""

    if request.request_shape == RequestShape.BASELINE:
        return MetricRequestPlan(
            status=MetricPlanStatus.NOT_MULTI,
            request=request,
        )
    if request.request_shape == RequestShape.POSSIBLE_MULTI:
        return MetricRequestPlan(
            status=MetricPlanStatus.AMBIGUOUS,
            request=request,
            reason="多指标列举包含否定、分别范围或其他不支持表达",
        )

    segment, segment_offset = _metric_segment(request.question)
    items = tuple(
        item
        for item in _list_items(segment)
        if _looks_like_metric(item.text)
    )
    mentions = _resolve_mentions(segment, segment_offset, catalog)
    selected_mentions: list[MetricMention] = []
    for item in items:
        item_mentions = tuple(
            mention
            for mention in mentions
            if (
                segment_offset + item.start <= mention.start
                and mention.end <= segment_offset + item.end
            )
        )
        identities = {mention.document_id for mention in item_mentions}
        if not identities:
            return MetricRequestPlan(
                status=MetricPlanStatus.NO_METRIC,
                request=request,
                mentions=tuple(selected_mentions),
                reason=f"列举项无法映射到已发布指标：{item.text}",
            )
        if len(identities) > 1:
            return MetricRequestPlan(
                status=MetricPlanStatus.AMBIGUOUS,
                request=request,
                mentions=tuple(selected_mentions),
                reason=f"列举项包含多个指标身份：{item.text}",
            )
        selected_mentions.append(item_mentions[0])

    unique_mentions: list[MetricMention] = []
    seen_documents: set[str] = set()
    for mention in selected_mentions:
        if mention.document_id in seen_documents:
            continue
        seen_documents.add(mention.document_id)
        unique_mentions.append(mention)
    if not unique_mentions:
        return MetricRequestPlan(
            status=MetricPlanStatus.NO_METRIC,
            request=request,
            reason="没有列举项能够映射到已发布指标",
        )
    if len(unique_mentions) > 5:
        return MetricRequestPlan(
            status=MetricPlanStatus.TOO_MANY,
            request=request,
            mentions=tuple(selected_mentions),
            reason="去重后的请求指标超过 5 个",
        )

    constraints = tuple(
        _constraint(index, mention, catalog)
        for index, mention in enumerate(unique_mentions, 1)
    )
    try:
        compatible = _compatible(constraints)
    except ValueError as exc:
        return MetricRequestPlan(
            status=MetricPlanStatus.INVALID_ASSET,
            request=request,
            mentions=tuple(selected_mentions),
            constraints=constraints,
            reason=str(exc),
        )
    if not compatible:
        return MetricRequestPlan(
            status=MetricPlanStatus.UNSUPPORTED_COMBINATION,
            request=request,
            mentions=tuple(selected_mentions),
            constraints=constraints,
            reason="请求指标的数据来源、日期口径或固定过滤条件不一致",
        )
    return MetricRequestPlan(
        status=MetricPlanStatus.SUCCESS,
        request=request,
        mentions=tuple(selected_mentions),
        constraints=constraints,
    )


def _metric_segment(question: str) -> tuple[str, int]:
    actions = tuple(_ACTION_PATTERN.finditer(question))
    if not actions:
        return question, 0
    last = actions[-1]
    return question[last.end():], last.end()


def _list_items(segment: str) -> tuple[_ListItem, ...]:
    items: list[_ListItem] = []
    start = 0
    for separator in _SEPARATOR_PATTERN.finditer(segment):
        _append_item(items, segment, start, separator.start())
        start = separator.end()
    _append_item(items, segment, start, len(segment))
    return tuple(items)


def _append_item(
    items: list[_ListItem],
    segment: str,
    start: int,
    end: int,
) -> None:
    raw = segment[start:end]
    left_trimmed = raw.lstrip(_TRIM_CHARS)
    text = left_trimmed.rstrip(_TRIM_CHARS)
    if not text:
        return
    item_start = start + len(raw) - len(left_trimmed)
    items.append(_ListItem(text=text, start=item_start, end=item_start + len(text)))


def _looks_like_metric(value: str) -> bool:
    compact = re.sub(r"[\s的]+", "", value)
    return bool(_METRIC_ENDING_PATTERN.search(compact))


def _has_separate_item_dates(items: tuple[_ListItem, ...]) -> bool:
    date_pattern = re.compile(
        r"(?:20\d{2}年|\d{1,2}月|第[一二三四1-4]季度|上月|本月|去年|今年)"
    )
    return sum(bool(date_pattern.search(item.text)) for item in items) > 1


def _resolve_mentions(
    segment: str,
    segment_offset: int,
    catalog: MetricCatalog,
) -> tuple[MetricMention, ...]:
    candidates: list[tuple[int, int, str, MetricCatalogEntry]] = []
    for entry in catalog.entries:
        for label in (entry.metric_name, *entry.aliases):
            if not label:
                continue
            for match in re.finditer(re.escape(label), segment, flags=re.IGNORECASE):
                candidates.append((match.start(), match.end(), label, entry))
    candidates.sort(key=lambda item: (item[0], -(item[1] - item[0]), item[1]))

    mentions: list[MetricMention] = []
    occupied_until = -1
    for start, end, _, entry in candidates:
        if start < occupied_until:
            continue
        mentions.append(
            MetricMention(
                requested_text=segment[start:end],
                start=segment_offset + start,
                end=segment_offset + end,
                document_id=entry.document_id,
                metric_name=entry.metric_name,
            )
        )
        occupied_until = end
    return tuple(mentions)


def _constraint(
    ordinal: int,
    mention: MetricMention,
    catalog: MetricCatalog,
) -> MetricConstraint:
    entry = catalog.by_document_id.get(mention.document_id)
    if entry is None:
        raise ValueError(f"指标目录缺少 document_id：{mention.document_id}")
    return MetricConstraint(
        ordinal=ordinal,
        requested_text=mention.requested_text,
        document_id=entry.document_id,
        metric_name=entry.metric_name,
        formula=entry.formula,
        data_source=entry.data_source,
        time_field=entry.time_field,
        filters=entry.filters,
        depends_on=entry.depends_on,
    )


def _compatible(constraints: tuple[MetricConstraint, ...]) -> bool:
    data_sources = {
        constraint.data_source.strip().casefold()
        for constraint in constraints
    }
    time_fields = {
        re.sub(r"\s+", "", constraint.time_field).casefold()
        for constraint in constraints
    }
    filters = {
        _canonical_filters(constraint.filters)
        for constraint in constraints
    }
    return len(data_sources) == len(time_fields) == len(filters) == 1


def _canonical_filters(filters: tuple[str, ...]) -> tuple[str, ...]:
    normalized: set[str] = set()
    for raw_filter in filters:
        try:
            statement = parse_one(
                f"SELECT 1 WHERE {raw_filter}",
                dialect="postgres",
            )
        except SqlglotError as exc:
            raise ValueError(f"指标固定过滤条件无法解析：{raw_filter}") from exc
        where = statement.args.get("where")
        if not isinstance(where, exp.Where):
            raise ValueError(f"指标固定过滤条件无法解析：{raw_filter}")
        for condition in _flatten_and(where.this):
            if condition.find(exp.Or) is not None:
                raise ValueError("指标固定过滤条件暂不支持 OR")
            normalized_condition = condition.copy()
            for column in normalized_condition.find_all(exp.Column):
                column.set("table", None)
                column.set("db", None)
                column.set("catalog", None)
            normalized.add(
                normalized_condition.sql(
                    dialect="postgres",
                    normalize=True,
                )
            )
    return tuple(sorted(normalized))


def _flatten_and(condition: exp.Expression) -> tuple[exp.Expression, ...]:
    if isinstance(condition, exp.And):
        return (*_flatten_and(condition.left), *_flatten_and(condition.right))
    if isinstance(condition, exp.Paren):
        return _flatten_and(condition.this)
    return (condition,)
