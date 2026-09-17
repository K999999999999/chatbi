"""Multi-Metric Retrieval（多指标检索）的确定性请求规划。"""

import re

from sqlglot import exp, parse_one
from sqlglot.errors import SqlglotError

from ..contracts import (
    FallbackPolicy,
    MetricConstraint,
    MetricHit,
    MetricMention,
    MetricRequestPlan,
    MetricPlanStatus,
    RequestShape,
    RetrievalRequest,
)
from .metric_request_shape import (
    _list_items,
    _looks_like_metric,
    _metric_segment,
    classify_request_shape,
)


_MAX_REQUEST_METRICS = 5


def build_retrieval_request(question: str) -> RetrievalRequest:
    """在读取发布资产前确定请求形态；在线技术故障统一 fail-closed。"""

    if not isinstance(question, str) or not question.strip():
        raise ValueError("检索问题不能为空")
    normalized = question.strip()
    shape = classify_request_shape(normalized)
    return RetrievalRequest(
        question=normalized,
        request_shape=shape,
        fallback_policy=FallbackPolicy.FAIL_CLOSED,
    )


def plan_retrieved_metrics(
    request: RetrievalRequest,
    metric_hits: tuple[MetricHit, ...],
) -> MetricRequestPlan:
    """只依据本次 METRIC 检索命中构造有序认证指标约束。

    指标正文和 Metadata 已经随向量命中返回；在线链路不再读取完整指标目录，
    也不按指标 ID 发起第二次 Catalog 查询。
    """

    if request.request_shape == RequestShape.POSSIBLE_MULTI:
        return MetricRequestPlan(
            status=MetricPlanStatus.AMBIGUOUS,
            request=request,
            reason="多指标列举包含否定、分别范围或其他不支持表达",
        )

    if request.request_shape == RequestShape.BASELINE:
        selected, status, reason = _select_single_retrieved_metric(
            request.question,
            metric_hits,
        )
        if selected is None:
            return MetricRequestPlan(
                status=status,
                request=request,
                reason=reason,
            )
        try:
            constraint = _constraint_from_hit(1, selected, requested_text=selected.metric_name)
        except ValueError as exc:
            return MetricRequestPlan(
                status=MetricPlanStatus.INVALID_ASSET,
                request=request,
                reason=str(exc),
            )
        return MetricRequestPlan(
            status=MetricPlanStatus.SUCCESS,
            request=request,
            mentions=(
                MetricMention(
                    requested_text=selected.metric_name,
                    start=0,
                    end=len(selected.metric_name),
                    document_id=selected.document_id,
                    metric_name=selected.metric_name,
                ),
            ),
            constraints=(constraint,),
        )

    segment, segment_offset = _metric_segment(request.question)
    items = tuple(
        item
        for item in _list_items(segment)
        if _looks_like_metric(item.text)
    )
    mentions = _resolve_retrieved_mentions(segment, segment_offset, metric_hits)
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
                reason=f"列举项无法映射到本次 METRIC 候选：{item.text}",
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
            reason="没有列举项能够映射到本次 METRIC 候选",
        )
    if len(unique_mentions) > _MAX_REQUEST_METRICS:
        return MetricRequestPlan(
            status=MetricPlanStatus.TOO_MANY,
            request=request,
            mentions=tuple(selected_mentions),
            reason=f"去重后的请求指标超过 V1 上限 {_MAX_REQUEST_METRICS} 个",
        )

    hits_by_document = {hit.document_id: hit for hit in metric_hits}
    try:
        constraints = tuple(
            _constraint_from_hit(
                index,
                hits_by_document[mention.document_id],
                requested_text=mention.requested_text,
            )
            for index, mention in enumerate(unique_mentions, 1)
        )
    except (KeyError, ValueError) as exc:
        return MetricRequestPlan(
            status=MetricPlanStatus.INVALID_ASSET,
            request=request,
            mentions=tuple(selected_mentions),
            reason=str(exc),
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


def _select_single_retrieved_metric(
    question: str,
    metric_hits: tuple[MetricHit, ...],
) -> tuple[MetricHit | None, MetricPlanStatus, str]:
    normalized_question = _normalize(question)
    matched = tuple(
        (match_length, hit)
        for hit in metric_hits
        if (match_length := _metric_match_length(normalized_question, hit)) > 0
    )
    longest_match = max((length for length, _ in matched), default=0)
    exact = {
        hit.document_id: hit
        for length, hit in matched
        if length == longest_match
    }
    if len(exact) == 1:
        return next(iter(exact.values())), MetricPlanStatus.SUCCESS, ""
    if len(exact) > 1:
        return None, MetricPlanStatus.AMBIGUOUS, "指标候选无法唯一确定"
    if len(metric_hits) > 1:
        return None, MetricPlanStatus.AMBIGUOUS, "问题未明确匹配唯一指标，候选存在歧义"
    return None, MetricPlanStatus.NO_METRIC, "问题未匹配到本次 METRIC 候选"


def _resolve_retrieved_mentions(
    segment: str,
    segment_offset: int,
    metric_hits: tuple[MetricHit, ...],
) -> tuple[MetricMention, ...]:
    candidates: list[tuple[int, int, MetricHit]] = []
    for hit in metric_hits:
        for label in _metric_labels(hit):
            if not label:
                continue
            for match in re.finditer(re.escape(label), segment, flags=re.IGNORECASE):
                candidates.append((match.start(), match.end(), hit))
    candidates.sort(key=lambda item: (item[0], -(item[1] - item[0]), item[1]))

    mentions: list[MetricMention] = []
    occupied_until = -1
    for start, end, hit in candidates:
        if start < occupied_until:
            continue
        requested_text = segment[start:end]
        mentions.append(
            MetricMention(
                requested_text=requested_text,
                start=segment_offset + start,
                end=segment_offset + end,
                document_id=hit.document_id,
                metric_name=hit.metric_name,
            )
        )
        occupied_until = end
    return tuple(mentions)


def _metric_labels(hit: MetricHit) -> tuple[str, ...]:
    aliases = hit.metadata.get("aliases")
    if aliases is None:
        return (hit.metric_name,)
    if not isinstance(aliases, (list, tuple)):
        return (hit.metric_name,)
    return (hit.metric_name, *(item for item in aliases if isinstance(item, str)))


def _metric_match_length(question: str, hit: MetricHit) -> int:
    return max(
        (
            len(_normalize(label))
            for label in _metric_labels(hit)
            if _contains_normalized(question, label)
        ),
        default=0,
    )


def _constraint_from_hit(
    ordinal: int,
    hit: MetricHit,
    *,
    requested_text: str,
) -> MetricConstraint:
    return MetricConstraint(
        ordinal=ordinal,
        requested_text=requested_text,
        document_id=hit.document_id,
        metric_name=hit.metric_name,
        formula=_required_metadata_text(hit, "formula"),
        data_source=_required_metadata_text(hit, "data_source"),
        time_field=_required_metadata_text(hit, "time_field"),
        filters=_metadata_strings(hit, "filters"),
        depends_on=_metadata_strings(hit, "depends_on"),
    )


def _required_metadata_text(hit: MetricHit, key: str) -> str:
    value = hit.metadata.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"指标 {hit.document_id} 缺少有效 {key}")
    return value.strip()


def _metadata_strings(hit: MetricHit, key: str) -> tuple[str, ...]:
    value = hit.metadata.get(key, ())
    if not isinstance(value, (list, tuple)):
        raise ValueError(f"指标 {hit.document_id} 的 {key} 格式无效")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise ValueError(f"指标 {hit.document_id} 的 {key} 格式无效")
    return tuple(item.strip() for item in value)


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


def _normalize(value: str) -> str:
    return "".join(
        char
        for char in value.casefold()
        if char.isalnum() or "\u4e00" <= char <= "\u9fff"
    )


def _contains_normalized(question: str, candidate: str) -> bool:
    normalized_candidate = _normalize(candidate)
    return bool(normalized_candidate) and normalized_candidate in question
