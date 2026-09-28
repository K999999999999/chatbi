"""经营分析 StateGraph 应用流程。"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from threading import Event, Thread
from typing import Protocol, TypedDict
from uuid import UUID, uuid4

from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime

from src.authorization.contracts import AuthContext
from src.online_query.contracts import QueryErrorCode, QueryFailure

from .attribution import (
    AttributionError,
    BusinessAnalysisAttribution,
    calculate_product_attribution,
)
from .contracts import (
    AnalysisDecompositionContext,
    AnalysisPlan,
    AnalysisPlanCannotAnswer,
    AnalysisPlanClarificationRequired,
    AnalysisPlanError,
    AnalysisRequest,
    AnalysisRequestCandidate,
    AnalysisRequestExtractionError,
    AnalysisSemanticCatalog,
)
from .decomposer import AnalysisRequestExtractor
from .execution import TaskExecutor, TaskResult, TaskSemanticAdapter, TaskStatus
from .planning import build_comparison_plan
from .reporting import AnalysisReportError, BusinessAnalysisReport
from .run_store import (
    AnalysisRunConflict,
    AnalysisRunStatus,
    PostgresAnalysisRunStore,
)


class AnalysisRunContext(TypedDict):
    """一次分析运行所需的认证和请求上下文。"""

    request_id: str
    auth_context: AuthContext


class AnalysisRunState(TypedDict, total=False):
    """LangGraph 节点间的单次经营分析状态。"""

    question: str
    decomposition_context: AnalysisDecompositionContext
    catalog: AnalysisSemanticCatalog
    candidate: AnalysisRequestCandidate
    analysis_request: AnalysisRequest
    plan: AnalysisPlan
    task_results: tuple[TaskResult, ...]
    attribution: BusinessAnalysisAttribution
    report: BusinessAnalysisReport
    failure: QueryFailure


class AnalysisContextProvider(Protocol):
    """加载当前已确认的经营分析语义上下文。"""

    def __call__(self) -> AnalysisDecompositionContext:
        """加载当前已确认的经营分析语义上下文。"""


class AnalysisSummarizer(Protocol):
    def summarize(
        self,
        question: str,
        task_results: tuple[TaskResult, ...],
        attribution: BusinessAnalysisAttribution,
    ) -> BusinessAnalysisReport:
        """根据结构化 TaskResult 生成报告。"""


class AuthorizedQueryEntry(Protocol):
    def bind(self, auth_context: AuthContext) -> object:
        """将当前身份绑定到内部查询入口。"""


@dataclass(frozen=True, slots=True)
class BusinessAnalysisSuccess:
    request_id: str
    report: BusinessAnalysisReport
    task_results: tuple[TaskResult, ...]
    analysis_run_id: str | None = None
    attribution: BusinessAnalysisAttribution | None = None
    # 仅供内部 Evaluation 使用；HTTP Response 不序列化该字段。
    plan: AnalysisPlan | None = None


AnalysisResult = BusinessAnalysisSuccess | QueryFailure
_LOGGER = logging.getLogger(__name__)


class BusinessAnalysisApplication:
    """用 StateGraph 编排提取、校验、查询和总结。"""

    def __init__(
        self,
        authorized_query_service: AuthorizedQueryEntry,
        *,
        decomposer: AnalysisRequestExtractor,
        summarizer: AnalysisSummarizer,
        context_provider: AnalysisContextProvider,
        adapter: TaskSemanticAdapter | None = None,
        checkpointer: object | None = None,
        run_store: PostgresAnalysisRunStore | None = None,
    ) -> None:
        self._authorized_query_service = authorized_query_service
        self._decomposer = decomposer
        self._summarizer = summarizer
        self._context_provider = context_provider
        self._adapter = adapter or TaskSemanticAdapter()
        self._checkpointer = checkpointer
        self._run_store = run_store
        if (checkpointer is None) != (run_store is None):
            raise ValueError("checkpoint 与运行登记必须同时配置")
        self._graph = self._build_graph()
        self._cleanup_stop: Event | None = None
        self._cleanup_thread: Thread | None = None
        if isinstance(run_store, PostgresAnalysisRunStore):
            self._cleanup_stop = Event()
            self._cleanup_thread = Thread(
                target=_cleanup_expired_runs,
                args=(run_store, self._cleanup_stop),
                name="business-analysis-checkpoint-cleanup",
                daemon=True,
            )
            self._cleanup_thread.start()

    def close(self) -> None:
        """释放生产装配持有的 checkpoint 和运行登记连接池。"""

        if self._cleanup_stop is not None:
            self._cleanup_stop.set()
        if self._cleanup_thread is not None:
            self._cleanup_thread.join(timeout=2)
        if self._run_store is not None:
            close_store = getattr(self._run_store, "close", None)
            if callable(close_store):
                close_store()
        connection_pool = getattr(self._checkpointer, "conn", None)
        close = getattr(connection_pool, "close", None)
        if callable(close):
            close()

    def analyze(
        self,
        question: str,
        *,
        request_id: str,
        auth_context: AuthContext,
        analysis_run_id: str | None = None,
    ) -> AnalysisResult:
        run_id = _analysis_run_uuid(analysis_run_id, request_id=request_id)
        if isinstance(run_id, QueryFailure):
            return run_id
        if self._run_store is not None:
            try:
                self._run_store.cleanup_expired()
                run = self._run_store.claim(
                    run_id,
                    owner_subject=_owner_subject(auth_context),
                    question=question,
                )
            except AnalysisRunConflict as exc:
                return _failure(
                    request_id,
                    QueryErrorCode.CANNOT_ANSWER,
                    reason=exc.reason,
                )
            except Exception:
                return _failure(
                    request_id,
                    QueryErrorCode.CONTEXT_ERROR,
                    reason="ANALYSIS_RUN_STORE_UNAVAILABLE",
                )
            if run.status == AnalysisRunStatus.COMPLETED:
                return self._completed_result(run_id, request_id)

        config = {
            "configurable": {"thread_id": str(run_id)},
            "metadata": {"analysis_run_id": str(run_id)},
        }
        try:
            state = self._graph.invoke(
                {"question": question},
                context={"request_id": request_id, "auth_context": auth_context},
                config=config,
            )
        except Exception:
            return _failure(
                request_id,
                QueryErrorCode.CONTEXT_ERROR,
                reason="ANALYSIS_GRAPH_FAILURE",
            )

        failure = state.get("failure")
        if isinstance(failure, QueryFailure):
            if self._run_store is not None and not _retryable_failure(
                failure,
                state.get("task_results", ()),
            ):
                self._run_store.mark_completed(run_id)
            return failure
        plan = state.get("plan")
        task_results = state.get("task_results", ())
        attribution = state.get("attribution")
        report = state.get("report")
        if (
            not isinstance(plan, AnalysisPlan)
            or not isinstance(attribution, BusinessAnalysisAttribution)
            or not isinstance(report, BusinessAnalysisReport)
        ):
            return _failure(
                request_id,
                QueryErrorCode.CONTEXT_ERROR,
                reason="ANALYSIS_GRAPH_OUTPUT_INVALID",
            )
        if self._run_store is not None:
            try:
                self._run_store.mark_completed(run_id)
            except Exception:
                return _failure(
                    request_id,
                    QueryErrorCode.CONTEXT_ERROR,
                    reason="ANALYSIS_RUN_STORE_UNAVAILABLE",
                )
        return BusinessAnalysisSuccess(
            request_id=request_id,
            report=report,
            task_results=task_results,
            analysis_run_id=str(run_id),
            attribution=attribution,
            plan=plan,
        )

    def _completed_result(self, run_id: UUID, request_id: str) -> AnalysisResult:
        try:
            snapshot = self._graph.get_state(
                {"configurable": {"thread_id": str(run_id)}}
            )
            state = snapshot.values
        except Exception:
            return _failure(
                request_id,
                QueryErrorCode.CONTEXT_ERROR,
                reason="ANALYSIS_CHECKPOINT_UNAVAILABLE",
            )
        failure = state.get("failure")
        if isinstance(failure, QueryFailure):
            return QueryFailure(
                request_id=request_id,
                error_code=failure.error_code,
                error_message=failure.error_message,
                failure_stage=failure.failure_stage,
                internal_reason=failure.internal_reason,
            )
        report = state.get("report")
        plan = state.get("plan")
        attribution = state.get("attribution")
        if not isinstance(report, BusinessAnalysisReport) or not isinstance(
            attribution, BusinessAnalysisAttribution
        ):
            return _failure(
                request_id,
                QueryErrorCode.CONTEXT_ERROR,
                reason="ANALYSIS_CHECKPOINT_OUTPUT_INVALID",
            )
        return BusinessAnalysisSuccess(
            request_id=request_id,
            report=report,
            task_results=state.get("task_results", ()),
            analysis_run_id=str(run_id),
            attribution=attribution,
            plan=plan if isinstance(plan, AnalysisPlan) else None,
        )

    def _build_graph(self):
        builder = StateGraph(AnalysisRunState, context_schema=AnalysisRunContext)
        builder.add_node("extract", self._extract_request)
        builder.add_node("validate", self._validate_request)
        builder.add_node("execute", self._execute_tasks)
        builder.add_node("attribute", self._attribute_results)
        builder.add_node("summarize", self._summarize_results)
        builder.add_edge(START, "extract")
        builder.add_edge("extract", "validate")
        builder.add_conditional_edges(
            "validate",
            _route_after_node,
            {"continue": "execute", "finish": END},
        )
        builder.add_conditional_edges(
            "execute",
            _route_after_task,
            {"execute": "execute", "attribute": "attribute", "finish": END},
        )
        builder.add_conditional_edges(
            "attribute",
            _route_after_node,
            {"continue": "summarize", "finish": END},
        )
        builder.add_edge("summarize", END)
        return builder.compile(checkpointer=self._checkpointer)

    def _extract_request(
        self,
        state: AnalysisRunState,
        runtime: Runtime[AnalysisRunContext],
    ) -> dict[str, object]:
        if isinstance(state.get("analysis_request"), AnalysisRequest) and isinstance(
            state.get("plan"), AnalysisPlan
        ):
            return {"failure": None}
        question = state.get("question", "")
        try:
            context = self._context_provider()
            catalog = AnalysisSemanticCatalog.from_records(
                context.metric_records,
                context.dimensions,
            )
        except Exception:
            return {
                "failure": _failure(
                    runtime.context["request_id"],
                    QueryErrorCode.CONTEXT_ERROR,
                    reason="ANALYSIS_CONTEXT_UNAVAILABLE",
                )
            }

        try:
            candidate = self._decomposer.decompose(question, context)
        except AnalysisRequestExtractionError as exc:
            return {
                "failure": _failure(
                    runtime.context["request_id"],
                    QueryErrorCode.LLM_ERROR,
                    reason=exc.reason,
                )
            }
        except Exception:
            return {
                "failure": _failure(
                    runtime.context["request_id"],
                    QueryErrorCode.LLM_ERROR,
                    reason="DECOMPOSER_FAILURE",
                )
            }
        return {
            "decomposition_context": context,
            "catalog": catalog,
            "candidate": candidate,
        }

    def _validate_request(
        self,
        state: AnalysisRunState,
        runtime: Runtime[AnalysisRunContext],
    ) -> dict[str, object]:
        if isinstance(state.get("failure"), QueryFailure):
            return {}
        if isinstance(state.get("analysis_request"), AnalysisRequest) and isinstance(
            state.get("plan"), AnalysisPlan
        ):
            return {"failure": None}
        try:
            request, plan = build_comparison_plan(
                state["candidate"],
                state["catalog"],
                question=state["question"],
            )
        except AnalysisPlanClarificationRequired as exc:
            return {
                "failure": _failure(
                    runtime.context["request_id"],
                    QueryErrorCode.CLARIFICATION_REQUIRED,
                    reason=exc.reason,
                )
            }
        except AnalysisPlanCannotAnswer as exc:
            return {
                "failure": _failure(
                    runtime.context["request_id"],
                    QueryErrorCode.CANNOT_ANSWER,
                    reason=exc.reason,
                )
            }
        except AnalysisPlanError as exc:
            return {
                "failure": _failure(
                    runtime.context["request_id"],
                    QueryErrorCode.CONTEXT_ERROR,
                    reason=exc.reason,
                )
            }
        except Exception:
            return {
                "failure": _failure(
                    runtime.context["request_id"],
                    QueryErrorCode.CONTEXT_ERROR,
                    reason="PLAN_VALIDATION_FAILURE",
                )
            }
        return {"analysis_request": request, "plan": plan}

    def _execute_tasks(
        self,
        state: AnalysisRunState,
        runtime: Runtime[AnalysisRunContext],
    ) -> dict[str, object]:
        try:
            bound_query_service = self._authorized_query_service.bind(
                runtime.context["auth_context"]
            )
            executor = TaskExecutor(
                bound_query_service,
                self._adapter,
            )
        except Exception:
            return {
                "failure": _failure(
                    runtime.context["request_id"],
                    QueryErrorCode.CONTEXT_ERROR,
                    reason="ANALYSIS_EXECUTION_FAILURE",
                )
            }

        previous = {result.task_id: result for result in state.get("task_results", ())}
        task = next(
            (
                item
                for item in state["plan"].tasks
                if item.task_id not in previous
                or previous[item.task_id].status is not TaskStatus.COMPLETED
                or previous[item.task_id].truncated
            ),
            None,
        )
        if task is None:
            return {
                "task_results": tuple(
                    previous[item.task_id] for item in state["plan"].tasks
                )
            }

        result = executor.execute_one(
            task,
            request_id=runtime.context["request_id"],
        )
        if result.status is TaskStatus.FAILED and _retryable_task_result(result):
            result = executor.execute_one(
                task,
                request_id=runtime.context["request_id"],
            )
        previous[task.task_id] = result
        task_results = tuple(
            previous[item.task_id]
            for item in state["plan"].tasks
            if item.task_id in previous
        )
        if result.status is not TaskStatus.COMPLETED or result.truncated:
            return {
                "task_results": task_results,
                "failure": _failure(
                    runtime.context["request_id"],
                    QueryErrorCode.CANNOT_ANSWER,
                    reason=(
                        "ANALYSIS_TASK_TRUNCATED"
                        if result.truncated
                        else "ANALYSIS_TASK_FAILED"
                    ),
                ),
            }
        return {"task_results": task_results, "failure": None}

    def _summarize_results(
        self,
        state: AnalysisRunState,
        runtime: Runtime[AnalysisRunContext],
    ) -> dict[str, object]:
        try:
            report = self._summarizer.summarize(
                state["question"],
                state["task_results"],
                state["attribution"],
            )
        except AnalysisReportError as exc:
            return {
                "failure": _failure(
                    runtime.context["request_id"],
                    _report_error_code(exc.code),
                    reason=exc.reason,
                )
            }
        except Exception:
            return {
                "failure": _failure(
                    runtime.context["request_id"],
                    QueryErrorCode.CONTEXT_ERROR,
                    reason="ANALYSIS_SUMMARY_FAILURE",
                )
            }
        return {"report": report}

    def _attribute_results(
        self,
        state: AnalysisRunState,
        runtime: Runtime[AnalysisRunContext],
    ) -> dict[str, object]:
        try:
            attribution = calculate_product_attribution(
                state["analysis_request"],
                state["task_results"],
            )
        except AttributionError as exc:
            return {
                "failure": _failure(
                    runtime.context["request_id"],
                    QueryErrorCode.CANNOT_ANSWER,
                    reason=exc.reason,
                )
            }
        except Exception:
            return {
                "failure": _failure(
                    runtime.context["request_id"],
                    QueryErrorCode.CANNOT_ANSWER,
                    reason="ATTRIBUTION_FAILURE",
                )
            }
        return {"attribution": attribution}


def _route_after_node(state: AnalysisRunState) -> str:
    return "finish" if isinstance(state.get("failure"), QueryFailure) else "continue"


def _route_after_task(state: AnalysisRunState) -> str:
    if isinstance(state.get("failure"), QueryFailure):
        return "finish"
    plan = state.get("plan")
    results = state.get("task_results", ())
    if isinstance(plan, AnalysisPlan) and len(results) == len(plan.tasks):
        return "attribute"
    return "execute"


def _retryable_task_result(result: TaskResult) -> bool:
    return result.error is not None and result.error.code in {
        QueryErrorCode.CONTEXT_ERROR.value,
        QueryErrorCode.DATABASE_ERROR.value,
        QueryErrorCode.LLM_ERROR.value,
        QueryErrorCode.QUERY_TIMEOUT.value,
    }


def _retryable_failure(
    failure: QueryFailure,
    task_results: tuple[TaskResult, ...],
) -> bool:
    if any(_retryable_task_result(item) for item in task_results):
        return True
    return failure.error_code in {
        QueryErrorCode.CONTEXT_ERROR,
        QueryErrorCode.DATABASE_ERROR,
        QueryErrorCode.LLM_ERROR,
        QueryErrorCode.QUERY_TIMEOUT,
    }


def _analysis_run_uuid(value: str | None, *, request_id: str) -> UUID | QueryFailure:
    if value is None:
        return uuid4()
    try:
        parsed = UUID(value)
    except (AttributeError, TypeError, ValueError):
        return _failure(
            request_id,
            QueryErrorCode.INVALID_REQUEST,
            reason="ANALYSIS_RUN_ID_INVALID",
        )
    if str(parsed) != value.casefold():
        return _failure(
            request_id,
            QueryErrorCode.INVALID_REQUEST,
            reason="ANALYSIS_RUN_ID_INVALID",
        )
    return parsed


def _owner_subject(auth_context: AuthContext) -> str:
    return f"{auth_context.identity_provider}:{auth_context.subject_id}"


def _cleanup_expired_runs(
    run_store: PostgresAnalysisRunStore,
    stop_event: Event,
) -> None:
    while not stop_event.wait(60):
        try:
            run_store.cleanup_expired()
        except Exception as exc:  # noqa: BLE001 - background cleanup must not stop API.
            _LOGGER.warning(
                "Business Analysis checkpoint cleanup failed: error_type=%s",
                type(exc).__name__,
            )


def _report_error_code(code: str) -> QueryErrorCode:
    if code == QueryErrorCode.LLM_ERROR.value:
        return QueryErrorCode.LLM_ERROR
    return QueryErrorCode.CANNOT_ANSWER


def _failure(
    request_id: str,
    error_code: QueryErrorCode,
    *,
    reason: str,
) -> QueryFailure:
    messages = {
        QueryErrorCode.CLARIFICATION_REQUIRED: "请明确经营分析中的指标或比较时期",
        QueryErrorCode.CANNOT_ANSWER: "当前经营分析无法安全完成",
        QueryErrorCode.CONTEXT_ERROR: "经营分析上下文暂时不可用",
        QueryErrorCode.LLM_ERROR: "经营分析暂时无法生成，请稍后重试",
    }
    return QueryFailure(
        request_id=request_id,
        error_code=error_code,
        error_message=messages.get(error_code, "暂时无法处理当前经营分析"),
        failure_stage="business_analysis",
        internal_reason=reason,
    )
