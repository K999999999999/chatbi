"""导出用例：固定已授权快照、运行文件生成器并裁决交付来源。"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from threading import Event
from time import monotonic
from typing import Protocol

from .export_runtime import ExportFailure


class FileGenerator(Protocol):
    def generate(
        self, owner: int, document: dict, cancelled: Event, *, format: str = "xlsx", selection: dict | None = None
    ): ...


@dataclass(frozen=True)
class ExportJob:
    owner: int
    request_id: str
    source_kind: str
    source_id: str
    turn_id: str | None
    source: dict
    document: dict
    format: str
    selection: dict | None


class ResultExportApplication:
    def __init__(self, history_application, file_generator: FileGenerator):
        self._history = history_application
        self._generator = file_generator

    def prepare(
        self,
        auth,
        request_id: str,
        source_kind: str,
        source_id: str,
        turn_id: str | None,
        format: str,
        selection: dict | None = None,
    ) -> ExportJob:
        if format not in {"xlsx", "png"}:
            raise ExportFailure(
                "EXPORT_FORMAT_UNAVAILABLE", "所选导出格式暂不可用", 422
            )
        if format == "xlsx" and selection is not None or format == "png" and not selection:
            raise ExportFailure(
                "EXPORT_SELECTION_INVALID", "图表选择无效", 422
            )
        source = self._history.export_source(
            auth, request_id, source_kind, source_id, turn_id
        )
        if not isinstance(source, dict) or source.get("kind") not in {"query", "analysis"}:
            raise ExportFailure(
                "EXPORT_SOURCE_UNAVAILABLE", "记录不可用，请刷新后重试", 404
            )
        if format == "xlsx" and source.get("kind") != "query":
            raise ExportFailure(
                "EXPORT_FORMAT_UNAVAILABLE", "XLSX 仅支持成功的查询快照", 422
            )
        document = {**source, "export_time": datetime.now(UTC).isoformat()}
        return ExportJob(
            auth.user_id,
            request_id,
            source_kind,
            source_id,
            turn_id,
            source,
            document,
            format,
            selection,
        )

    def generate(self, job: ExportJob, cancelled: Event):
        return self._generator.generate(
            job.owner,
            job.document,
            cancelled,
            format=job.format,
            selection=job.selection,
        )

    def verify_delivery(self, job: ExportJob, current_auth, artifact) -> None:
        if monotonic() >= artifact.deadline:
            raise ExportFailure("EXPORT_TIMEOUT", "文件生成超过 60 秒限制", 504)
        if current_auth.user_id != job.owner:
            raise ExportFailure(
                "EXPORT_SOURCE_UNAVAILABLE", "记录不可用，请刷新后重试", 404
            )
        current_source = self._history.export_source(
            current_auth,
            job.request_id,
            job.source_kind,
            job.source_id,
            job.turn_id,
        )
        if _source_hash(current_source) != _source_hash(job.source):
            raise ExportFailure(
                "EXPORT_SOURCE_UNAVAILABLE", "记录已更新或不可用，请刷新后重试", 404
            )
        if monotonic() >= artifact.deadline:
            raise ExportFailure("EXPORT_TIMEOUT", "文件生成超过 60 秒限制", 504)


def _source_hash(source: dict) -> str:
    stable = {
        key: source.get(key)
        for key in ("kind", "question", "result_time", "saved_time", "result")
    }
    return hashlib.sha256(
        json.dumps(
            stable, sort_keys=True, ensure_ascii=False, separators=(",", ":")
        ).encode()
    ).hexdigest()
