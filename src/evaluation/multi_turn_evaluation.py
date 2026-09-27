"""按完整 Conversation（对话场景）运行多轮查询评测。"""

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from time import perf_counter
from typing import Protocol

from src.online_query.contracts import (
    QueryContext,
    QueryData,
    QueryErrorCode,
    QueryExecutor,
    QueryFailure,
    QuerySuccess,
    ValidatedSQL,
)
from src.online_query.sql_guard import validate_sql

from .evaluator import results_match

_OUTCOMES = frozenset(
    {"result_match", "clarification_required", "cannot_answer", "query_failure"}
)
_OUTCOME_ERROR_CODES = {
    "clarification_required": QueryErrorCode.CLARIFICATION_REQUIRED.value,
    "cannot_answer": QueryErrorCode.CANNOT_ANSWER.value,
}
_VALID_ERROR_CODES = frozenset(code.value for code in QueryErrorCode)


class MultiTurnEvaluationLoadError(RuntimeError):
    """多轮测试集文件整体不能用于评测。"""


class MultiTurnStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    INVALID_CASE = "INVALID_CASE"


@dataclass(frozen=True, slots=True)
class MultiTurnTurn:
    id: str
    question: str
    expected_sql: str = ""
    expected_outcome: str = "result_match"
    expected_error_code: str | None = None
    order_sensitive: bool = False
    validation_error: str | None = None

    @property
    def is_valid(self) -> bool:
        return self.validation_error is None


@dataclass(frozen=True, slots=True)
class MultiTurnCase:
    id: str
    description: str
    coverage: tuple[str, ...]
    turns: tuple[MultiTurnTurn, ...]
    validation_error: str | None = None

    @property
    def is_valid(self) -> bool:
        return (
            self.validation_error is None
            and len(self.turns) >= 2
            and all(turn.is_valid for turn in self.turns)
        )


@dataclass(frozen=True, slots=True)
class ConversationResponse:
    result: object
    conversation_id: str | None


class ConversationQueryClient(Protocol):
    def query(
        self,
        question: str,
        *,
        conversation_id: str | None,
        request_id: str,
    ) -> ConversationResponse:
        """通过正式 Query API 入口执行一轮查询。"""


class ConversationClientFactory(Protocol):
    def __call__(self) -> ConversationQueryClient:
        """为一个全新的 Conversation 创建隔离客户端。"""


@dataclass(frozen=True, slots=True)
class MultiTurnTurnEvaluation:
    turn_id: str
    question: str
    expected_outcome: str
    expected_error_code: str | None
    status: MultiTurnStatus
    query_error_code: str | None
    failure_reason: str | None
    duration_ms: int
    generated_sql: str | None = None


@dataclass(frozen=True, slots=True)
class MultiTurnCaseEvaluation:
    case_id: str
    coverage: tuple[str, ...]
    status: MultiTurnStatus
    failure_reason: str | None
    turns: tuple[MultiTurnTurnEvaluation, ...]


@dataclass(frozen=True, slots=True)
class MultiTurnEvaluationSummary:
    total_conversations: int
    valid_conversations: int
    passed_conversations: int
    failed_conversations: int
    invalid_conversations: int
    conversation_accuracy: float | None
    total_turns: int
    valid_turns: int
    passed_turns: int
    failed_turns: int
    invalid_turns: int
    execution_turns: int
    execution_passed: int
    execution_accuracy: float | None
    outcome_turns: int
    outcome_passed: int
    outcome_accuracy: float | None
    coverage_accuracy: Mapping[str, float | None]


@dataclass(frozen=True, slots=True)
class MultiTurnEvaluationRun:
    cases: tuple[MultiTurnCaseEvaluation, ...]
    summary: MultiTurnEvaluationSummary
    reference_results: Mapping[str, QueryData]


def load_multi_turn_cases(path: Path) -> tuple[MultiTurnCase, ...]:
    """加载多轮案例；单条格式错误保留为 INVALID_CASE。"""

    try:
        content = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise MultiTurnEvaluationLoadError("多轮测试集文件不存在") from None
    except (OSError, UnicodeError):
        raise MultiTurnEvaluationLoadError("多轮测试集文件无法读取") from None
    try:
        records = json.loads(content)
    except json.JSONDecodeError:
        raise MultiTurnEvaluationLoadError("多轮测试集不是合法 JSON") from None
    if not isinstance(records, list) or not records:
        raise MultiTurnEvaluationLoadError("多轮测试集必须是非空 JSON 数组")

    cases = tuple(
        _parse_case(record, index) for index, record in enumerate(records, start=1)
    )
    ids = [case.id for case in cases]
    if len(ids) != len(set(ids)):
        raise MultiTurnEvaluationLoadError("多轮测试集存在重复场景 id")
    return cases


def run_multi_turn_evaluation(
    cases: Sequence[MultiTurnCase],
    client_factory: ConversationClientFactory,
    query_executor: QueryExecutor,
    context: QueryContext,
) -> MultiTurnEvaluationRun:
    """逐个运行完整场景；场景内共享会话，场景间创建新客户端。"""

    evaluated: list[MultiTurnCaseEvaluation] = []
    reference_results: dict[str, QueryData] = {}
    for case in cases:
        if not case.is_valid:
            evaluated.append(
                _invalid_conversation(case, case.validation_error or "案例无效")
            )
            continue

        references, invalid_turn = _prepare_references(
            case,
            query_executor=query_executor,
            context=context,
        )
        if invalid_turn is not None:
            reason, turn_id = invalid_turn
            evaluated.append(
                _invalid_conversation(case, reason, invalid_turn_id=turn_id)
            )
            continue
        reference_results.update(references)

        try:
            client = client_factory()
        except Exception:
            evaluated.append(
                _failed_conversation(case, "无法创建隔离的 Query API 客户端")
            )
            continue

        turns: list[MultiTurnTurnEvaluation] = []
        conversation_id: str | None = None
        session_unavailable = False
        for turn in case.turns:
            if session_unavailable:
                turns.append(
                    _turn_result(
                        turn,
                        MultiTurnStatus.FAIL,
                        "前序轮次未建立会话，无法继续验证此场景",
                    )
                )
                continue

            request_id = f"evaluation-{case.id}-{turn.id}"
            started = perf_counter()
            try:
                response = client.query(
                    turn.question,
                    conversation_id=conversation_id,
                    request_id=request_id,
                )
            except Exception:
                turns.append(
                    _turn_result(
                        turn,
                        MultiTurnStatus.FAIL,
                        "Query API 调用失败",
                        duration_ms=_duration_ms(started),
                    )
                )
                if conversation_id is None:
                    session_unavailable = True
                continue
            duration_ms = _duration_ms(started)
            result = response.result

            if turn.expected_outcome == "result_match":
                turn_result, next_conversation_id = _evaluate_success_turn(
                    turn,
                    result,
                    response.conversation_id,
                    conversation_id,
                    references[_reference_id(case.id, turn.id)],
                    duration_ms=duration_ms,
                    order_sensitive=turn.order_sensitive,
                )
                turns.append(turn_result)
                if next_conversation_id is not None:
                    conversation_id = next_conversation_id
                elif conversation_id is None:
                    session_unavailable = True
                continue

            turn_result = _evaluate_failure_turn(
                turn,
                result,
                response.conversation_id,
                duration_ms=duration_ms,
            )
            turns.append(turn_result)
            if isinstance(result, QuerySuccess) and response.conversation_id:
                conversation_id = response.conversation_id

        evaluated.append(_conversation_result(case, tuple(turns)))
        _close_client(client)

    result_cases = tuple(evaluated)
    return MultiTurnEvaluationRun(
        cases=result_cases,
        summary=_summarize(result_cases),
        reference_results=reference_results,
    )


def _parse_case(record: object, index: int) -> MultiTurnCase:
    if not isinstance(record, dict):
        return MultiTurnCase(
            id=f"conversation-{index}",
            description="",
            coverage=(),
            turns=(),
            validation_error="案例必须是 JSON 对象",
        )

    errors: list[str] = []
    case_id = _required_text(record.get("id"), "id", errors) or f"conversation-{index}"
    description = _required_text(record.get("description"), "description", errors)
    raw_coverage = record.get("coverage", [])
    if not isinstance(raw_coverage, list) or any(
        not isinstance(value, str) or not value.strip() for value in raw_coverage
    ):
        errors.append("coverage 必须是字符串数组")
        coverage: tuple[str, ...] = ()
    else:
        coverage = tuple(dict.fromkeys(value.strip() for value in raw_coverage))

    raw_turns = record.get("turns")
    if not isinstance(raw_turns, list) or not raw_turns:
        errors.append("turns 必须是非空数组")
        turns: tuple[MultiTurnTurn, ...] = ()
    else:
        turns = tuple(
            _parse_turn(value, turn_index)
            for turn_index, value in enumerate(raw_turns, start=1)
        )
        errors.extend(
            f"{turn.id}: {turn.validation_error}"
            for turn in turns
            if turn.validation_error is not None
        )
        turn_ids = [turn.id for turn in turns]
        if len(turn_ids) != len(set(turn_ids)):
            errors.append("场景内存在重复 turn id")
        if len(turns) < 2:
            errors.append("完整 Conversation 至少包含两轮")
        elif turns[0].expected_outcome != "result_match":
            errors.append("Conversation 第一轮必须建立成功查询状态")

    return MultiTurnCase(
        id=case_id,
        description=description,
        coverage=coverage,
        turns=turns,
        validation_error="；".join(errors) or None,
    )


def _parse_turn(record: object, index: int) -> MultiTurnTurn:
    if not isinstance(record, dict):
        return MultiTurnTurn(
            id=f"turn-{index}",
            question="",
            validation_error="轮次必须是 JSON 对象",
        )

    errors: list[str] = []
    turn_id = _required_text(record.get("id"), "turn.id", errors) or f"turn-{index}"
    question = _required_text(record.get("question"), "question", errors)
    expected_outcome = record.get("expected_outcome", "result_match")
    if not isinstance(expected_outcome, str) or expected_outcome not in _OUTCOMES:
        errors.append("expected_outcome 无效")
        expected_outcome = "result_match"

    expected_sql_value = record.get("expected_sql", "")
    if not isinstance(expected_sql_value, str):
        errors.append("expected_sql 必須是字符串")
        expected_sql = ""
    else:
        expected_sql = expected_sql_value.strip()

    raw_error_code = record.get("expected_error_code")
    expected_error_code = (
        raw_error_code.strip() if isinstance(raw_error_code, str) else None
    )
    if expected_outcome == "result_match":
        if not expected_sql:
            errors.append("result_match 轮次缺少 expected_sql")
        if expected_error_code is not None:
            errors.append("result_match 轮次不能设置 expected_error_code")
    else:
        if expected_sql:
            errors.append("失败 outcome 轮次不能设置 expected_sql")
        if not expected_error_code:
            errors.append("失败轮次缺少 expected_error_code")
        elif expected_error_code not in _VALID_ERROR_CODES:
            errors.append("expected_error_code 无效")
        expected_code = _OUTCOME_ERROR_CODES.get(expected_outcome)
        if expected_code is not None and expected_error_code != expected_code:
            errors.append(
                f"{expected_outcome} 的 expected_error_code 必须为 {expected_code}"
            )

    order_sensitive = record.get("order_sensitive", False)
    if not isinstance(order_sensitive, bool):
        errors.append("order_sensitive 必须是布尔值")
        order_sensitive = False

    return MultiTurnTurn(
        id=turn_id,
        question=question,
        expected_sql=expected_sql,
        expected_outcome=expected_outcome,
        expected_error_code=expected_error_code,
        order_sensitive=order_sensitive,
        validation_error="；".join(errors) or None,
    )


def _prepare_references(
    case: MultiTurnCase,
    *,
    query_executor: QueryExecutor,
    context: QueryContext,
) -> tuple[dict[str, QueryData], tuple[str, str] | None]:
    references: dict[str, QueryData] = {}
    for turn in case.turns:
        if turn.expected_outcome != "result_match":
            continue
        try:
            standard_sql: ValidatedSQL = validate_sql(turn.expected_sql, context)
            result = query_executor.execute(standard_sql)
        except Exception:
            return {}, ("标准 SQL 未通过安全校验或无法执行", turn.id)
        if result.truncated:
            return {}, ("标准结果被截断", turn.id)
        references[_reference_id(case.id, turn.id)] = result
    return references, None


def _evaluate_success_turn(
    turn: MultiTurnTurn,
    result: object,
    response_conversation_id: str | None,
    current_conversation_id: str | None,
    expected: QueryData,
    *,
    duration_ms: int,
    order_sensitive: bool,
) -> tuple[MultiTurnTurnEvaluation, str | None]:
    if isinstance(result, QueryFailure):
        return (
            _turn_result(
                turn,
                MultiTurnStatus.FAIL,
                f"期望查询结果，实际错误码为 {result.error_code.value}",
                query_error_code=result.error_code.value,
                duration_ms=duration_ms,
            ),
            None,
        )
    if not isinstance(result, QuerySuccess):
        return (
            _turn_result(
                turn,
                MultiTurnStatus.FAIL,
                "Query API 返回类型无效",
                duration_ms=duration_ms,
            ),
            None,
        )
    if result.truncated:
        return (
            _turn_result(
                turn,
                MultiTurnStatus.INVALID_CASE,
                "系统结果被截断",
                duration_ms=duration_ms,
                generated_sql=result.sql,
            ),
            None,
        )
    if not response_conversation_id:
        return (
            _turn_result(
                turn,
                MultiTurnStatus.FAIL,
                "成功查询没有返回 conversation_id",
                duration_ms=duration_ms,
            ),
            None,
        )
    if (
        current_conversation_id is not None
        and response_conversation_id != current_conversation_id
    ):
        return (
            _turn_result(
                turn,
                MultiTurnStatus.FAIL,
                "同一 Conversation 的 conversation_id 发生变化",
                duration_ms=duration_ms,
            ),
            None,
        )

    actual = QueryData(
        columns=result.columns,
        rows=result.rows,
        truncated=result.truncated,
    )
    matched = results_match(
        actual,
        expected,
        order_sensitive=order_sensitive,
        normalize_json_numeric_strings=True,
    )
    return (
        _turn_result(
            turn,
            MultiTurnStatus.PASS if matched else MultiTurnStatus.FAIL,
            None if matched else "执行结果与标准 SQL 不一致",
            duration_ms=duration_ms,
            generated_sql=result.sql,
        ),
        response_conversation_id,
    )


def _evaluate_failure_turn(
    turn: MultiTurnTurn,
    result: object,
    response_conversation_id: str | None,
    *,
    duration_ms: int,
) -> MultiTurnTurnEvaluation:
    expected_code = turn.expected_error_code
    if isinstance(result, QueryFailure):
        if (
            result.error_code.value == expected_code
            and response_conversation_id is None
        ):
            return _turn_result(
                turn,
                MultiTurnStatus.PASS,
                None,
                query_error_code=result.error_code.value,
                duration_ms=duration_ms,
            )
        reason = (
            f"期望错误码 {expected_code}，实际为 {result.error_code.value}"
            if result.error_code.value != expected_code
            else "失败轮次意外返回 conversation_id"
        )
        return _turn_result(
            turn,
            MultiTurnStatus.FAIL,
            reason,
            query_error_code=result.error_code.value,
            duration_ms=duration_ms,
        )
    if isinstance(result, QuerySuccess):
        return _turn_result(
            turn,
            MultiTurnStatus.FAIL,
            f"期望错误码 {expected_code}，实际返回查询结果",
            duration_ms=duration_ms,
            generated_sql=result.sql,
        )
    return _turn_result(
        turn,
        MultiTurnStatus.FAIL,
        "Query API 返回类型无效",
        duration_ms=duration_ms,
    )


def _turn_result(
    turn: MultiTurnTurn,
    status: MultiTurnStatus,
    failure_reason: str | None,
    *,
    query_error_code: str | None = None,
    duration_ms: int = 0,
    generated_sql: str | None = None,
) -> MultiTurnTurnEvaluation:
    return MultiTurnTurnEvaluation(
        turn_id=turn.id,
        question=turn.question,
        expected_outcome=turn.expected_outcome,
        expected_error_code=turn.expected_error_code,
        status=status,
        query_error_code=query_error_code,
        failure_reason=failure_reason,
        duration_ms=duration_ms,
        generated_sql=generated_sql,
    )


def _invalid_conversation(
    case: MultiTurnCase,
    reason: str,
    *,
    invalid_turn_id: str | None = None,
) -> MultiTurnCaseEvaluation:
    turns = tuple(
        _turn_result(
            turn,
            MultiTurnStatus.INVALID_CASE
            if invalid_turn_id is None or turn.id == invalid_turn_id
            else MultiTurnStatus.FAIL,
            reason
            if invalid_turn_id is None or turn.id == invalid_turn_id
            else "场景标准案例无效",
        )
        for turn in case.turns
    )
    return MultiTurnCaseEvaluation(
        case_id=case.id,
        coverage=case.coverage,
        status=MultiTurnStatus.INVALID_CASE,
        failure_reason=reason,
        turns=turns,
    )


def _failed_conversation(case: MultiTurnCase, reason: str) -> MultiTurnCaseEvaluation:
    turns = tuple(
        _turn_result(turn, MultiTurnStatus.FAIL, reason) for turn in case.turns
    )
    return MultiTurnCaseEvaluation(
        case_id=case.id,
        coverage=case.coverage,
        status=MultiTurnStatus.FAIL,
        failure_reason=reason,
        turns=turns,
    )


def _conversation_result(
    case: MultiTurnCase,
    turns: tuple[MultiTurnTurnEvaluation, ...],
) -> MultiTurnCaseEvaluation:
    if any(turn.status is MultiTurnStatus.INVALID_CASE for turn in turns):
        status = MultiTurnStatus.INVALID_CASE
    elif all(turn.status is MultiTurnStatus.PASS for turn in turns):
        status = MultiTurnStatus.PASS
    else:
        status = MultiTurnStatus.FAIL
    failed_turn = next(
        (turn for turn in turns if turn.status is not MultiTurnStatus.PASS),
        None,
    )
    return MultiTurnCaseEvaluation(
        case_id=case.id,
        coverage=case.coverage,
        status=status,
        failure_reason=(failed_turn.failure_reason if failed_turn else None),
        turns=turns,
    )


def _summarize(
    cases: tuple[MultiTurnCaseEvaluation, ...],
) -> MultiTurnEvaluationSummary:
    valid_cases = [
        case for case in cases if case.status is not MultiTurnStatus.INVALID_CASE
    ]
    passed_conversations = sum(
        case.status is MultiTurnStatus.PASS for case in valid_cases
    )
    failed_conversations = len(valid_cases) - passed_conversations
    valid_turns = [
        turn
        for case in valid_cases
        for turn in case.turns
        if turn.status is not MultiTurnStatus.INVALID_CASE
    ]
    execution_turns = [
        turn for turn in valid_turns if turn.expected_outcome == "result_match"
    ]
    outcome_turns = [
        turn for turn in valid_turns if turn.expected_outcome != "result_match"
    ]
    passed_execution = sum(
        turn.status is MultiTurnStatus.PASS for turn in execution_turns
    )
    passed_outcomes = sum(turn.status is MultiTurnStatus.PASS for turn in outcome_turns)
    passed_turns = sum(turn.status is MultiTurnStatus.PASS for turn in valid_turns)
    failed_turns = len(valid_turns) - passed_turns

    coverage_accuracy: dict[str, float | None] = {}
    for tag in sorted({tag for case in cases for tag in case.coverage}):
        tagged = [case for case in valid_cases if tag in case.coverage]
        passed = sum(case.status is MultiTurnStatus.PASS for case in tagged)
        coverage_accuracy[tag] = passed / len(tagged) if tagged else None

    invalid_turns = sum(
        turn.status is MultiTurnStatus.INVALID_CASE
        for case in cases
        for turn in case.turns
    )
    total_turns = sum(len(case.turns) for case in cases)
    return MultiTurnEvaluationSummary(
        total_conversations=len(cases),
        valid_conversations=len(valid_cases),
        passed_conversations=passed_conversations,
        failed_conversations=failed_conversations,
        invalid_conversations=len(cases) - len(valid_cases),
        conversation_accuracy=(
            passed_conversations / len(valid_cases) if valid_cases else None
        ),
        total_turns=total_turns,
        valid_turns=len(valid_turns),
        passed_turns=passed_turns,
        failed_turns=failed_turns,
        invalid_turns=invalid_turns,
        execution_turns=len(execution_turns),
        execution_passed=passed_execution,
        execution_accuracy=(
            passed_execution / len(execution_turns) if execution_turns else None
        ),
        outcome_turns=len(outcome_turns),
        outcome_passed=passed_outcomes,
        outcome_accuracy=(
            passed_outcomes / len(outcome_turns) if outcome_turns else None
        ),
        coverage_accuracy=coverage_accuracy,
    )


def _required_text(value: object, field_name: str, errors: list[str]) -> str:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"缺少有效的 {field_name}")
        return ""
    return value.strip()


def _reference_id(case_id: str, turn_id: str) -> str:
    return f"{case_id}/{turn_id}"


def _duration_ms(started: float) -> int:
    return max(0, round((perf_counter() - started) * 1000))


def _close_client(client: ConversationQueryClient) -> None:
    close = getattr(client, "close", None)
    if callable(close):
        try:
            close()
        except Exception:
            pass


__all__ = [
    "ConversationResponse",
    "MultiTurnCase",
    "MultiTurnEvaluationLoadError",
    "MultiTurnEvaluationRun",
    "MultiTurnStatus",
    "MultiTurnTurn",
    "load_multi_turn_cases",
    "run_multi_turn_evaluation",
]
