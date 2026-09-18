"""Online Retrieval（在线检索）公共入口和高层编排。"""

from src.observability.contracts import TraceRecorder
from src.observability.tracing import create_trace_recorder

from ..contracts import (
    OnlineRetrievalResult,
    RetrievalConfig,
    RetrievalRequest,
    RetrievalStatus,
)
from ..query_understanding import ValidatedSemanticQuery
from .rag_runtime import RagRuntime
from .resource_retrieval import (
    _contains_required_columns,
    _missing_required_column_details,
)
from .retrieval_join_stage import _assemble_success, _resolve_join
from .retrieval_pipeline import (
    _ColumnStage,
    _ResourceStage,
    _RetrievalExecution,
)
from .retrieval_resource_stage import (
    _resolve_snapshot,
    _retrieve_columns,
    _retrieve_resources,
)
from .retrieval_results import result as _result
from .retrieval_selection import grouping_text_from_dimensions


class OnlineRetriever:
    """使用一个 RAG Runtime 完成单次同步在线检索。"""

    def __init__(
        self,
        runtime: RagRuntime,
        *,
        config: RetrievalConfig | None = None,
        trace_recorder: TraceRecorder | None = None,
    ) -> None:
        self._runtime = runtime
        self._config = config or RetrievalConfig()
        if trace_recorder is not None:
            self._trace_recorder = trace_recorder
        else:
            try:
                self._trace_recorder = create_trace_recorder()
            except Exception:
                self._trace_recorder = None
        self._execution = _RetrievalExecution(
            runtime=self._runtime,
            config=self._config,
            trace_recorder=self._trace_recorder,
        )

    def retrieve(self, request: RetrievalRequest) -> OnlineRetrievalResult:
        """消费结构化查询，执行 TABLE、COLUMN、METRIC 和关系解析流水线。"""

        if not isinstance(request, RetrievalRequest):
            raise TypeError("OnlineRetriever.retrieve 需要 RetrievalRequest")
        return self._retrieve_request(request)

    def _retrieve_request(
        self,
        request: RetrievalRequest,
    ) -> OnlineRetrievalResult:
        """在同一条链路中处理 metrics = 0 / 1 / N。"""

        if request.semantic_query is None:
            raise ValueError("RetrievalRequest 缺少 ValidatedSemanticQuery")
        if not isinstance(request.question, str) or not request.question.strip():
            raise ValueError("检索问题不能为空")
        semantic_query: ValidatedSemanticQuery = request.semantic_query
        grouping_text = grouping_text_from_dimensions(semantic_query.dimensions)

        snapshot, failure = _resolve_snapshot(self._execution, request)
        if failure is not None:
            return failure
        assert snapshot is not None

        resources, failure = _retrieve_resources(
            self._execution,
            request,
            semantic_query,
            snapshot,
        )
        if failure is not None:
            return failure
        assert resources is not None

        resource_failure = self._validate_resources(request, resources)
        if resource_failure is not None:
            return resource_failure

        columns, failure = _retrieve_columns(
            self._execution,
            request,
            semantic_query,
            grouping_text,
            resources,
        )
        if failure is not None:
            return failure
        assert columns is not None

        column_failure = self._validate_columns(request, resources, columns)
        if column_failure is not None:
            return column_failure

        join, failure = _resolve_join(self._execution, request, resources, columns)
        if failure is not None:
            return failure
        assert join is not None
        return _assemble_success(self._execution, request, resources, columns, join)

    @staticmethod
    def _validate_resources(
        request: RetrievalRequest,
        resources: _ResourceStage,
    ) -> OnlineRetrievalResult | None:
        if not resources.table_hits:
            return _result(
                RetrievalStatus.NO_TABLE_HIT,
                resources.snapshot.asset_version,
                evidence=resources.evidence,
                warnings=("TABLE 检索没有超过阈值的有效候选",),
                request=request,
                metric_constraints=resources.metric_constraints,
            )

        metric_table = (
            resources.metric_constraints[0].data_source
            if resources.metric_constraints
            else None
        )
        if metric_table is not None and not any(
            hit.qualified_name == metric_table for hit in resources.table_hits
        ):
            return _result(
                RetrievalStatus.NO_TABLE_HIT,
                resources.snapshot.asset_version,
                tables=resources.table_hits,
                metrics=resources.selected_metrics,
                evidence=resources.evidence,
                warnings=("指标 data_source 没有被 TABLE 路线命中",),
                request=request,
                metric_constraints=resources.metric_constraints,
            )
        return None

    @staticmethod
    def _validate_columns(
        request: RetrievalRequest,
        resources: _ResourceStage,
        columns: _ColumnStage,
    ) -> OnlineRetrievalResult | None:
        if not columns.column_hits:
            return _result(
                RetrievalStatus.NO_REQUIRED_COLUMN_HIT,
                resources.snapshot.asset_version,
                tables=resources.table_hits,
                fields=columns.column_hits,
                metrics=resources.selected_metrics,
                evidence=columns.evidence,
                warnings=("COLUMN 检索没有超过阈值的有效候选",),
                request=request,
                metric_constraints=resources.metric_constraints,
            )

        if resources.selected_metrics and not _contains_required_columns(
            columns.column_hits,
            columns.required,
        ):
            missing_details = _missing_required_column_details(
                resources.selected_metrics,
                columns.time_field,
                columns.column_hits,
            )
            return _result(
                RetrievalStatus.NO_REQUIRED_COLUMN_HIT,
                resources.snapshot.asset_version,
                tables=resources.table_hits,
                fields=columns.column_hits,
                metrics=resources.selected_metrics,
                evidence=columns.evidence,
                warnings=(
                    "至少一个指标的必需字段没有被 COLUMN 有效命中",
                    *missing_details,
                ),
                request=request,
                metric_constraints=resources.metric_constraints,
            )
        return None
