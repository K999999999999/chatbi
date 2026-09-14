"""Application Port（应用端口）的最小中立接口。"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Protocol, Self, TypeAlias, runtime_checkable

from ..domain.models import TableRef
from .contracts import (
    CollectionKind,
    PublishedRetrievalSnapshot,
    RawRetrievalHit,
    SanitizedColumnPayload,
    SanitizedMetricPayload,
    SanitizedPayload,
    SanitizedTablePayload,
)

if TYPE_CHECKING:
    from ..contracts import QueryContext, QueryData, ValidatedSQL


TraceAttributeValue: TypeAlias = str | bool | int | float | Sequence[str | bool | int | float]
TraceAttributes: TypeAlias = Mapping[str, TraceAttributeValue]


class RetrievalAssetError(RuntimeError):
    """检索资产端口返回的受控技术错误基类。"""


class OpaqueQueryVector(Protocol):
    """查询向量的不可解释句柄，Application 不读取其内部结构。"""


@runtime_checkable
class RetrievalAssetPort(Protocol):
    """发布资产和检索能力的最小端口。"""

    def load_snapshot(self) -> PublishedRetrievalSnapshot:
        """返回同一发布版本的不可变 Snapshot。"""

    def embed(
        self,
        snapshot: PublishedRetrievalSnapshot,
        text: str,
    ) -> OpaqueQueryVector:
        """基于 Snapshot 生成查询向量句柄。"""

    def search(
        self,
        snapshot: PublishedRetrievalSnapshot,
        collection_kind: CollectionKind,
        vector: OpaqueQueryVector,
        limit: int,
        table_filter: frozenset[TableRef] | None = None,
    ) -> tuple[RawRetrievalHit, ...]:
        """按逻辑集合和受控表过滤返回脱敏命中。"""


class SQLGenerator(Protocol):
    """SQL 候选生成端口。"""

    def generate(self, prompt: str) -> str:
        """生成 SQL 候选或受控的不可回答结果。"""


class SQLGuard(Protocol):
    """SQL 范围和 AST 安全校验端口。"""

    def validate(self, candidate: str, context: QueryContext) -> ValidatedSQL:
        """校验 SQL 候选并返回已校验 SQL。"""


class QueryExecutor(Protocol):
    """只读查询执行端口。"""

    def execute(self, sql: ValidatedSQL) -> QueryData:
        """执行已经通过 Guard 的 SQL。"""


class SpanScope(Protocol):
    """一个实际执行节点的安全作用域。"""

    @property
    def trace_id(self) -> str: ...

    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: object,
    ) -> bool | None: ...


class TraceScope(SpanScope, Protocol):
    """一次查询根 Trace 的拥有或借用作用域。"""

    @property
    def owns_root(self) -> bool: ...


class TraceRecorder(Protocol):
    """Application 唯一依赖的 Trace 记录端口。"""

    def query_trace(
        self,
        source: str,
        carrier: Mapping[str, str] | None = None,
        attributes: TraceAttributes | None = None,
    ) -> TraceScope:
        """创建或借用根 Trace，记录失败不得阻断业务。"""

    def span(
        self,
        name: str,
        attributes: TraceAttributes | None = None,
    ) -> SpanScope:
        """创建一个实际执行的子 Span。"""

    def enrich_current(
        self,
        attributes: TraceAttributes | None = None,
        outcome: str | None = None,
        error_type: str | None = None,
        error_code: str | None = None,
    ) -> None:
        """写入安全属性，记录失败不得阻断业务。"""


__all__ = [
    "CollectionKind",
    "OpaqueQueryVector",
    "PublishedRetrievalSnapshot",
    "QueryExecutor",
    "RawRetrievalHit",
    "RetrievalAssetError",
    "RetrievalAssetPort",
    "SQLGenerator",
    "SQLGuard",
    "SanitizedColumnPayload",
    "SanitizedMetricPayload",
    "SanitizedPayload",
    "SanitizedTablePayload",
    "SpanScope",
    "TraceRecorder",
    "TraceScope",
]
