"""Business Analysis Application Workflow（经营分析应用流程）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from src.online_query.contracts import QueryErrorCode, QueryFailure

if TYPE_CHECKING:
    from src.authorization.contracts import AuthContext

from .contracts import (
    AnalysisDecompositionContext,
    AnalysisPlanCannotAnswer,
    AnalysisPlanClarificationRequired,
    AnalysisPlanError,
    AnalysisPlanLLMError,
    AnalysisSemanticCatalog,
)
from .decomposer import AnalysisPlanDecomposer
from .execution import TaskExecutor, TaskResult, TaskSemanticAdapter
from .planning import validate_analysis_plan
from .reporting import AnalysisReportError, BusinessAnalysisReport


class AnalysisContextProvider(Protocol):
    def __call__(self) -> AnalysisDecompositionContext:
        """读取当前已确认的经营分析语义上下文。"""


class AnalysisSummarizer(Protocol):
    def summarize(
        self,
        question: str,
        task_results: tuple[TaskResult, ...],
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


AnalysisResult = BusinessAnalysisSuccess | QueryFailure


class BusinessAnalysisApplication:
    """编排计划、授权 Task 执行和报告汇总，不拥有底层查询事实。"""

    def __init__(
        self,
        authorized_query_service: AuthorizedQueryEntry,
        *,
        decomposer: AnalysisPlanDecomposer,
        summarizer: AnalysisSummarizer,
        context_provider: AnalysisContextProvider,
        adapter: TaskSemanticAdapter | None = None,
    ) -> None:
        self._authorized_query_service = authorized_query_service
        self._decomposer = decomposer
        self._summarizer = summarizer
        self._context_provider = context_provider
        self._adapter = adapter or TaskSemanticAdapter()

    def analyze(
        self,
        question: str,
        *,
        request_id: str,
        auth_context: AuthContext,
    ) -> AnalysisResult:
        try:
            context = self._context_provider()
            catalog = AnalysisSemanticCatalog.from_records(
                context.metric_records,
                context.dimensions,
            )
        except Exception:
            return _failure(
                request_id,
                QueryErrorCode.CONTEXT_ERROR,
                reason="ANALYSIS_CONTEXT_UNAVAILABLE",
            )

        try:
            candidate = self._decomposer.decompose(question, context)
        except AnalysisPlanLLMError as exc:
            return _failure(
                request_id,
                QueryErrorCode.LLM_ERROR,
                reason=exc.reason,
            )
        except Exception:
            return _failure(
                request_id,
                QueryErrorCode.LLM_ERROR,
                reason="DECOMPOSER_FAILURE",
            )

        try:
            plan = validate_analysis_plan(candidate, catalog)
        except AnalysisPlanClarificationRequired as exc:
            return _failure(
                request_id,
                QueryErrorCode.CLARIFICATION_REQUIRED,
                reason=exc.reason,
            )
        except AnalysisPlanCannotAnswer as exc:
            return _failure(
                request_id,
                QueryErrorCode.CANNOT_ANSWER,
                reason=exc.reason,
            )
        except AnalysisPlanError as exc:
            return _failure(
                request_id,
                QueryErrorCode.CONTEXT_ERROR,
                reason=exc.reason,
            )
        except Exception:
            return _failure(
                request_id,
                QueryErrorCode.CONTEXT_ERROR,
                reason="PLAN_VALIDATION_FAILURE",
            )

        try:
            bound_query_service = self._authorized_query_service.bind(auth_context)
            task_results = TaskExecutor(
                bound_query_service,
                self._adapter,
            ).execute(plan, request_id=request_id)
            report = self._summarizer.summarize(question, task_results)
        except AnalysisReportError as exc:
            error_code = _report_error_code(exc.code)
            return _failure(request_id, error_code, reason=exc.reason)
        except Exception:
            return _failure(
                request_id,
                QueryErrorCode.CONTEXT_ERROR,
                reason="ANALYSIS_EXECUTION_FAILURE",
            )

        return BusinessAnalysisSuccess(
            request_id=request_id,
            report=report,
            task_results=task_results,
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
        QueryErrorCode.CLARIFICATION_REQUIRED: "请明确经营分析中的指标或维度口径",
        QueryErrorCode.CANNOT_ANSWER: "当前经营分析计划无法安全执行",
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
