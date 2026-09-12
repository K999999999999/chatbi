"""ChatBI Observability（可观测性）T1 的稳定入口。"""

from .config import ObservabilityConfig
from .contracts import (
    ErrorType,
    QuerySource,
    SpanScope,
    TraceOutcome,
    TraceRecorder,
    TraceScope,
)
from .tracing import (
    SafeTraceRecorder,
    create_in_memory_recorder,
    create_trace_recorder,
)

__all__ = [
    "ErrorType",
    "ObservabilityConfig",
    "QuerySource",
    "SafeTraceRecorder",
    "SpanScope",
    "TraceOutcome",
    "TraceRecorder",
    "TraceScope",
    "create_in_memory_recorder",
    "create_trace_recorder",
]
