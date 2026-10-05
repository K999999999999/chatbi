"""后台执行 HTTP Adapter：写请求只负责受理，读取只检查现有执行。"""

from types import SimpleNamespace
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr, field_validator
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import Headers

from src.authorization.contracts import (
    AuthContext,
    AuthenticationRequired,
    IdentityProviderUnavailable,
)

from .execution_events import encode_sse
from .history_api import _identity, _public_header, _public_turn, _request_id
from .history_contracts import HistoryError, storage_unavailable


class QueryExecutionBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Literal["query"]
    question: StrictStr = Field(max_length=8192)
    operation_id: UUID
    expected_context_revision: StrictInt = Field(ge=0)

    @field_validator("question")
    @classmethod
    def nonempty(cls, value):
        if not value.strip():
            raise ValueError("问题不能为空")
        return value.strip()


class AnalysisExecutionBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Literal["analysis"]
    operation_id: UUID
    expected_record_revision: StrictInt = Field(ge=0)


ExecutionSubmitBody = Annotated[
    QueryExecutionBody | AnalysisExecutionBody,
    Field(discriminator="mode"),
]


class RequeryExecutionBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    operation_id: UUID
    source_turn_id: UUID | None = None


def _execution_application(request):
    application = getattr(request.app.state, "execution_application", None)
    if application is None:
        raise storage_unavailable()
    return application


def _request_snapshot(request):
    headers = []
    for name in ("authorization", "x-chatbi-user-id"):
        value = request.headers.get(name)
        if value is not None:
            headers.append((name.encode("ascii"), value.encode("latin-1")))
    return SimpleNamespace(
        cookies=dict(request.cookies),
        headers=Headers(raw=headers),
    )


def _readonly_identity(request):
    provider = request.app.state.identity_provider
    try:
        readonly = getattr(provider, "authenticate_readonly", None)
        auth = (
            readonly(_request_snapshot(request))
            if callable(readonly)
            else provider.authenticate(_request_snapshot(request))
        )
        if not isinstance(auth, AuthContext):
            raise IdentityProviderUnavailable("身份响应非法")
        return auth
    except AuthenticationRequired:
        raise HistoryError("AUTHENTICATION_REQUIRED", "需要有效身份认证", 401) from None
    except IdentityProviderUnavailable:
        raise HistoryError(
            "AUTHENTICATION_UNAVAILABLE", "身份认证暂时不可用", 503
        ) from None
    except Exception:  # noqa: BLE001 - identity validation fails closed
        raise HistoryError(
            "AUTHENTICATION_UNAVAILABLE", "身份认证暂时不可用", 503
        ) from None


def _reauthenticator(request, initial_auth):
    provider = request.app.state.identity_provider
    credential = _request_snapshot(request)
    expected = (
        initial_auth.user_id,
        initial_auth.subject_id,
        initial_auth.identity_provider,
    )

    def reauthenticate():
        try:
            readonly = getattr(provider, "authenticate_readonly", None)
            current = (
                readonly(credential)
                if callable(readonly)
                else provider.authenticate(credential)
            )
        except AuthenticationRequired:
            raise HistoryError(
                "AUTHENTICATION_REQUIRED", "登录已失效，请重新登录", 401
            ) from None
        except IdentityProviderUnavailable:
            raise HistoryError(
                "AUTHENTICATION_UNAVAILABLE", "身份认证暂时不可用", 503
            ) from None
        except Exception:  # noqa: BLE001 - worker identity checks fail closed
            raise HistoryError(
                "AUTHENTICATION_UNAVAILABLE", "身份认证暂时不可用", 503
            ) from None
        if not isinstance(current, AuthContext):
            raise HistoryError(
                "AUTHENTICATION_UNAVAILABLE", "身份认证暂时不可用", 503
            )
        if (current.user_id, current.subject_id, current.identity_provider) != expected:
            raise HistoryError(
                "AUTHORIZATION_DENIED", "当前身份不可交付该结果", 403
            )
        return current

    return reauthenticate


def _public_view(view):
    execution = view.execution
    return jsonable_encoder(
        {
            "execution": {
                "id": execution.id,
                "history_id": execution.history_id,
                "turn_id": execution.turn_id,
                "operation_id": execution.operation_id,
                "mode": execution.mode,
                "operation_kind": execution.operation_kind,
                "status": execution.status,
                "stop_reason": execution.stop_reason,
                "created_at": execution.created_at,
                "started_at": execution.started_at,
                "deadline_at": execution.deadline_at,
                "finished_at": execution.finished_at,
                "public_error": execution.public_error,
            },
            "history": _public_header(view.history),
            "turn": _public_turn(
                view.turn,
                include_snapshot=view.turn.status == "succeeded",
            ),
        }
    )


def _persisted_snapshot(view):
    execution = view.execution
    return {
        "version": 1,
        "execution_id": execution.id,
        "history_id": execution.history_id,
        "turn_id": execution.turn_id,
        "sequence": 0,
        "draft_generation": 0,
        "type": "snapshot",
        "payload": {
            "status": execution.status,
            "stage": None,
            "completed_tasks": 0,
            "total_tasks": None,
            "stop_reason": execution.stop_reason,
            "draft_generation": 0,
        },
    }


def _auth_lost_event(execution_id, sequence):
    return {
        "version": 1,
        "execution_id": execution_id,
        "sequence": sequence,
        "type": "auth_lost",
        "payload": {},
    }


def mount_execution_api(app):
    histories = APIRouter(prefix="/api/v1/histories")
    executions = APIRouter(prefix="/api/v1/executions")
    saved = APIRouter(prefix="/api/v1/saved-results")

    @histories.post("/{history_id}/executions", status_code=202)
    def submit(
        request: Request,
        history_id: UUID,
        body: ExecutionSubmitBody,
    ):
        application = _execution_application(request)
        auth = _identity(request)
        request_id = _request_id(request)
        reauthenticate = _reauthenticator(request, auth)
        if isinstance(body, QueryExecutionBody):
            view = application.submit(
                auth,
                request_id,
                str(history_id),
                str(body.operation_id),
                mode="query",
                question=body.question,
                expected_context_revision=body.expected_context_revision,
                reauthenticate=reauthenticate,
            )
        else:
            view = application.submit(
                auth,
                request_id,
                str(history_id),
                str(body.operation_id),
                mode="analysis",
                expected_record_revision=body.expected_record_revision,
                reauthenticate=reauthenticate,
            )
        return JSONResponse(status_code=202, content=_public_view(view))

    @histories.post("/{history_id}/requery-executions", status_code=202)
    def requery_history(
        request: Request,
        history_id: UUID,
        body: RequeryExecutionBody,
    ):
        auth = _identity(request)
        view = _execution_application(request).requery(
            auth,
            _request_id(request),
            "history",
            str(history_id),
            str(body.source_turn_id) if body.source_turn_id else None,
            str(body.operation_id),
            reauthenticate=_reauthenticator(request, auth),
        )
        return JSONResponse(status_code=202, content=_public_view(view))

    @saved.post("/{result_id}/requery-executions", status_code=202)
    def requery_saved_result(
        request: Request,
        result_id: UUID,
        body: RequeryExecutionBody,
    ):
        auth = _identity(request)
        view = _execution_application(request).requery(
            auth,
            _request_id(request),
            "saved",
            str(result_id),
            None,
            str(body.operation_id),
            reauthenticate=_reauthenticator(request, auth),
        )
        return JSONResponse(status_code=202, content=_public_view(view))

    @executions.get("/by-operation/{operation_id}")
    def by_operation(request: Request, operation_id: UUID):
        view = _execution_application(request).by_operation(
            _readonly_identity(request),
            _request_id(request),
            str(operation_id),
        )
        return _public_view(view)

    @executions.get("/{execution_id}")
    def get_execution(request: Request, execution_id: UUID):
        view = _execution_application(request).get(
            _readonly_identity(request),
            _request_id(request),
            str(execution_id),
        )
        return _public_view(view)

    @executions.get("/{execution_id}/events")
    async def observe_execution(request: Request, execution_id: UUID):
        application = _execution_application(request)
        initial_auth = _readonly_identity(request)
        view, subscription = application.subscribe(
            initial_auth,
            _request_id(request),
            str(execution_id),
        )
        reauthenticate = _reauthenticator(request, initial_auth)

        async def stream():
            sequence = 0

            async def authorized_now():
                current_auth = await run_in_threadpool(reauthenticate)
                await run_in_threadpool(
                    application.authorize_observer,
                    current_auth,
                    _request_id(request),
                    str(execution_id),
                )

            try:
                if subscription is None:
                    event = _persisted_snapshot(view)
                    try:
                        await authorized_now()
                    except HistoryError:
                        yield encode_sse(_auth_lost_event(str(execution_id), 0))
                        return
                    yield encode_sse(event)
                    return

                initial = subscription.snapshot
                sequence = initial["sequence"]
                try:
                    await authorized_now()
                except HistoryError:
                    yield encode_sse(_auth_lost_event(str(execution_id), sequence))
                    return
                yield encode_sse(initial)
                if initial["payload"]["status"] in {
                    "succeeded",
                    "failed",
                    "cancelled",
                    "timed_out",
                    "unconfirmed",
                }:
                    return

                while not await request.is_disconnected():
                    events = await run_in_threadpool(subscription.read, 15.0)
                    if not events:
                        try:
                            await authorized_now()
                        except HistoryError:
                            yield encode_sse(_auth_lost_event(str(execution_id), sequence))
                            return
                        yield b": heartbeat\n\n"
                        continue
                    for event in events:
                        try:
                            await authorized_now()
                        except HistoryError:
                            yield encode_sse(
                                _auth_lost_event(str(execution_id), sequence)
                            )
                            return
                        sequence = event["sequence"]
                        yield encode_sse(event)
                        if event["type"] == "terminal":
                            return
            finally:
                if subscription is not None:
                    subscription.close()

        return StreamingResponse(
            stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-store",
                "X-Accel-Buffering": "no",
            },
        )

    app.include_router(histories)
    app.include_router(saved)
    app.include_router(executions)
