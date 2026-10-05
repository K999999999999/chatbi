"""后台执行 Application：先持久受理，再把已占用的业务尝试交给 worker。"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import wraps
from uuid import uuid4

from src.business_analysis.run_execution import AnalysisExecutionBusy

from .execution_contracts import ExecutionRecord
from .execution_runtime import (
    ExecutionCapacityExceeded,
    ExecutionRuntimeClosed,
)
from .history_contracts import HistoryError, operation_hash

_LOGGER = logging.getLogger(__name__)


def _serialize_operation_at(index):
    def decorate(method):
        @wraps(method)
        def wrapped(self, auth, *args, **kwargs):
            operation_id = kwargs.get("operation_id")
            if operation_id is None:
                operation_id = args[index]
            with self.runtime.serialize_operation(auth.user_id, operation_id):
                return method(self, auth, *args, **kwargs)

        return wrapped

    return decorate


@dataclass(frozen=True, slots=True)
class ExecutionView:
    execution: ExecutionRecord
    history: object
    turn: object


class ExecutionApplication:
    def __init__(self, history_application, execution_runtime):
        self.history = history_application
        self.store = history_application.store
        self.runtime = execution_runtime

    @_serialize_operation_at(2)
    def submit(
        self,
        auth,
        request_id,
        history_id,
        operation_id,
        *,
        mode,
        question=None,
        expected_context_revision=None,
        expected_record_revision=None,
        reauthenticate,
    ):
        self.history.authorize(auth, request_id)
        request_hash = operation_hash(
            {
                "action": "query" if mode == "query" else "analysis_resume",
                "history_id": history_id,
                "question": question if mode == "query" else None,
                "expected_context_revision": expected_context_revision,
                "expected_record_revision": expected_record_revision,
            }
        )
        existing = self.store.execution_by_operation(
            auth.user_id, operation_id, request_hash
        )
        if existing is not None:
            return self._view(auth, request_id, existing)

        self.history.runtime.check()
        header = self.store.header(auth.user_id, history_id)
        if header.kind != mode:
            raise HistoryError("INVALID_REQUEST", "执行模式与历史类型不匹配", 400)
        if mode == "analysis":
            if header.last_success_turn_id is not None:
                raise HistoryError(
                    "HISTORY_RESULT_NOT_SAVABLE", "已完成的分析无需恢复", 409
                )
            if not header.analysis_recovery_available:
                raise HistoryError(
                    "HISTORY_CONTEXT_INCOMPATIBLE",
                    "原分析任务已过期或无法恢复，请新建分析",
                    422,
                )
        lease = self._reserve(
            auth,
            history_id,
            analysis_run_id=header.analysis_run_id if mode == "analysis" else None,
        )
        try:
            accepted = self.store.begin_execution_attempt(
                owner=auth.user_id,
                history_id=history_id,
                question=question if mode == "query" else header.first_question,
                operation_id=operation_id,
                request_hash=request_hash,
                revision=expected_context_revision,
                request_id=request_id,
                epoch=self.history.runtime.epoch,
                mode=mode,
                operation_kind="query" if mode == "query" else "analysis_resume",
                deadline_seconds=180 if mode == "query" else 1200,
                expected_record_revision=expected_record_revision,
            )
            if not accepted.created:
                lease.release()
                return self._view(auth, request_id, accepted.execution)
            self._dispatch(
                lease,
                auth,
                request_id,
                accepted.execution,
                accepted.attempt,
                accepted.attempt.turn.question,
                reauthenticate,
                kind=mode,
                analysis_run_id=header.analysis_run_id,
            )
            return self._view(auth, request_id, accepted.execution)
        except BaseException:
            lease.release()
            raise

    @_serialize_operation_at(4)
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
        self.history.authorize(auth, request_id)
        request_hash = operation_hash(
            {
                "action": f"{source_kind}_requery",
                "source_kind": source_kind,
                "source_id": source_id,
                "source_turn_id": source_turn_id,
            }
        )
        existing = self.store.execution_by_operation(
            auth.user_id, operation_id, request_hash
        )
        if existing is not None:
            return self._view(auth, request_id, existing)

        if source_kind == "history":
            source = self.store.header(auth.user_id, source_id)
            mode = source.kind
        else:
            source, _snapshot = self.store.saved_result(auth.user_id, source_id)
            mode = source.kind
        new_history_id = str(uuid4())
        new_analysis_run_id = str(uuid4()) if mode == "analysis" else None
        lease = self._reserve(
            auth,
            new_history_id,
            analysis_run_id=new_analysis_run_id,
        )
        try:
            header, accepted, execution, created = self.store.begin_execution_requery(
                owner=auth.user_id,
                source_kind=source_kind,
                source_id=source_id,
                source_turn_id=source_turn_id,
                operation_id=operation_id,
                request_id=request_id,
                epoch=self.history.runtime.epoch,
                new_id=new_history_id,
                request_hash=request_hash,
                operation_kind=(
                    "history_requery"
                    if source_kind == "history"
                    else "saved_result_requery"
                ),
                deadline_seconds=180 if mode == "query" else 1200,
                analysis_run_id=new_analysis_run_id,
            )
            if not created:
                lease.release()
                return self._view(auth, request_id, execution)
            self._dispatch(
                lease,
                auth,
                request_id,
                execution,
                accepted,
                accepted.turn.question,
                reauthenticate,
                kind=mode,
                requery=True,
                analysis_run_id=header.analysis_run_id,
            )
            return self._view(auth, request_id, execution)
        except BaseException:
            lease.release()
            raise

    def get(self, auth, request_id, execution_id):
        self.history.authorize(auth, request_id)
        try:
            record = self.store.execution(auth.user_id, execution_id)
        except HistoryError as exc:
            if exc.status == 404:
                raise HistoryError("EXECUTION_UNAVAILABLE", "执行记录不可用", 404) from None
            raise
        return self._view(auth, request_id, record)

    def by_operation(self, auth, request_id, operation_id):
        self.history.authorize(auth, request_id)
        record = self.store.execution_by_operation(auth.user_id, operation_id)
        if record is None:
            raise HistoryError("EXECUTION_UNAVAILABLE", "执行记录尚不可用", 404)
        return self._view(auth, request_id, record)

    def _reserve(self, auth, history_id, *, analysis_run_id):
        try:
            return self.runtime.reserve(
                auth.user_id,
                history_id,
                auth=auth if analysis_run_id is not None else None,
                analysis_run_id=analysis_run_id,
            )
        except ExecutionCapacityExceeded as exc:
            if exc.scope == "user":
                raise HistoryError(
                    "EXECUTION_LIMIT_REACHED", "已有执行仍在运行", 429
                ) from None
            raise HistoryError("EXECUTION_LIMIT_REACHED", "服务繁忙，请稍后再试", 429) from None
        except AnalysisExecutionBusy:
            raise HistoryError("HISTORY_BUSY", "原分析运行仍在执行，请稍后刷新", 409) from None
        except ExecutionRuntimeClosed:
            raise HistoryError("EXECUTION_UNAVAILABLE", "执行服务正在关闭", 503) from None

    def _dispatch(
        self,
        lease,
        auth,
        request_id,
        execution,
        accepted,
        question,
        reauthenticate,
        *,
        kind,
        requery=False,
        analysis_run_id=None,
    ):
        def work():
            try:
                self.store.mark_execution_running(auth.user_id, execution.id)
                self.history._execute_attempt(
                    auth,
                    request_id,
                    execution.history_id,
                    question,
                    accepted,
                    reauthenticate=reauthenticate,
                    requery=requery,
                    kind=kind,
                    analysis_run_id=analysis_run_id,
                    execution_id=execution.id,
                    guard_preowned=True,
                )
            except HistoryError as exc:
                self._persist_worker_failure(
                    auth.user_id, execution, accepted, request_id, exc.code, exc.message
                )
            except Exception as exc:  # noqa: BLE001 - worker failure must not leak internals
                _LOGGER.warning(
                    "Background execution failed: error_type=%s", type(exc).__name__
                )
                self._persist_worker_failure(
                    auth.user_id,
                    execution,
                    accepted,
                    request_id,
                    "EXECUTION_FAILED",
                    "执行失败，请刷新后查看状态",
                )

        try:
            self.runtime.submit(lease, work)
        except RuntimeError as exc:
            _LOGGER.warning("Background execution dispatch failed: error_type=%s", type(exc).__name__)
            self._persist_worker_failure(
                auth.user_id,
                execution,
                accepted,
                request_id,
                "EXECUTION_UNAVAILABLE",
                "执行启动失败，请刷新后查看状态",
            )
            raise HistoryError(
                "EXECUTION_UNAVAILABLE",
                "执行启动失败，请刷新后查看状态",
                503,
                history_id=execution.history_id,
                turn_id=execution.turn_id,
                execution_id=execution.id,
            ) from None

    def _persist_worker_failure(
        self, owner, execution, accepted, request_id, error_code, error_message
    ):
        try:
            self.store.finish_execution_attempt(
                owner,
                accepted.token,
                None,
                {
                    "request_id": request_id,
                    "error_code": error_code,
                    "error_message": error_message,
                },
                execution.id,
            )
        except HistoryError:
            # 保存结果不确定时不能再尝试业务工作；后续状态以 PostgreSQL 为准。
            return

    def _view(self, auth, request_id, execution):
        header = self.history.header(auth, request_id, execution.history_id)
        turn = self.history.turn(
            auth, request_id, execution.history_id, execution.turn_id
        )
        current = self.store.execution(auth.user_id, execution.id)
        return ExecutionView(current, header, turn)
