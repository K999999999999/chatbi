"""基于本地 OpenTelemetry SDK 的安全、Fail-open Trace Adapter。"""

from collections.abc import Mapping
from contextvars import ContextVar, Token
from dataclasses import dataclass
from typing import Any

from opentelemetry import trace
from opentelemetry.trace import Span as OTelSpan
from opentelemetry.trace import use_span
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    SimpleSpanProcessor,
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
from .tracing_export import SafeExporter
from .tracing_safety import (
    _LOGGER,
    _SAFE_ERROR_TYPES,
    _SAFE_OUTCOMES,
    is_safe_error_code as _is_safe_error_code,
    new_trace_id as _new_trace_id,
    safe_attributes as _safe_attributes,
    safe_enum_value as _safe_enum_value,
    safe_set_attribute as _safe_set_attribute,
    safe_set_status as _safe_set_status,
    safe_source as _safe_source,
    safe_span_name as _safe_span_name,
    safe_warning as _safe_warning,
    trace_id_from_span as _trace_id_from_span,
    valid_trace_id as _valid_trace_id,
)

# 保留现有测试和内部诊断使用的兼容名称；实现归属已移至 tracing_export.py。
_SafeExporter = SafeExporter
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
        provider.add_span_processor(BatchSpanProcessor(SafeExporter(exporter)))
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
