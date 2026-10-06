"""历史Use Case：持久受理先于执行，成功快照与状态一起提交。"""

import logging
from contextlib import nullcontext

from src.authorization.query_entry import AuthorizedQueryService
from src.business_analysis.application import BusinessAnalysisSuccess
from src.business_analysis.reporting import ReportDraftObserver
from src.business_analysis.run_execution import AnalysisExecutionBusy
from src.online_query.contracts import (
    ExecutionControl,
    ExecutionProgressObserver,
    ExecutionStage,
    ExecutionStopped,
    QueryFailure,
    QueryRequest,
    QuerySuccess,
)
from src.online_query.semantic_state import SemanticCertificationError

from .history_codec import decode_query_state, encode_snapshot, public_snapshot
from .history_contracts import HistoryError, HistoryStore
from .query_response import analysis_payload, query_payload
from .semantic_revision import SemanticRevisionError, revise_history_semantic_query


class HistoryApplication:
    def __init__(
        self,
        store: HistoryStore,
        runtime,
        query_service: AuthorizedQueryService,
        *,
        query_understanding=None,
        certifier=None,
        analysis_service=None,
        analysis_guard=None,
    ):
        self.store, self.runtime, self.query_service = store, runtime, query_service
        self.query_understanding, self.certifier = query_understanding, certifier
        self.analysis_service, self.analysis_guard = analysis_service, analysis_guard

    def restore(self, state):
        semantic = decode_query_state(state)
        if self.certifier is None:
            raise HistoryError("CONTEXT_ERROR", "当前业务认证服务不可用", 422)
        try:
            current = self.certifier(semantic)
        except SemanticCertificationError:
            raise HistoryError(
                "HISTORY_CONTEXT_INCOMPATIBLE",
                "相关业务定义或认证映射已变化，请新开对话",
                422,
            ) from None
        except Exception:  # noqa: BLE001 - retrieval故障不得冒充定义变化
            raise HistoryError(
                "CONTEXT_ERROR", "当前业务上下文暂时不可用", 422
            ) from None
        if current["provenance"] != state["provenance"]:
            changed_sections = sorted(
                key
                for key in set(current["provenance"]) | set(state["provenance"])
                if current["provenance"].get(key) != state["provenance"].get(key)
            )
            logging.getLogger(__name__).warning(
                "History definition compatibility changed: sections=%s",
                ",".join(changed_sections),
            )
            raise HistoryError(
                "HISTORY_CONTEXT_INCOMPATIBLE",
                "相关业务定义或认证映射已变化，请新开对话",
                422,
            )
        return semantic

    def authorize(self, auth, request_id, *, audit=True):
        if auth.user_id is None:
            raise HistoryError("AUTHENTICATION_REQUIRED", "需要本地有效账号", 401)
        request = QueryRequest("历史管理", request_id=request_id)
        rejection = (
            self.query_service.authorize(request, auth_context=auth)
            if audit
            else self.query_service.authorize(
                request, auth_context=auth, write_audit=False
            )
        )
        if rejection is not None:
            code = rejection.error_code.value
            status = (
                401
                if code == "AUTHENTICATION_REQUIRED"
                else 503
                if code == "AUTHENTICATION_UNAVAILABLE"
                else 403
            )
            raise HistoryError(code, rejection.error_message, status)

    def _finish_attempt(self, owner, token, snapshot, error, execution_id=None):
        if execution_id is not None:
            return self.store.finish_execution_attempt(
                owner, token, snapshot, error, execution_id
            )
        return self.store.finish_attempt(owner, token, snapshot, error)

    def create(self, auth, request_id, kind, question, operation_id):
        self.authorize(auth, request_id)
        self.runtime.check()
        return self.store.create(auth.user_id, kind, question, operation_id)

    def header(self, auth, request_id, history_id):
        self.authorize(auth, request_id)
        self.store.header(auth.user_id, history_id)
        try:
            self.runtime.reconcile(history_id)
        except HistoryError as exc:
            if exc.code != "HISTORY_STORAGE_UNAVAILABLE":
                raise
            # guard失效只禁止执行 /回收，已提交快照仍可按当前权限读取。
        return self.store.header(auth.user_id, history_id)

    def turn(self, auth, request_id, history_id, turn_id):
        self.authorize(auth, request_id)
        return self.store.turn(auth.user_id, history_id, turn_id)

    def export_source(self, auth, request_id, source_kind, source_id, turn_id=None):
        self.authorize(auth, request_id)
        return self.store.export_snapshot(auth.user_id, source_kind, source_id, turn_id)

    def delete(self, auth, request_id, history_id, revision):
        self.authorize(auth, request_id)
        self.runtime.check()
        h = self.store.header(auth.user_id, history_id)
        try:
            guard = (
                self.analysis_guard.executing(auth, h.analysis_run_id)
                if h.kind == "analysis" and self.analysis_guard is not None
                else nullcontext()
            )
            with guard:
                self.store.delete_history(
                    auth.user_id,
                    history_id,
                    revision,
                    f"{auth.identity_provider}:{auth.subject_id}",
                )
        except AnalysisExecutionBusy:
            raise HistoryError(
                "HISTORY_BUSY", "原分析运行仍在执行，请稍后刷新", 409
            ) from None

    def resume_analysis(
        self, auth, request_id, history_id, operation_id, revision, *, reauthenticate
    ):
        self.authorize(auth, request_id)
        header = self.store.header(auth.user_id, history_id)
        if header.kind != "analysis":
            raise HistoryError("INVALID_REQUEST", "问数历史不能恢复分析运行", 400)
        if header.last_success_turn_id is not None:
            return self.store.turn(
                auth.user_id, history_id, header.last_success_turn_id
            )
        if not header.analysis_recovery_available:
            raise HistoryError(
                "HISTORY_CONTEXT_INCOMPATIBLE",
                "原分析任务已过期或无法恢复，请新建分析",
                422,
            )
        with self.runtime.executing(history_id):
            accepted = self.store.begin_analysis_attempt(
                auth.user_id,
                history_id,
                operation_id,
                revision,
                request_id,
                self.runtime.epoch,
            )
            return self._execute_attempt(
                auth,
                request_id,
                history_id,
                header.first_question,
                accepted,
                reauthenticate=reauthenticate,
                kind="analysis",
                analysis_run_id=header.analysis_run_id,
            )

    def submit_query(
        self,
        auth,
        request_id,
        history_id,
        question,
        operation_id,
        revision,
        *,
        reauthenticate,
    ):
        self.authorize(auth, request_id)
        header = self.store.header(auth.user_id, history_id)
        if header.kind != "query":
            raise HistoryError("INVALID_REQUEST", "分析历史不能提交问数追问", 400)
        with self.runtime.executing(history_id):
            accepted = self.store.begin_attempt(
                auth.user_id,
                history_id,
                question,
                operation_id,
                revision,
                request_id,
                self.runtime.epoch,
            )
            return self._execute_attempt(
                auth,
                request_id,
                history_id,
                question,
                accepted,
                reauthenticate=reauthenticate,
            )

    def requery(
        self,
        auth,
        request_id,
        source_kind,
        source_id,
        source_turn_id,
        operation_id,
        *,
        reauthenticate,
    ):
        from uuid import uuid4

        self.authorize(auth, request_id)
        new_id = str(uuid4())
        with self.runtime.executing(new_id):
            header, accepted = self.store.begin_requery(
                auth.user_id,
                source_kind,
                source_id,
                source_turn_id,
                operation_id,
                request_id,
                self.runtime.epoch,
                new_id,
            )
            result = self._execute_attempt(
                auth,
                request_id,
                header.id,
                accepted.turn.question,
                accepted,
                reauthenticate=reauthenticate,
                requery=True,
                kind=header.kind,
                analysis_run_id=header.analysis_run_id,
            )
            return self.store.header(auth.user_id, header.id), result

    def _execute_attempt(
        self,
        auth,
        request_id,
        history_id,
        question,
        accepted,
        *,
        reauthenticate,
        requery=False,
        kind="query",
        analysis_run_id=None,
        execution_id=None,
        guard_preowned=False,
        progress_observer: ExecutionProgressObserver | None = None,
        execution_control: ExecutionControl | None = None,
    ):
        if accepted.token is None:
            return accepted.turn
        try:
            guard = (
                self.analysis_guard.executing(auth, analysis_run_id)
                if kind == "analysis"
                and self.analysis_guard is not None
                and not guard_preowned
                else nullcontext()
            )
            with guard:
                return self._complete_attempt(
                    auth,
                    request_id,
                    history_id,
                    question,
                    accepted,
                    reauthenticate=reauthenticate,
                    requery=requery,
                    kind=kind,
                    analysis_run_id=analysis_run_id,
                    execution_id=execution_id,
                    progress_observer=progress_observer,
                    execution_control=execution_control,
                )
        except ExecutionStopped:
            raise
        except AnalysisExecutionBusy:
            self._finish_attempt(
                auth.user_id,
                accepted.token,
                None,
                {
                    "request_id": request_id,
                    "error_code": "HISTORY_BUSY",
                    "error_message": "原分析运行仍在执行，请稍后刷新",
                },
                execution_id,
            )
            raise HistoryError(
                "HISTORY_BUSY",
                "原分析运行仍在执行，请稍后刷新",
                409,
                history_id=history_id,
                turn_id=accepted.turn.id,
            ) from None

    def _complete_attempt(
        self,
        auth,
        request_id,
        history_id,
        question,
        accepted,
        *,
        reauthenticate,
        requery,
        kind,
        analysis_run_id,
        execution_id=None,
        progress_observer: ExecutionProgressObserver | None = None,
        execution_control: ExecutionControl | None = None,
    ):
        token = accepted.token
        finishing = False
        try:
            if execution_control is not None:
                execution_control.checkpoint()
            if requery and kind == "query":
                public_snapshot(accepted.source_snapshot)
                if accepted.base_state is None:
                    raise HistoryError(
                        "HISTORY_CONTEXT_INCOMPATIBLE",
                        "来源缺少完整查询条件，不能重新查询",
                        422,
                    )
            semantic = None
            if accepted.base_state is not None:
                if execution_control is not None:
                    execution_control.checkpoint()
                if not requery and progress_observer is not None:
                    progress_observer.set_stage(ExecutionStage.QUERY_UNDERSTANDING)
                previous = self.restore(accepted.base_state)
                try:
                    semantic = (
                        previous
                        if requery
                        else revise_history_semantic_query(
                            previous,
                            question,
                            query_understanding=self.query_understanding,
                            execution_control=execution_control,
                        )
                    )
                    if execution_control is not None:
                        execution_control.checkpoint()
                except SemanticRevisionError as exc:
                    raise HistoryError(exc.error_code.value, str(exc), 422) from None
            if kind == "analysis":
                if self.analysis_service is None:
                    raise HistoryError("CONTEXT_ERROR", "分析服务暂时不可用", 503)
                analysis_options: dict[str, object] = {}
                if execution_control is not None:
                    analysis_options["execution_control"] = execution_control
                if progress_observer is not None:
                    analysis_options["progress_observer"] = progress_observer
                if isinstance(progress_observer, ReportDraftObserver):
                    analysis_options["report_observer"] = progress_observer
                result = self.analysis_service.analyze(
                    question,
                    request_id=request_id,
                    auth_context=auth,
                    analysis_run_id=analysis_run_id,
                    **analysis_options,
                )
            else:
                result = self.query_service.execute_authorized(
                    QueryRequest(
                        question,
                        request_id=request_id,
                        semantic_query=semantic,
                        require_restorable=True,
                        progress_observer=progress_observer,
                        execution_control=execution_control,
                    ),
                    auth_context=auth,
                )
            if execution_control is not None:
                execution_control.checkpoint()
            current_auth = reauthenticate()
            if current_auth.user_id != auth.user_id:
                raise HistoryError(
                    "AUTHORIZATION_DENIED", "当前身份不可交付该结果", 403
                )
            self.authorize(current_auth, request_id)
            self.runtime.check()
            if isinstance(result, QueryFailure):
                finishing = True
                if execution_control is not None:
                    execution_control.checkpoint()
                if progress_observer is not None:
                    progress_observer.set_stage(ExecutionStage.RESULT_SAVING)
                return self._finish_attempt(
                    auth.user_id,
                    token,
                    None,
                    {
                        "request_id": result.request_id,
                        "error_code": result.error_code.value,
                        "error_message": result.error_message,
                    },
                    execution_id,
                )
            if kind == "analysis" and isinstance(result, BusinessAnalysisSuccess):
                snapshot = encode_snapshot(
                    "analysis",
                    analysis_payload(result, analysis_run_id),
                    original_question=question,
                )
            elif isinstance(result, QuerySuccess) and kind == "query":
                snapshot = encode_snapshot(
                    "query",
                    query_payload(result),
                    query_state=result.restoration_state,
                    source_question=question,
                )
            else:
                raise HistoryError(
                    "HISTORY_SNAPSHOT_UNAVAILABLE", "查询结果不可保存", 422
                )
            finishing = True
            if execution_control is not None:
                execution_control.checkpoint()
            if progress_observer is not None:
                progress_observer.set_stage(ExecutionStage.RESULT_SAVING)
            return self._finish_attempt(
                auth.user_id, token, snapshot, None, execution_id
            )
        except ExecutionStopped:
            raise
        except HistoryError as exc:
            exc.history_id, exc.turn_id = history_id, token.turn_id
            if finishing:
                raise HistoryError(
                    "HISTORY_SAVE_UNCONFIRMED",
                    "结果未确认，请刷新历史",
                    503,
                    history_id=history_id,
                    turn_id=token.turn_id,
                ) from None
            if exc.code not in {
                "HISTORY_STORAGE_UNAVAILABLE",
                "HISTORY_SAVE_UNCONFIRMED",
            }:
                try:
                    self._finish_attempt(
                        auth.user_id,
                        token,
                        None,
                        {
                            "request_id": request_id,
                            "error_code": exc.code,
                            "error_message": exc.message,
                        },
                        execution_id,
                    )
                except HistoryError:
                    raise HistoryError(
                        "HISTORY_SAVE_UNCONFIRMED",
                        "结果未确认，请刷新历史",
                        503,
                        history_id=history_id,
                        turn_id=token.turn_id,
                    ) from None
            if exc.code == "HISTORY_STORAGE_UNAVAILABLE":
                raise HistoryError(
                    "HISTORY_SAVE_UNCONFIRMED",
                    "结果未确认，请刷新历史",
                    503,
                    history_id=history_id,
                    turn_id=token.turn_id,
                ) from None
            raise
        except Exception:  # noqa: BLE001 - 禁止泄漏下游异常或自动重试
            raise HistoryError(
                "HISTORY_SAVE_UNCONFIRMED",
                "结果未确认，请刷新历史；本请求不会自动重试",
                503,
                history_id=history_id,
                turn_id=token.turn_id,
            ) from None
