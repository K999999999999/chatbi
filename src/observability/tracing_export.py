"""Observability Exporter 的 Fail-open 边界。"""

from collections.abc import Sequence
from typing import Any

from opentelemetry.sdk.trace.export import SpanExportResult, SpanExporter

from .tracing_safety import safe_warning


class SafeExporter(SpanExporter):
    """Exporter 边界的 fail-open 包装器；不把供应商异常交给 Batch Processor。"""

    def __init__(self, delegate: SpanExporter) -> None:
        self._delegate = delegate

    def export(self, spans: Sequence[Any]) -> SpanExportResult:
        try:
            result = self._delegate.export(spans)
            return (
                result
                if isinstance(result, SpanExportResult)
                else SpanExportResult.SUCCESS
            )
        except Exception:
            safe_warning("exporter_export")
            return SpanExportResult.FAILURE

    def shutdown(self) -> None:
        try:
            self._delegate.shutdown()
        except Exception:
            safe_warning("exporter_shutdown")

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        try:
            force_flush = getattr(self._delegate, "force_flush", None)
            if not callable(force_flush):
                return True
            result = force_flush(timeout_millis)
            return result is not False
        except Exception:
            safe_warning("exporter_force_flush")
            return False
