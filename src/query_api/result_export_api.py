"""只读历史 / 成果文件导出 HTTP Adapter。"""

from __future__ import annotations

import asyncio
import re
import subprocess
import threading
import unicodedata
from contextlib import nullcontext
from datetime import UTC, datetime
from typing import Literal
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr, model_validator
from starlette.concurrency import run_in_threadpool

from src.observability.contracts import (
    Carrier,
    QuerySource,
    TraceOutcome,
    TraceRecorder,
)
from src.query_api.history_api import _identity, _request_id

from .export_application import ExportJob, ResultExportApplication
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
    chart_id: StrictStr | None = Field(default=None, max_length=80)
    chart_type: Literal["line", "bar"] | None = None
    task_id: StrictStr | None = Field(default=None, max_length=80)
    product_index: StrictInt | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_chart_selection(self):
        selection_values = (
            self.chart_id,
            self.chart_type,
            self.task_id,
            self.product_index,
        )
        if self.format == "png":
            if self.chart_id is None or self.chart_type is None:
                raise ValueError("PNG 导出需要指定图表和类型")
        elif any(value is not None for value in selection_values):
            raise ValueError("仅 PNG 导出接受图表选择")
        return self


class TemporaryFileResponse(FileResponse):
    def __init__(
        self,
        path,
        *,
        runtime,
        owner: int,
        trace_recorder: TraceRecorder | None = None,
        trace_carrier: Carrier | None = None,
        export_format: str,
        export_id: str,
        **kwargs,
    ):
        super().__init__(path, **kwargs)
        self._runtime = runtime
        self._owner = owner
        self._path = path
        self._trace_recorder = trace_recorder
        self._trace_carrier = trace_carrier
        self._export_format = export_format
        self._export_id = export_id

    async def __call__(self, scope, receive, send):
        recorder = self._trace_recorder
        root = (
            recorder.query_trace(
                QuerySource.EXPORT,
                carrier=self._trace_carrier,
                attributes={
                    "chatbi.export.id": self._export_id,
                    "chatbi.export.format": self._export_format,
                },
            )
            if recorder is not None
            else nullcontext()
        )
        with root:
            try:
                delivery = (
                    recorder.span(
                        "export.delivery",
                        {"chatbi.operation.stage": "delivery"},
                    )
                    if recorder is not None
                    else nullcontext()
                )
                with delivery:
                    await super().__call__(scope, receive, send)
            except BaseException:
                if recorder is not None:
                    recorder.enrich_current(
                        outcome=TraceOutcome.TECHNICAL_FAILURE,
                        error_code="EXPORT_DELIVERY_FAILED",
                    )
                raise
            finally:
                cleanup = (
                    recorder.span(
                        "export.cleanup",
                        {"chatbi.operation.stage": "cleanup"},
                    )
                    if recorder is not None
                    else nullcontext()
                )
                try:
                    with cleanup:
                        await asyncio.shield(
                            run_in_threadpool(
                                self._runtime.finish, self._owner, self._path
                            )
                        )
                except BaseException:
                    if recorder is not None:
                        recorder.enrich_current(
                            outcome=TraceOutcome.TECHNICAL_FAILURE,
                            error_code="EXPORT_CLEANUP_FAILED",
                        )
                    raise
            if recorder is not None:
                recorder.enrich_current(outcome=TraceOutcome.SUCCESS)


def _content_disposition(filename: str) -> str:
    fallback = re.sub(r"[^A-Za-z0-9._-]", "_", filename) or "result.xlsx"
    return f"attachment; filename=\"{fallback}\"; filename*=UTF-8''{quote(filename)}"


def _export_filename(job: ExportJob) -> str:
    title = job.source.get("title") or job.source.get("question") or "ChatBI"
    if not isinstance(title, str):
        title = "ChatBI"
    title = unicodedata.normalize("NFKC", title)
    safe_title = "".join(
        "_"
        if character in "/\\" or unicodedata.category(character).startswith("C")
        else character
        for character in title
    )
    safe_title = (
        re.sub(r"\s+", " ", safe_title).strip(" .")[:48].strip(" .") or "ChatBI"
    )
    try:
        exported_at = datetime.fromisoformat(job.document["export_time"]).astimezone(
            UTC
        )
    except (KeyError, TypeError, ValueError):
        exported_at = datetime.now(UTC)
    timestamp = exported_at.strftime("%Y%m%dT%H%M%SZ")
    kind = {"xlsx": "查询结果", "png": "图表", "pdf": "经营分析报告"}[job.format]
    return f"{safe_title}-{kind}-{timestamp}.{job.format}"


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
            (
                {
                    "chart_id": body.chart_id,
                    "chart_type": body.chart_type,
                    **({"task_id": body.task_id} if body.task_id is not None else {}),
                    **(
                        {"product_index": body.product_index}
                        if body.product_index is not None
                        else {}
                    ),
                }
                if body.format == "png"
                else None
            ),
        )
        cancelled = threading.Event()
        trace_recorder = getattr(request.app.state, "trace_recorder", None)
        trace_carrier = getattr(request.state, "trace_carrier", None)

        def generate_export():
            if trace_recorder is None:
                return export_application.generate(job, cancelled)
            with trace_recorder.query_trace(
                QuerySource.EXPORT,
                carrier=trace_carrier,
                attributes={
                    "chatbi.export.id": request_id,
                    "chatbi.export.format": job.format,
                },
            ):
                try:
                    with trace_recorder.span(
                        "export.generate",
                        {"chatbi.operation.stage": "generation"},
                    ):
                        artifact = export_application.generate(job, cancelled)
                except Exception:
                    trace_recorder.enrich_current(
                        outcome=TraceOutcome.TECHNICAL_FAILURE,
                        error_code="EXPORT_GENERATION_FAILED",
                    )
                    raise
                trace_recorder.enrich_current(outcome=TraceOutcome.SUCCESS)
                return artifact

        generate = asyncio.create_task(run_in_threadpool(generate_export))
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

        is_png = job.format == "png"
        is_pdf = job.format == "pdf"
        filename = _export_filename(job)
        return TemporaryFileResponse(
            artifact.path,
            runtime=runtime,
            owner=auth.user_id,
            trace_recorder=trace_recorder,
            trace_carrier=trace_carrier,
            export_format=job.format,
            export_id=request_id,
            media_type="image/png"
            if is_png
            else "application/pdf"
            if is_pdf
            else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename=filename,
            headers={
                "Content-Disposition": _content_disposition(filename),
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
            },
        )

    app.include_router(router)
