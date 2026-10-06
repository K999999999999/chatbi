"""只读历史 / 成果文件导出 HTTP Adapter。"""

from __future__ import annotations

import asyncio
import re
import subprocess
import threading
from typing import Literal
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StrictStr
from starlette.concurrency import run_in_threadpool

from src.query_api.history_api import _identity, _request_id

from .export_application import ResultExportApplication
from .export_runtime import ExportFailure, ExportRuntime


class HistoryTurnSource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["history_turn"]
    history_id: UUID
    turn_id: UUID


class SavedResultSource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["saved_result"]
    saved_result_id: UUID


class ResultExportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: HistoryTurnSource | SavedResultSource = Field(discriminator="kind")
    format: StrictStr


class TemporaryFileResponse(FileResponse):
    def __init__(self, path, *, runtime, owner: int, **kwargs):
        super().__init__(path, **kwargs)
        self._runtime = runtime
        self._owner = owner
        self._path = path

    async def __call__(self, scope, receive, send):
        try:
            await super().__call__(scope, receive, send)
        finally:
            await asyncio.shield(
                run_in_threadpool(self._runtime.finish, self._owner, self._path)
            )


def _content_disposition(filename: str) -> str:
    fallback = re.sub(r"[^A-Za-z0-9._-]", "_", filename) or "result.xlsx"
    return f"attachment; filename=\"{fallback}\"; filename*=UTF-8''{quote(filename)}"


def mount_result_export_api(app: FastAPI) -> None:
    runtime = ExportRuntime()
    app.state.result_export_runtime = runtime
    app.router.on_shutdown.append(runtime.shutdown)
    router = APIRouter(prefix="/api/v1/result-exports")

    @app.exception_handler(ExportFailure)
    async def export_failure(request: Request, exc: ExportFailure):
        return JSONResponse(
            status_code=exc.status,
            content={
                "request_id": _request_id(request),
                "error_code": exc.code,
                "error_message": exc.message,
            },
        )

    @router.post("")
    async def export_result(request: Request, body: ResultExportRequest):
        if isinstance(body.source, HistoryTurnSource):
            source_kind = "history_turn"
            source_id = str(body.source.history_id)
            turn_id = str(body.source.turn_id)
        else:
            source_kind = "saved_result"
            source_id = str(body.source.saved_result_id)
            turn_id = None

        history_application = getattr(request.app.state, "history_application", None)
        if history_application is None:
            raise ExportFailure(
                "HISTORY_STORAGE_UNAVAILABLE", "历史存储暂时不可用", 503
            )
        export_application = ResultExportApplication(history_application, runtime)
        auth = await run_in_threadpool(_identity, request)
        request_id = _request_id(request)
        job = await run_in_threadpool(
            export_application.prepare,
            auth,
            request_id,
            source_kind,
            source_id,
            turn_id,
            body.format,
        )
        cancelled = threading.Event()
        generate = asyncio.create_task(
            run_in_threadpool(export_application.generate, job, cancelled)
        )
        try:
            while not generate.done():
                await asyncio.sleep(0.05)
                if await request.is_disconnected():
                    cancelled.set()
                    disconnected_artifact = await asyncio.shield(generate)
                    runtime.finish(auth.user_id, disconnected_artifact.path)
                    raise ExportFailure("EXPORT_DISCONNECTED", "下载连接已中断", 499)
            artifact = await asyncio.shield(generate)
        except asyncio.CancelledError:
            cancelled.set()

            def cleanup_unclaimed_export(task: asyncio.Task):
                if not task.cancelled() and task.exception() is None:
                    generated_artifact = task.result()
                    runtime.finish(auth.user_id, generated_artifact.path)

            generate.add_done_callback(cleanup_unclaimed_export)
            raise
        except ExportFailure:
            raise
        except (OSError, ValueError, subprocess.SubprocessError):
            raise ExportFailure(
                "EXPORT_FAILED", "文件无法完整生成，请稍后重试", 422
            ) from None

        try:
            current_auth = await run_in_threadpool(_identity, request)
            await run_in_threadpool(
                export_application.verify_delivery, job, current_auth, artifact
            )
        except BaseException:
            runtime.finish(auth.user_id, artifact.path)
            raise

        filename = f"chatbi-query-{job.source_id}.xlsx"
        return TemporaryFileResponse(
            artifact.path,
            runtime=runtime,
            owner=auth.user_id,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename=filename,
            headers={
                "Content-Disposition": _content_disposition(filename),
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
            },
        )

    app.include_router(router)
