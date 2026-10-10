"""Multi-Turn Query V1 的结构化语义修订与确定性合并。"""

import re
from dataclasses import replace

from src.online_query.contracts import (
    ExecutionControl,
    ExecutionStopped,
    QueryErrorCode,
)
from src.online_query.query_understanding import (
    FilterCandidate,
    QueryType,
    QueryUnderstandingClarificationRequired,
    SemanticQueryCandidate,
    SemanticQueryCannotAnswer,
    SemanticQueryStructureError,
    ValidatedFilter,
    ValidatedSemanticQuery,
    validate_candidate,
)


class SemanticRevisionError(ValueError):
    """语义修订不能安全产生唯一的下一轮查询。"""

    def __init__(
        self,
        message: str,
        *,
        error_code: QueryErrorCode,
        reason: str,
    ) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.reason = reason


_UNSUPPORTED_ANALYSIS_TERMS = (
    "同比",
    "环比",
    "趋势",
    "原因",
    "为什么",
    "为何",
    "归因",
    "对比",
    "比较",
    "经营分析",
    "商业分析",
    "多查询",
    "多次查询",
    "多条查询",
)


def revise_semantic_query(
    previous: ValidatedSemanticQuery,
    question: str,
    *,
    query_understanding: object | None,
    execution_control: ExecutionControl | None = None,
) -> ValidatedSemanticQuery:
    """把当前追问解析为 delta，并合并到上一轮已确认语义。"""

    if not isinstance(previous, ValidatedSemanticQuery):
        raise SemanticRevisionError(
            "当前会话缺少可用的结构化查询状态",
            error_code=QueryErrorCode.CONVERSATION_UNAVAILABLE,
            reason="STRUCTURED_STATE_MISSING",
        )
    if not isinstance(question, str) or not question.strip():
        raise SemanticRevisionError(
            "查询问题不能为空或格式错误",
            error_code=QueryErrorCode.INVALID_REQUEST,
            reason="QUESTION_EMPTY",
        )

    normalized_question = question.strip()
    if _contains_unsupported_analysis(normalized_question):
        raise SemanticRevisionError(
            "当前问题超出单条查询修订范围",
            error_code=QueryErrorCode.UNSUPPORTED_ANALYSIS,
            reason="UNSUPPORTED_ANALYSIS_SCOPE",
        )

    dimension_operation = _dimension_operation(normalized_question)
    if dimension_operation == "clarify":
        raise SemanticRevisionError(
            "请明确是替换现有分组维度，还是在现有维度上增加分组维度",
            error_code=QueryErrorCode.CLARIFICATION_REQUIRED,
            reason="DIMENSION_OPERATION_AMBIGUOUS",
        )

    understand_revision = getattr(query_understanding, "understand_revision", None)
    if not callable(understand_revision):
        raise SemanticRevisionError(
            "查询修订服务尚未配置，请稍后重试",
            error_code=QueryErrorCode.LLM_ERROR,
            reason="REVISION_ADAPTER_NOT_CONFIGURED",
        )
    try:
        if execution_control is not None:
            execution_control.checkpoint()
        controlled = getattr(
            query_understanding, "understand_revision_with_control", None
        )
        candidate = (
            controlled(previous, normalized_question, execution_control)
            if execution_control is not None and callable(controlled)
            else understand_revision(previous, normalized_question)
        )
        if execution_control is not None:
            execution_control.checkpoint()
    except ExecutionStopped:
        raise
    except SemanticRevisionError:
        raise
    except Exception as exc:  # noqa: BLE001 - adapter must map to a safe error
        raise SemanticRevisionError(
            "暂时无法理解这个查询，请稍后重试",
            error_code=QueryErrorCode.LLM_ERROR,
            reason=_exception_reason(exc, "REVISION_UNDERSTANDING_FAILED"),
        ) from exc

    if isinstance(candidate, QueryUnderstandingClarificationRequired):
        raise SemanticRevisionError(
            "请明确需要查询的业务指标口径",
            error_code=QueryErrorCode.CLARIFICATION_REQUIRED,
            reason=candidate.reason,
        )

    if not isinstance(candidate, SemanticQueryCandidate):
        raise SemanticRevisionError(
            "暂时无法理解这个查询，请稍后重试",
            error_code=QueryErrorCode.LLM_ERROR,
            reason="REVISION_CANDIDATE_TYPE_INVALID",
        )
    if dimension_operation == "replace" and not candidate.dimensions:
        raise SemanticRevisionError(
            "请明确要替换成哪个分组维度",
            error_code=QueryErrorCode.CLARIFICATION_REQUIRED,
            reason="DIMENSION_REPLACEMENT_TARGET_MISSING",
        )
    if not _has_semantic_delta(candidate):
        raise SemanticRevisionError(
            "请明确需要新增或修改的查询条件",
            error_code=QueryErrorCode.CLARIFICATION_REQUIRED,
            reason="REVISION_DELTA_EMPTY",
        )

    try:
        return _merge_and_validate(
            previous,
            candidate,
            normalized_question,
            replace_dimensions=dimension_operation == "replace",
        )
    except SemanticQueryCannotAnswer as exc:
        raise SemanticRevisionError(
            "请明确需要新增或修改的查询条件",
            error_code=QueryErrorCode.CLARIFICATION_REQUIRED,
            reason=exc.reason,
        ) from exc
    except SemanticQueryStructureError as exc:
        raise SemanticRevisionError(
            "暂时无法理解这个查询，请稍后重试",
            error_code=QueryErrorCode.LLM_ERROR,
            reason=exc.reason,
        ) from exc
    except Exception as exc:  # noqa: BLE001 - state merge must fail closed
        raise SemanticRevisionError(
            "暂时无法理解这个查询，请稍后重试",
            error_code=QueryErrorCode.LLM_ERROR,
            reason=_exception_reason(exc, "REVISION_VALIDATION_FAILED"),
        ) from exc


def _merge_and_validate(
    previous: ValidatedSemanticQuery,
    candidate: SemanticQueryCandidate,
    question: str,
    *,
    replace_dimensions: bool = False,
) -> ValidatedSemanticQuery:
    """执行固定槽位规则，随后交给 Domain 校验。"""

    query_type = (
        previous.query_type
        if candidate.query_type is QueryType.UNKNOWN
        else candidate.query_type
    )
    subjects = candidate.subjects or previous.subjects
    metrics = candidate.metrics or previous.metrics
    dimensions = (
        candidate.dimensions
        if replace_dimensions
        else _append_unique(previous.dimensions, candidate.dimensions)
    )
    filters = _merge_filters(previous.filters, candidate.filters)

    # None 表示当前追问没有修改时间。先跳过旧时间的重新解析，避免跨午夜
    # 后把已经确认的绝对时间窗口重新解释成另一段相对时间。
    validated = validate_candidate(
        SemanticQueryCandidate(
            query_type=query_type,
            subjects=subjects,
            metrics=metrics,
            dimensions=dimensions,
            time=candidate.time,
            filters=filters,
        ),
        original_question=question,
    )
    if candidate.time is None:
        validated = replace(validated, time=previous.time)
    return validated


def revise_history_semantic_query(
    previous,
    question,
    *,
    query_understanding,
    execution_control: ExecutionControl | None = None,
):
    """历史profile使用完整条件delta，基础语义沿用既有确定性合并。"""

    def clarification(message):
        return SemanticRevisionError(
            message,
            error_code=QueryErrorCode.CLARIFICATION_REQUIRED,
            reason="HISTORY_DELTA_AMBIGUOUS",
        )

    if _contains_unsupported_analysis(question):
        raise SemanticRevisionError(
            "当前问题超出单条查询修订范围",
            error_code=QueryErrorCode.UNSUPPORTED_ANALYSIS,
            reason="UNSUPPORTED_ANALYSIS_SCOPE",
        )
    dimension_operation = _dimension_operation(question)
    if dimension_operation == "clarify":
        raise clarification("请明确增加还是替换分组维度")
    try:
        if execution_control is not None:
            controlled = getattr(
                query_understanding,
                "understand_history_revision_with_control",
                None,
            )
            response = (
                controlled(previous, question, execution_control)
                if callable(controlled)
                else query_understanding.understand_history_revision(previous, question)
            )
        else:
            response = query_understanding.understand_history_revision(
                previous, question
            )
    except ExecutionStopped:
        raise
    except Exception as exc:  # noqa: BLE001 - model候选故障映射为公开错误
        raise SemanticRevisionError(
            "暂时无法理解追问",
            error_code=QueryErrorCode.LLM_ERROR,
            reason="HISTORY_REVISION_FAILED",
        ) from exc
    if isinstance(response, QueryUnderstandingClarificationRequired):
        raise clarification("请明确要修改的业务条件")
    candidate, operations = response
    if not _has_semantic_delta(candidate) and all(
        operation == "keep" for operation, _ in operations.values()
    ):
        raise clarification("请明确需要新增或修改的查询条件")
    if dimension_operation == "replace" and not candidate.dimensions:
        raise clarification("请明确新的分组维度")
    try:
        merged = _merge_and_validate(
            previous,
            candidate,
            question,
            replace_dimensions=dimension_operation == "replace",
        )
    except (SemanticQueryCannotAnswer, SemanticQueryStructureError) as exc:
        raise clarification("当前条件无法确定唯一查询") from exc
    conditions = previous.restoration_conditions
    if conditions is None:
        raise clarification("历史缺少完整查询条件")
    values = {}
    for name, (operation, value) in operations.items():
        values[name] = (
            getattr(conditions, name)
            if operation == "keep"
            else value
            if operation == "set"
            else (() if name in {"order_by", "aggregate_filters"} else None)
        )
    if values["row_limit"] is not None and not values["order_by"]:
        raise clarification("排名需要明确排序依据；取消排序时请同时取消排名数量")
    if operations["order_by"][0] == "keep" and merged.metrics != previous.metrics:
        missing = {
            item.target
            for item in values["order_by"]
            if item.target_kind == "metric" and item.target not in merged.metrics
        }
        if missing:
            if (
                len(previous.metrics) != 1
                or len(merged.metrics) != 1
                or len(missing) != 1
            ):
                raise clarification("请明确新指标对应的排序")
            values["order_by"] = tuple(
                replace(item, target=merged.metrics[0])
                if item.target_kind == "metric"
                else item
                for item in values["order_by"]
            )
    if any(item.metric not in merged.metrics for item in values["aggregate_filters"]):
        raise clarification("请明确旧指标聚合筛选是否取消或改成新条件")
    output = set(merged.dimensions)
    if values["selection"] is not None:
        output.update(values["selection"].fields)
    if any(
        item.target_kind != "metric" and item.target not in output
        for item in values["order_by"]
    ):
        raise clarification("分组或选择已改变，请明确新的排序条件")
    return replace(merged, restoration_conditions=replace(conditions, **values))


def _merge_filters(
    previous: tuple[ValidatedFilter, ...],
    current: tuple[FilterCandidate, ...],
) -> tuple[FilterCandidate, ...]:
    result = [
        FilterCandidate(
            field_text=item.field_text,
            operator=item.operator,
            values=item.values,
        )
        for item in previous
    ]
    positions = {
        _filter_key(item.field_text): index for index, item in enumerate(result)
    }
    for item in current:
        key = _filter_key(item.field_text)
        position = positions.get(key)
        if position is None:
            positions[key] = len(result)
            result.append(item)
        else:
            result[position] = item
    return tuple(result)


_DIMENSION_REPLACEMENT = re.compile(
    r"(?:分组维度|分组|维度)\s*(?:改成|改为|换成|替换为|替换成)"
)
_DIMENSION_APPEND = re.compile(r"(?:再加(?:上)?|再增加|增加|追加|加上)")
_DIMENSION_REPLACEMENT_NEGATION = re.compile(
    r"(?:不是|不要|别|并非)\s*(?:把)?\s*(?:分组维度|分组|维度)\s*"
    r"(?:改成|改为|换成|替换为|替换成)"
)


def _dimension_operation(question: str) -> str:
    """只按用户明确的维度操作词选择替换；其他情况沿用追加规则。"""

    has_replacement = _DIMENSION_REPLACEMENT.search(question) is not None
    has_append = _DIMENSION_APPEND.search(question) is not None
    if _DIMENSION_REPLACEMENT_NEGATION.search(question) or (
        has_replacement and has_append
    ):
        return "clarify"
    if has_replacement:
        return "replace"
    return "append"


def _append_unique(
    previous: tuple[str, ...],
    current: tuple[str, ...],
) -> tuple[str, ...]:
    result = list(previous)
    seen = {_text_key(item) for item in result}
    for item in current:
        key = _text_key(item)
        if key not in seen:
            seen.add(key)
            result.append(item)
    return tuple(result)


def _has_semantic_delta(candidate: SemanticQueryCandidate) -> bool:
    return bool(
        candidate.subjects
        or candidate.metrics
        or candidate.dimensions
        or candidate.time is not None
        or candidate.filters
    )


def _contains_unsupported_analysis(question: str) -> bool:
    compact = "".join(question.split())
    return any(term in compact for term in _UNSUPPORTED_ANALYSIS_TERMS)


def _filter_key(value: str) -> str:
    return _text_key(value)


def _text_key(value: str) -> str:
    return "".join(value.split()).casefold()


def _exception_reason(error: BaseException, fallback: str) -> str:
    reason = getattr(error, "reason", None)
    if isinstance(reason, str) and reason.strip():
        return reason.strip()
    return fallback


__all__ = ["SemanticRevisionError", "revise_semantic_query"]
