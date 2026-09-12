"""Observability（可观测性）向业务层暴露的最小 Contract（契约）。"""

from collections.abc import Mapping, Sequence
from enum import StrEnum
from typing import Any, Protocol, TypeAlias


AttributeValue: TypeAlias = str | bool | int | float | Sequence[str | bool | int | float]
Attributes: TypeAlias = Mapping[str, AttributeValue]
Carrier: TypeAlias = Mapping[str, str]


class QuerySource(StrEnum):
    """创建 Query Trace（查询链路）的可信进程内来源。"""

    HTTP = "HTTP"
    INTERNAL = "INTERNAL"
    EVALUATION = "EVALUATION"


class TraceOutcome(StrEnum):
    """Trace 中允许记录的固定业务结果分类。"""

    SUCCESS = "SUCCESS"
    BUSINESS_REJECTION = "BUSINESS_REJECTION"
    TECHNICAL_FAILURE = "TECHNICAL_FAILURE"
    TIMEOUT = "TIMEOUT"
    FALLBACK_SUCCESS = "FALLBACK_SUCCESS"


class ErrorType(StrEnum):
    """Trace 中允许记录的安全错误分类。"""

    CONFIGURATION = "CONFIGURATION"
    EXPORTER = "EXPORTER"
    INSTRUMENTATION = "INSTRUMENTATION"
    VALIDATION = "VALIDATION"
    RETRIEVAL = "RETRIEVAL"
    LLM = "LLM"
    DATABASE = "DATABASE"
    TIMEOUT = "TIMEOUT"
    SQL_GUARD = "SQL_GUARD"
    UNKNOWN = "UNKNOWN"


class SpanScope(Protocol):
    """一个实际执行节点的安全作用域。"""

    @property
    def trace_id(self) -> str:
        """返回小写 32 位十六进制 Trace ID。"""

    def __enter__(self) -> "SpanScope": ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: Any,
    ) -> bool | None: ...


class TraceScope(SpanScope, Protocol):
    """一次 Query Trace 的拥有或借用作用域。"""

    @property
    def owns_root(self) -> bool:
        """是否负责结束 Root Span（根链路）和清理 Context。"""


class TraceRecorder(Protocol):
    """业务代码唯一依赖的 Trace Recorder（链路记录器）。"""

    def query_trace(
        self,
        source: QuerySource | str,
        carrier: Carrier | None = None,
        attributes: Attributes | None = None,
    ) -> TraceScope:
        """创建或借用 ``query.request``，且不会向调用方抛出异常。"""

    def span(
        self,
        name: str,
        attributes: Attributes | None = None,
    ) -> SpanScope:
        """创建一个实际执行的子 Span，且不会向调用方抛出异常。"""

    def enrich_current(
        self,
        attributes: Attributes | None = None,
        outcome: TraceOutcome | str | None = None,
        error_type: ErrorType | str | None = None,
        error_code: str | None = None,
    ) -> None:
        """向当前 Span 写入安全属性，且不会向调用方抛出异常。"""
