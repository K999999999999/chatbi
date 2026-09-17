"""Multi-Metric Retrieval（多指标检索）的确定性指标规划。"""

import re

from sqlglot import exp, parse_one
from sqlglot.errors import SqlglotError

from .contracts import (
    MetricConstraint,
    MetricHit,
    MetricMention,
    MetricPlanStatus,
    MetricRequestPlan,
    RetrievalRequest,
)


_MAX_REQUEST_METRICS = 5


def plan_retrieved_metrics(
    request: RetrievalRequest,
    metric_hits_by_query: tuple[tuple[MetricHit, ...], ...],
) -> MetricRequestPlan:
    """按结构化 metrics 顺序确认唯一权威 Metric。

    每个用户请求指标对应一次独立的 METRIC 检索结果。程序只接受名称或
    已登记 alias 的唯一精确匹配，不让排名第一的候选替用户猜测指标。
    """

    query = request.semantic_query
    if query is None:
        return MetricRequestPlan(
            status=MetricPlanStatus.INVALID_ASSET,
            request=request,
            reason="RetrievalRequest 缺少 ValidatedSemanticQuery",
        )

    requested_metrics = query.metrics
    if len(requested_metrics) > _MAX_REQUEST_METRICS:
        return MetricRequestPlan(
            status=MetricPlanStatus.TOO_MANY,
            request=request,
            reason=f"请求指标超过 V1 上限 {_MAX_REQUEST_METRICS} 个",
        )
    if len(metric_hits_by_query) != len(requested_metrics):
        return MetricRequestPlan(
            status=MetricPlanStatus.NO_METRIC,
            request=request,
            reason="本次 METRIC 检索结果与请求指标数量不一致",
        )

    selected_mentions: list[MetricMention] = []
    selected_hits: list[MetricHit] = []
    for index, (requested_text, hits) in enumerate(
        zip(requested_metrics, metric_hits_by_query, strict=True),
        1,
    ):
        matches = _matching_hits(requested_text, hits)
        identities = {hit.document_id for hit in matches}
        if not identities:
            candidate_identities = {hit.document_id for hit in hits}
            status = (
                MetricPlanStatus.AMBIGUOUS
                if len(candidate_identities) > 1
                else MetricPlanStatus.NO_METRIC
            )
            return MetricRequestPlan(
                status=status,
                request=request,
                mentions=tuple(selected_mentions),
                reason=(
                    f"指标候选存在歧义：{requested_text}"
                    if status == MetricPlanStatus.AMBIGUOUS
                    else f"指标无法映射到唯一权威候选：{requested_text}"
                ),
            )
        if len(identities) > 1:
            return MetricRequestPlan(
                status=MetricPlanStatus.AMBIGUOUS,
                request=request,
                mentions=tuple(selected_mentions),
                reason=f"指标候选存在歧义：{requested_text}",
            )

        selected = next(iter(matches))
        selected_hits.append(selected)
        selected_mentions.append(
            MetricMention(
                requested_text=requested_text,
                start=index - 1,
                end=index - 1 + len(requested_text),
                document_id=selected.document_id,
                metric_name=selected.metric_name,
            )
        )

    unique_mentions: list[MetricMention] = []
    unique_hits: list[MetricHit] = []
    seen_documents: set[str] = set()
    for mention, hit in zip(selected_mentions, selected_hits, strict=True):
        if mention.document_id in seen_documents:
            continue
        seen_documents.add(mention.document_id)
        unique_mentions.append(mention)
        unique_hits.append(hit)

    if len(unique_mentions) > _MAX_REQUEST_METRICS:
        return MetricRequestPlan(
            status=MetricPlanStatus.TOO_MANY,
            request=request,
            mentions=tuple(selected_mentions),
            reason=f"去重后的请求指标超过 V1 上限 {_MAX_REQUEST_METRICS} 个",
        )

    try:
        constraints = tuple(
            _constraint_from_hit(
                index,
                hit,
                requested_text=mention.requested_text,
            )
            for index, (mention, hit) in enumerate(
                zip(unique_mentions, unique_hits, strict=True),
                1,
            )
        )
    except ValueError as exc:
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


def _matching_hits(
    requested_text: str,
    metric_hits: tuple[MetricHit, ...],
) -> tuple[MetricHit, ...]:
    normalized_request = _normalize(requested_text)
    matches: dict[str, MetricHit] = {}
    for hit in metric_hits:
        if any(
            normalized_request == _normalize(label) for label in _metric_labels(hit)
        ):
            previous = matches.get(hit.document_id)
            if previous is None or hit.score > previous.score:
                matches[hit.document_id] = hit
    return tuple(
        sorted(matches.values(), key=lambda item: (-item.score, item.document_id))
    )


def _metric_labels(hit: MetricHit) -> tuple[str, ...]:
    aliases = hit.metadata.get("aliases")
    if aliases is None:
        return (hit.metric_name,)
    if not isinstance(aliases, (list, tuple)):
        return (hit.metric_name,)
    return (hit.metric_name, *(item for item in aliases if isinstance(item, str)))


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
        constraint.data_source.strip().casefold() for constraint in constraints
    }
    time_fields = {
        re.sub(r"\s+", "", constraint.time_field).casefold()
        for constraint in constraints
    }
    filters = {_canonical_filters(constraint.filters) for constraint in constraints}
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
