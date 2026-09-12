"""基于本地 OpenTelemetry SDK 的安全、Fail-open Trace Adapter。"""

from collections.abc import Mapping, Sequence
from contextvars import ContextVar, Token
from dataclasses import dataclass
import logging
import re
import secrets
from typing import Any

from opentelemetry import trace
from opentelemetry.trace import Span as OTelSpan
from opentelemetry.trace import Status, StatusCode, use_span
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    SimpleSpanProcessor,
    SpanExportResult,
    SpanExporter,
)
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
from opentelemetry.sdk.trace.sampling import ALWAYS_OFF, ALWAYS_ON
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

from .config import ObservabilityConfig
from .contracts import (
    Attributes,
    Carrier,
    ErrorType,
    QuerySource,
    SpanScope,
    TraceOutcome,
    TraceRecorder,
    TraceScope,
)


_LOGGER = logging.getLogger(__name__)
_TRACE_ID_RE = re.compile(r"^[0-9a-f]{32}$")
_ERROR_CODE_RE = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")
_SAFE_OUTCOMES = frozenset(item.value for item in TraceOutcome)
_SAFE_ERROR_TYPES = frozenset(item.value for item in ErrorType)
_SAFE_WARNING_STAGES = frozenset(
    {
        "attribute",
        "exporter_configuration",
        "exporter_export",
        "exporter_force_flush",
        "exporter_initialization",
        "exporter_shutdown",
        "instrumentation",
        "provider_shutdown",
        "query_trace",
        "safe_enrich_current",
        "safe_query_trace",
        "safe_shutdown",
        "safe_span",
        "scope_context_exit",
        "scope_context_reset",
        "scope_end",
        "scope_enter",
        "span",
        "span_start",
        "status",
    }
)
_SAFE_ATTRIBUTE_RULES: dict[str, str] = {
    "chatbi.request.source": "source",
    "chatbi.request.id": "identifier",
    "chatbi.content_capture.enabled": "boolean",
    "chatbi.outcome": "outcome",
    "chatbi.error.type": "error_type",
    "chatbi.error_code": "error_code",
    "chatbi.status": "status",
    "chatbi.result.status": "status",
    "chatbi.retrieval.status": "status",
    "chatbi.retrieval.request_shape": "status",
    "chatbi.retrieval.fallback_policy": "status",
    "chatbi.retrieval.fallback_used": "boolean",
    "chatbi.retrieval.context_source": "identifier",
    "chatbi.retrieval.asset_version": "version",
    "chatbi.retrieval.candidate_id": "identifier",
    "chatbi.retrieval.candidate_type": "identifier",
    "chatbi.retrieval.table_count": "count",
    "chatbi.retrieval.column_count": "count",
    "chatbi.retrieval.metric_count": "count",
    "chatbi.prompt.length": "count",
    "chatbi.prompt.question_length": "count",
    "chatbi.prompt.context_length": "count",
    "chatbi.sql.sha256": "hash",
    "chatbi.database.row_count": "count",
    "chatbi.database.truncated": "boolean",
    "chatbi.trace.version": "version",
    "chatbi.schema.version": "version",
    "chatbi.retry_count": "count",
    "chatbi.retrieval.candidate_count": "count",
    "chatbi.result.row_count": "count",
    "chatbi.duration_ms": "count",
}
_SAFE_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_SAFE_HASH_RE = re.compile(r"^[0-9a-fA-F]{32,128}$")
_SAFE_VERSION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,63}$")
_SENSITIVE_VALUE_RE = re.compile(
    r"(?:raw[-_ ]?secret|password|authorization|api[-_ ]?key|bearer|access[-_ ]?token)",
    re.IGNORECASE,
)
_ACTIVE_ROOT: ContextVar["_RootState | None"] = ContextVar(
    "chatbi_observability_active_root",
    default=None,
)


@dataclass(slots=True)
class _RootState:
    trace_id: str
    span: OTelSpan | None
    active: bool = True


class _NoopScope:
    def __init__(
        self,
        trace_id: str,
        *,
        owns_root: bool = False,
        root_state: _RootState | None = None,
    ) -> None:
        self._trace_id = _valid_trace_id(trace_id)
        self._owns_root = owns_root
        self._root_state = root_state
        self._root_token: Token[_RootState | None] | None = None
        self._entered = False
        self._ended = False

    @property
    def trace_id(self) -> str:
        return self._trace_id

    @property
    def owns_root(self) -> bool:
        return self._owns_root

    def __enter__(self) -> "_NoopScope":
        if self._entered:
            return self
        self._entered = True
        if self._owns_root and self._root_state is not None:
            try:
                self._root_token = _ACTIVE_ROOT.set(self._root_state)
            except Exception:
                _safe_warning("scope_enter")
        return self

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> bool:
        if self._ended:
            return False
        if self._root_token is not None:
            try:
                _ACTIVE_ROOT.reset(self._root_token)
            except Exception:
                _safe_warning("scope_context_reset")
            self._root_token = None
        if self._owns_root and self._root_state is not None:
            self._root_state.active = False
        self._ended = True
        return False


class _OtelScope:
    def __init__(
        self,
        span: OTelSpan,
        *,
        owns_root: bool = False,
        root_state: _RootState | None = None,
    ) -> None:
        self._span = span
        self._trace_id = _trace_id_from_span(span)
        self._owns_root = owns_root
        self._root_state = root_state
        self._root_token: Token[_RootState | None] | None = None
        self._span_context: Any = use_span(
            span,
            end_on_exit=False,
            record_exception=False,
            set_status_on_exception=False,
        )
        self._entered = False
        self._ended = False

    @property
    def trace_id(self) -> str:
        return self._trace_id

    @property
    def owns_root(self) -> bool:
        return self._owns_root

    def __enter__(self) -> "_OtelScope":
        if self._entered:
            return self
        try:
            self._span_context.__enter__()
            self._entered = True
            if self._owns_root and self._root_state is not None:
                self._root_token = _ACTIVE_ROOT.set(self._root_state)
        except Exception:
            _safe_warning("scope_enter")
        return self

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> bool:
        if self._ended:
            return False
        try:
            if self._entered:
                self._span_context.__exit__(None, None, None)
        except Exception:
            _safe_warning("scope_context_exit")
        finally:
            if self._root_token is not None:
                try:
                    _ACTIVE_ROOT.reset(self._root_token)
                except Exception:
                    _safe_warning("scope_context_reset")
                self._root_token = None
            if self._owns_root and self._root_state is not None:
                self._root_state.active = False
            try:
                self._span.end()
            except Exception:
                _safe_warning("scope_end")
            self._ended = True
        return False


class _BorrowedScope(_NoopScope):
    """借用外层 Root；退出时绝不结束或清理外层状态。"""

    def __init__(self, trace_id: str) -> None:
        super().__init__(trace_id, owns_root=False)


class _SafeExporter(SpanExporter):
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
            _safe_warning("exporter_export")
            return SpanExportResult.FAILURE

    def shutdown(self) -> None:
        try:
            self._delegate.shutdown()
        except Exception:
            _safe_warning("exporter_shutdown")

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        try:
            force_flush = getattr(self._delegate, "force_flush", None)
            if not callable(force_flush):
                return True
            result = force_flush(timeout_millis)
            return result is not False
        except Exception:
            _safe_warning("exporter_force_flush")
            return False


class OtelTraceRecorder:
    """不直接暴露给业务层的 OTel 实现；所有边界均安全降级。"""

    def __init__(
        self,
        provider: TracerProvider,
        config: ObservabilityConfig | None = None,
    ) -> None:
        self._provider = provider
        self._config = config or ObservabilityConfig()
        try:
            self._tracer = provider.get_tracer("chatbi.observability")
        except Exception:
            self._tracer = None

    def query_trace(
        self,
        source: QuerySource | str,
        carrier: Carrier | None = None,
        attributes: Attributes | None = None,
    ) -> TraceScope:
        try:
            active_root = _ACTIVE_ROOT.get()
            if active_root is not None and active_root.active:
                return _BorrowedScope(active_root.trace_id)

            # T1 不信任 HTTP Header；carrier 只保留 Contract 形状，真正的 HTTP
            # 边界由后续任务决定。进程内 Context 由 OTel 当前上下文继续传播。
            del carrier
            root_attributes = _safe_attributes(attributes)
            root_attributes["chatbi.request.source"] = _safe_source(source)
            # 内容采集开关只能来自受信任配置，调用方不能用同名属性覆盖。
            root_attributes[
                "chatbi.content_capture.enabled"
            ] = self._config.content_capture_enabled
            root = self._start_span("query.request", root_attributes)
            if root is None:
                return _new_noop_root_scope()
            state = _RootState(_trace_id_from_span(root), root)
            return _OtelScope(root, owns_root=True, root_state=state)
        except Exception:
            _safe_warning("query_trace")
            return _new_noop_root_scope()

    def span(
        self,
        name: str,
        attributes: Attributes | None = None,
    ) -> SpanScope:
        try:
            normalized_name = _safe_span_name(name)
            if normalized_name is None:
                return _NoopScope(_current_trace_id())
            span = self._start_span(normalized_name, _safe_attributes(attributes))
            if span is None:
                return _NoopScope(_current_trace_id())
            return _OtelScope(span)
        except Exception:
            _safe_warning("span")
            return _NoopScope(_current_trace_id())

    def enrich_current(
        self,
        attributes: Attributes | None = None,
        outcome: TraceOutcome | str | None = None,
        error_type: ErrorType | str | None = None,
        error_code: str | None = None,
    ) -> None:
        try:
            current = trace.get_current_span()
            if not current.get_span_context().is_valid:
                return
            for key, value in _safe_attributes(attributes).items():
                if key == "chatbi.content_capture.enabled":
                    continue
                _safe_set_attribute(current, key, value)

            normalized_outcome = _safe_enum_value(outcome, _SAFE_OUTCOMES)
            if normalized_outcome is not None:
                _safe_set_attribute(current, "chatbi.outcome", normalized_outcome)
                _safe_set_status(current, normalized_outcome)

            normalized_error_type = _safe_enum_value(error_type, _SAFE_ERROR_TYPES)
            if normalized_error_type is not None:
                _safe_set_attribute(
                    current,
                    "chatbi.error.type",
                    normalized_error_type,
                )
            if _is_safe_error_code(error_code):
                _safe_set_attribute(current, "chatbi.error_code", error_code)
        except Exception:
            _safe_warning("enrich_current")

    def shutdown(self) -> None:
        """关闭进程级 Provider；查询结束不会调用此方法。"""

        try:
            self._provider.shutdown()
        except Exception:
            _safe_warning("provider_shutdown")

    def _start_span(
        self,
        name: str,
        attributes: Mapping[str, Any],
    ) -> OTelSpan | None:
        if self._tracer is None:
            return None
        try:
            return self._tracer.start_span(name, attributes=attributes)
        except Exception:
            _safe_warning("span_start")
            return None


class SafeTraceRecorder:
    """业务边界使用的 Safe Wrapper（安全包装器）。"""

    def __init__(self, delegate: TraceRecorder) -> None:
        self._delegate = delegate

    def query_trace(
        self,
        source: QuerySource | str,
        carrier: Carrier | None = None,
        attributes: Attributes | None = None,
    ) -> TraceScope:
        try:
            return self._delegate.query_trace(source, carrier, attributes)
        except Exception:
            _safe_warning("safe_query_trace")
            return _new_noop_root_scope()

    def span(
        self,
        name: str,
        attributes: Attributes | None = None,
    ) -> SpanScope:
        try:
            return self._delegate.span(name, attributes)
        except Exception:
            _safe_warning("safe_span")
            return _NoopScope(_current_trace_id())

    def enrich_current(
        self,
        attributes: Attributes | None = None,
        outcome: TraceOutcome | str | None = None,
        error_type: ErrorType | str | None = None,
        error_code: str | None = None,
    ) -> None:
        try:
            self._delegate.enrich_current(
                attributes,
                outcome,
                error_type,
                error_code,
            )
        except Exception:
            _safe_warning("safe_enrich_current")

    def shutdown(self) -> None:
        try:
            shutdown = getattr(self._delegate, "shutdown", None)
            if callable(shutdown):
                shutdown()
        except Exception:
            _safe_warning("safe_shutdown")


def create_trace_recorder(
    config: ObservabilityConfig | None = None,
) -> SafeTraceRecorder:
    """按配置创建 Safe Recorder；Exporter 不可用时自动使用关闭模式。"""

    resolved = config or ObservabilityConfig.from_env()
    provider = _build_provider(resolved)
    return SafeTraceRecorder(OtelTraceRecorder(provider, resolved))


def create_in_memory_recorder(
    config: ObservabilityConfig | None = None,
) -> tuple[SafeTraceRecorder, InMemorySpanExporter]:
    """创建确定性测试 Recorder 和 In-memory Exporter。"""

    resolved = config or ObservabilityConfig()
    exporter = InMemorySpanExporter()
    provider = TracerProvider(
        resource=_resource_for(resolved),
        sampler=ALWAYS_ON,
    )
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return SafeTraceRecorder(OtelTraceRecorder(provider, resolved)), exporter


def _build_provider(config: ObservabilityConfig) -> TracerProvider:
    resource = _resource_for(config)
    provider = TracerProvider(resource=resource, sampler=ALWAYS_OFF)
    if not config.enabled or not config.otlp_traces_endpoint:
        if config.enabled:
            _safe_warning("exporter_configuration")
        return provider

    try:
        exporter = OTLPSpanExporter(
            endpoint=config.otlp_traces_endpoint,
            headers=dict(config.otlp_headers),
            timeout=config.otlp_timeout_seconds,
        )
        # Export 开启时允许 SDK 记录 Span；关闭模式保持 AlwaysOff。
        provider = TracerProvider(resource=resource, sampler=ALWAYS_ON)
        provider.add_span_processor(BatchSpanProcessor(_SafeExporter(exporter)))
    except Exception:
        _safe_warning("exporter_initialization")
        provider = TracerProvider(resource=resource, sampler=ALWAYS_OFF)
    return provider


def _resource_for(config: ObservabilityConfig) -> Resource:
    attributes: dict[str, str] = {
        "service.name": config.service_name,
        "service.version": config.service_version,
    }
    if config.deployment_environment:
        attributes["deployment.environment.name"] = config.deployment_environment
    return Resource.create(attributes)


def _safe_attributes(attributes: Attributes | None) -> dict[str, Any]:
    if not isinstance(attributes, Mapping):
        return {}
    result: dict[str, Any] = {}
    for raw_key, value in attributes.items():
        if not isinstance(raw_key, str):
            continue
        rule = _SAFE_ATTRIBUTE_RULES.get(raw_key)
        if rule is None:
            continue
        safe_value = _safe_attribute_value(value, rule)
        if safe_value is not None:
            result[raw_key] = safe_value
    return result


def _safe_attribute_value(value: Any, rule: str) -> Any:
    if rule == "boolean":
        return value if isinstance(value, bool) else None
    if rule == "count":
        return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None
    if not isinstance(value, str):
        return None
    if len(value) > 128 or "\n" in value or "\r" in value:
        return None
    if _SENSITIVE_VALUE_RE.search(value):
        return None
    if rule == "source":
        return value if value in {item.value for item in QuerySource} else None
    if rule == "outcome":
        return value if value in _SAFE_OUTCOMES else None
    if rule == "error_type":
        return value if value in _SAFE_ERROR_TYPES else None
    if rule == "error_code":
        return value if _is_safe_error_code(value) else None
    if rule == "identifier":
        return value if _SAFE_IDENTIFIER_RE.fullmatch(value) else None
    if rule == "hash":
        return value if _SAFE_HASH_RE.fullmatch(value) else None
    if rule == "version":
        return value if _SAFE_VERSION_RE.fullmatch(value) else None
    if rule == "status":
        return value if _SAFE_IDENTIFIER_RE.fullmatch(value) else None
    return None


def _safe_span_name(name: str) -> str | None:
    if not isinstance(name, str):
        return None
    normalized = name.strip()
    if not normalized or len(normalized) > 128 or "\n" in normalized:
        return None
    return normalized


def _safe_source(source: QuerySource | str) -> str:
    if isinstance(source, QuerySource):
        return source.value
    if isinstance(source, str) and source.strip().upper() in {
        item.value for item in QuerySource
    }:
        return source.strip().upper()
    return QuerySource.INTERNAL.value


def _safe_enum_value(value: Any, allowed: frozenset[str]) -> str | None:
    candidate = value.value if isinstance(value, (TraceOutcome, ErrorType)) else value
    if isinstance(candidate, str) and candidate in allowed:
        return candidate
    return None


def _is_safe_error_code(value: str | None) -> bool:
    return isinstance(value, str) and _ERROR_CODE_RE.fullmatch(value) is not None


def _safe_set_attribute(span: OTelSpan, key: str, value: Any) -> None:
    try:
        span.set_attribute(key, value)
    except Exception:
        _safe_warning("attribute")


def _safe_set_status(span: OTelSpan, outcome: str) -> None:
    try:
        status_code = (
            StatusCode.OK
            if outcome in {
                TraceOutcome.SUCCESS.value,
                TraceOutcome.FALLBACK_SUCCESS.value,
            }
            else StatusCode.ERROR
            if outcome
            in {
                TraceOutcome.TECHNICAL_FAILURE.value,
                TraceOutcome.TIMEOUT.value,
            }
            else StatusCode.UNSET
        )
        span.set_status(Status(status_code))
    except Exception:
        _safe_warning("status")


def _trace_id_from_span(span: OTelSpan) -> str:
    try:
        return _valid_trace_id(f"{span.get_span_context().trace_id:032x}")
    except Exception:
        return _new_trace_id()


def _valid_trace_id(value: str) -> str:
    if _TRACE_ID_RE.fullmatch(value) and int(value, 16) != 0:
        return value
    return _new_trace_id()


def _new_trace_id() -> str:
    value = secrets.token_hex(16)
    return value if int(value, 16) != 0 else "0" * 31 + "1"


def _current_trace_id() -> str:
    active = _ACTIVE_ROOT.get()
    if active is not None and active.active:
        return active.trace_id
    try:
        current = trace.get_current_span().get_span_context()
        if current.is_valid:
            return _valid_trace_id(f"{current.trace_id:032x}")
    except Exception:
        pass
    return _new_trace_id()


def _new_noop_root_scope() -> TraceScope:
    active = _ACTIVE_ROOT.get()
    if active is not None and active.active:
        return _BorrowedScope(active.trace_id)
    trace_id = _new_trace_id()
    return _NoopScope(
        trace_id,
        owns_root=True,
        root_state=_RootState(trace_id, None),
    )


def _safe_warning(stage: str) -> None:
    try:
        safe_stage = stage if stage in _SAFE_WARNING_STAGES else "instrumentation"
        _LOGGER.warning(
            "Observability degraded: component=trace stage=%s error_type=INSTRUMENTATION",
            safe_stage,
        )
    except Exception:
        pass
