"""历史HTTP Adapter：当前身份、严格输入与公开DTO。"""

from dataclasses import asdict
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr, field_validator

from src.authorization.contracts import (
    AuthContext,
    AuthenticationRequired,
    IdentityProviderUnavailable,
)

from .history_codec import public_snapshot
from .history_contracts import HistoryError, storage_unavailable
from .query_response import HTTP_STATUS_BY_ERROR


class CreateHistoryBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["query", "analysis"]
    first_question: StrictStr = Field(max_length=8192)
    operation_id: UUID

    @field_validator("first_question")
    @classmethod
    def nonempty(cls, value):
        if not value.strip():
            raise ValueError("问题不能为空")
        return value.strip()


class QueryHistoryBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: StrictStr = Field(max_length=8192)
    operation_id: UUID
    expected_context_revision: StrictInt = Field(ge=0)

    @field_validator("question")
    @classmethod
    def nonempty(cls, value):
        if not value.strip():
            raise ValueError("问题不能为空")
        return value.strip()


class RequeryHistoryBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    operation_id: UUID
    source_turn_id: UUID | None = None


class ResumeAnalysisBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    operation_id: UUID
    expected_record_revision: StrictInt = Field(ge=0)


class EditTitleBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: StrictStr = Field(max_length=120)
    expected_record_revision: StrictInt = Field(ge=0)

    @field_validator("title")
    @classmethod
    def title_nonempty(cls, value):
        if not value.strip():
            raise ValueError("名称不能为空")
        return value.strip()


class DeleteBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_record_revision: StrictInt = Field(ge=0)


class SaveResultBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    history_id: UUID
    turn_id: UUID
    title: StrictStr = Field(max_length=120)

    @field_validator("title")
    @classmethod
    def title_nonempty(cls, value):
        return EditTitleBody.title_nonempty(value)


class RequerySavedBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    operation_id: UUID


def _identity(request):
    try:
        auth = request.app.state.identity_provider.authenticate(request)
        if not isinstance(auth, AuthContext):
            raise IdentityProviderUnavailable("身份响应非法")
        return auth
    except AuthenticationRequired:
        raise HistoryError("AUTHENTICATION_REQUIRED", "需要有效身份认证", 401) from None
    except IdentityProviderUnavailable:
        raise HistoryError(
            "AUTHENTICATION_UNAVAILABLE", "身份认证暂时不可用", 503
        ) from None
    except Exception:  # noqa: BLE001 - 未知身份故障必须Fail Closed
        raise HistoryError(
            "AUTHENTICATION_UNAVAILABLE", "身份认证暂时不可用", 503
        ) from None


def _application(request):
    application = getattr(request.app.state, "history_application", None)
    if application is None:
        raise storage_unavailable()
    return application


def _request_id(request):
    return getattr(request.state, "request_id", None) or str(uuid4())


def _public_header(header):
    value = asdict(header)
    value.pop("analysis_recovery_available")
    value["active"] = header.active_turn_id is not None
    value["can_continue"] = header.kind == "query" and not value["active"]
    value["can_resume"] = (
        header.kind == "analysis"
        and not value["active"]
        and header.last_success_turn_id is None
        and header.analysis_recovery_available
    )
    return jsonable_encoder(value)


def _public_turn(turn, *, include_snapshot):
    value = asdict(turn)
    value.pop("snapshot")
    if include_snapshot and turn.snapshot is not None:
        value["snapshot"] = public_snapshot(turn.snapshot)
    return jsonable_encoder(value)


def mount_history_api(app):
    router = APIRouter(prefix="/api/v1/histories")

    @app.exception_handler(HistoryError)
    async def history_error(request: Request, exc: HistoryError):
        return JSONResponse(
            status_code=exc.status,
            content={
                "request_id": _request_id(request),
                "error_code": exc.code,
                "error_message": exc.message,
                **({"history_id": exc.history_id} if exc.history_id else {}),
                **({"turn_id": exc.turn_id} if exc.turn_id else {}),
            },
        )

    @router.post("")
    def create(request: Request, body: CreateHistoryBody):
        header = _application(request).create(
            _identity(request),
            _request_id(request),
            body.kind,
            body.first_question,
            str(body.operation_id),
        )
        return JSONResponse(status_code=201, content=_public_header(header))

    @router.get("")
    def histories(
        request: Request,
        kind: Literal["query", "analysis"] | None = None,
        limit: int = 20,
        cursor: str | None = None,
        q: str = "",
    ):
        if (
            not 1 <= limit <= 100
            or len(q.strip()) > 200
            or set(request.query_params)
            - {
                "kind",
                "limit",
                "cursor",
                "q",
            }
        ):
            raise HistoryError("INVALID_REQUEST", "分页参数非法", 400)
        application, auth = _application(request), _identity(request)
        application.authorize(auth, _request_id(request))
        headers, next_cursor = application.store.list_histories(
            auth.user_id, kind, limit, cursor, q.strip()
        )
        return {
            "items": [_public_header(h) for h in headers],
            "next_cursor": next_cursor,
        }

    @router.get("/{history_id}")
    def header(request: Request, history_id: UUID):
        return _public_header(
            _application(request).header(
                _identity(request), _request_id(request), str(history_id)
            )
        )

    @router.patch("/{history_id}")
    def rename(request: Request, history_id: UUID, body: EditTitleBody):
        application, auth = _application(request), _identity(request)
        application.authorize(auth, _request_id(request))
        return _public_header(
            application.store.rename_history(
                auth.user_id, str(history_id), body.title, body.expected_record_revision
            )
        )

    @router.delete("/{history_id}")
    def delete(request: Request, history_id: UUID, body: DeleteBody):
        application, auth = _application(request), _identity(request)
        application.delete(
            auth, _request_id(request), str(history_id), body.expected_record_revision
        )
        return Response(status_code=204)

    @router.get("/{history_id}/turns")
    def turns(request: Request, history_id: UUID, limit: int = 20, cursor: int = 0):
        if (
            not 1 <= limit <= 100
            or cursor < 0
            or set(request.query_params) - {"limit", "cursor"}
        ):
            raise HistoryError("INVALID_REQUEST", "分页参数非法", 400)
        application, auth = _application(request), _identity(request)
        application.authorize(auth, _request_id(request))
        items, next_cursor = application.store.turns(
            auth.user_id, str(history_id), limit, cursor
        )
        return {
            "items": [_public_turn(t, include_snapshot=False) for t in items],
            "next_cursor": next_cursor,
        }

    @router.get("/{history_id}/turns/{turn_id}")
    def turn(request: Request, history_id: UUID, turn_id: UUID):
        result = _application(request).turn(
            _identity(request), _request_id(request), str(history_id), str(turn_id)
        )
        return _public_turn(result, include_snapshot=True)

    @router.post("/{history_id}/turns")
    def submit(request: Request, history_id: UUID, body: QueryHistoryBody):
        application, auth = _application(request), _identity(request)
        result = application.submit_query(
            auth,
            _request_id(request),
            str(history_id),
            body.question,
            str(body.operation_id),
            body.expected_context_revision,
            reauthenticate=lambda: _identity(request),
        )
        if result.public_error is not None:
            return JSONResponse(
                status_code=HTTP_STATUS_BY_ERROR.get(
                    result.public_error["error_code"], 422
                ),
                content={
                    **result.public_error,
                    "history_id": str(history_id),
                    "turn_id": result.id,
                },
            )
        return {
            "history": _public_header(
                application.store.header(auth.user_id, str(history_id))
            ),
            "turn": _public_turn(result, include_snapshot=True),
        }

    @router.post("/{history_id}/requery")
    def requery(request: Request, history_id: UUID, body: RequeryHistoryBody):
        application, auth = _application(request), _identity(request)
        header, result = application.requery(
            auth,
            _request_id(request),
            "history",
            str(history_id),
            str(body.source_turn_id) if body.source_turn_id else None,
            str(body.operation_id),
            reauthenticate=lambda: _identity(request),
        )
        if result.public_error is not None:
            return JSONResponse(
                status_code=HTTP_STATUS_BY_ERROR.get(
                    result.public_error["error_code"], 422
                ),
                content={
                    **result.public_error,
                    "history_id": header.id,
                    "turn_id": result.id,
                },
            )
        return {
            "history": _public_header(header),
            "turn": _public_turn(result, include_snapshot=True),
        }

    @router.post("/{history_id}/resume")
    def resume(request: Request, history_id: UUID, body: ResumeAnalysisBody):
        application, auth = _application(request), _identity(request)
        result = application.resume_analysis(
            auth,
            _request_id(request),
            str(history_id),
            str(body.operation_id),
            body.expected_record_revision,
            reauthenticate=lambda: _identity(request),
        )
        if result.public_error is not None:
            return JSONResponse(
                status_code=HTTP_STATUS_BY_ERROR.get(
                    result.public_error["error_code"], 422
                ),
                content={
                    **result.public_error,
                    "history_id": str(history_id),
                    "turn_id": result.id,
                },
            )
        return {
            "history": _public_header(
                application.store.header(auth.user_id, str(history_id))
            ),
            "turn": _public_turn(result, include_snapshot=True),
        }

    app.include_router(router)

    saved = APIRouter(prefix="/api/v1/saved-results")

    def authorized(request):
        application, auth = _application(request), _identity(request)
        application.authorize(auth, _request_id(request))
        return application, auth

    @saved.post("")
    def save_result(request: Request, body: SaveResultBody):
        application, auth = authorized(request)
        result = application.store.copy_result(
            auth.user_id, str(body.history_id), str(body.turn_id), body.title
        )
        return JSONResponse(status_code=201, content=jsonable_encoder(asdict(result)))

    @saved.get("")
    def results(
        request: Request,
        kind: Literal["query", "analysis"] | None = None,
        q: str = "",
        limit: int = 20,
        cursor: str | None = None,
    ):
        if (
            not 1 <= limit <= 100
            or len(q.strip()) > 200
            or set(request.query_params) - {"kind", "q", "limit", "cursor"}
        ):
            raise HistoryError("INVALID_REQUEST", "分页参数非法", 400)
        application, auth = authorized(request)
        items, next_cursor = application.store.list_saved_results(
            auth.user_id, kind, limit, cursor, q.strip()
        )
        return {
            "items": jsonable_encoder([asdict(item) for item in items]),
            "next_cursor": next_cursor,
        }

    @saved.get("/{result_id}")
    def result_detail(request: Request, result_id: UUID):
        application, auth = authorized(request)
        header, snapshot = application.store.saved_result(auth.user_id, str(result_id))
        return {
            **jsonable_encoder(asdict(header)),
            "snapshot": public_snapshot(snapshot),
        }

    @saved.patch("/{result_id}")
    def rename_result(request: Request, result_id: UUID, body: EditTitleBody):
        application, auth = authorized(request)
        return jsonable_encoder(
            asdict(
                application.store.rename_saved_result(
                    auth.user_id,
                    str(result_id),
                    body.title,
                    body.expected_record_revision,
                )
            )
        )

    @saved.delete("/{result_id}")
    def delete_result(request: Request, result_id: UUID, body: DeleteBody):
        application, auth = authorized(request)
        application.store.delete_saved_result(
            auth.user_id, str(result_id), body.expected_record_revision
        )
        return Response(status_code=204)

    @saved.post("/{result_id}/requery")
    def requery_result(request: Request, result_id: UUID, body: RequerySavedBody):
        application, auth = authorized(request)
        header, turn = application.requery(
            auth,
            _request_id(request),
            "saved",
            str(result_id),
            None,
            str(body.operation_id),
            reauthenticate=lambda: _identity(request),
        )
        if turn.public_error:
            return JSONResponse(
                status_code=HTTP_STATUS_BY_ERROR.get(
                    turn.public_error["error_code"], 422
                ),
                content={
                    **turn.public_error,
                    "history_id": header.id,
                    "turn_id": turn.id,
                },
            )
        return {
            "history": _public_header(header),
            "turn": _public_turn(turn, include_snapshot=True),
        }

    app.include_router(saved)
