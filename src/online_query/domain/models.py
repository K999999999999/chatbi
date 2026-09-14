"""不依赖技术实现的 Online Query Domain（在线查询领域）值对象。

本模块只表达身份、目录事实和版本绑定，不负责检索、SQL 解析或查询编排。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TypeAlias


def _required_text(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} 必须是非空字符串")
    return value.strip()


def _text_tuple(values: tuple[str, ...], field_name: str) -> tuple[str, ...]:
    normalized = tuple(values)
    if any(not isinstance(value, str) or not value.strip() for value in normalized):
        raise ValueError(f"{field_name} 只能包含非空字符串")
    return tuple(value.strip() for value in normalized)


class OpaqueSnapshotIdentity:
    """一次已发布资产快照的进程内身份令牌。

    令牌只支持同一对象比较，且明确禁止序列化；调用方只能把它作为来源闭包
    的校验值传递，不能从中取得物理资源信息。
    """

    __slots__ = ("__token",)

    def __init__(self) -> None:
        self.__token = object()

    def __eq__(self, other: object) -> bool:
        return self is other

    def __hash__(self) -> int:
        return id(self)

    def __repr__(self) -> str:
        return "<OpaqueSnapshotIdentity>"

    def __reduce__(self) -> object:
        raise TypeError("OpaqueSnapshotIdentity 不允许序列化")


@dataclass(frozen=True, slots=True)
class TableRef:
    """中立的物理表身份。"""

    schema: str
    table: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "schema", _required_text(self.schema, "schema"))
        object.__setattr__(self, "table", _required_text(self.table, "table"))

    @property
    def qualified_name(self) -> str:
        return f"{self.schema}.{self.table}"


@dataclass(frozen=True, slots=True)
class ColumnRef:
    """中立的表字段身份。"""

    table: TableRef
    column: str

    def __post_init__(self) -> None:
        if not isinstance(self.table, TableRef):
            raise TypeError("column.table 必须是 TableRef")
        object.__setattr__(self, "column", _required_text(self.column, "column"))


class FormulaShape(StrEnum):
    """当前已冻结的指标公式形态。"""

    AGGREGATE = "AGGREGATE"
    AGGREGATE_RATIO = "AGGREGATE_RATIO"


class ZeroDivisionGuard(StrEnum):
    """比率指标的零除保护方式。"""

    NULLIF_ZERO = "NULLIF_ZERO"
    NONE = "NONE"


@dataclass(frozen=True, slots=True)
class AggregateSpec:
    """一个受控聚合项的中立描述。"""

    function: str
    distinct: bool
    argument_columns: tuple[ColumnRef, ...]
    argument_shape: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "function",
            _required_text(self.function, "aggregate.function").upper(),
        )
        if not isinstance(self.distinct, bool):
            raise TypeError("aggregate.distinct 必须是 bool")
        columns = tuple(self.argument_columns)
        if any(not isinstance(column, ColumnRef) for column in columns):
            raise TypeError("aggregate.argument_columns 必须全部是 ColumnRef")
        object.__setattr__(self, "argument_columns", columns)
        object.__setattr__(
            self,
            "argument_shape",
            _required_text(self.argument_shape, "aggregate.argument_shape"),
        )


@dataclass(frozen=True, slots=True)
class FormulaStructure:
    """已由基础设施适配器规范化的公式结构。"""

    shape: FormulaShape
    aggregates: tuple[AggregateSpec, ...]
    referenced_columns: tuple[ColumnRef, ...]
    zero_division_guard: ZeroDivisionGuard
    canonical_expression: str

    def __post_init__(self) -> None:
        shape = self.shape if isinstance(self.shape, FormulaShape) else FormulaShape(self.shape)
        guard = (
            self.zero_division_guard
            if isinstance(self.zero_division_guard, ZeroDivisionGuard)
            else ZeroDivisionGuard(self.zero_division_guard)
        )
        aggregates = tuple(self.aggregates)
        columns = tuple(self.referenced_columns)
        if any(not isinstance(item, AggregateSpec) for item in aggregates):
            raise TypeError("formula.aggregates 必须全部是 AggregateSpec")
        if any(not isinstance(item, ColumnRef) for item in columns):
            raise TypeError("formula.referenced_columns 必须全部是 ColumnRef")
        object.__setattr__(self, "shape", shape)
        object.__setattr__(self, "zero_division_guard", guard)
        object.__setattr__(self, "aggregates", aggregates)
        object.__setattr__(self, "referenced_columns", columns)
        object.__setattr__(
            self,
            "canonical_expression",
            _required_text(self.canonical_expression, "formula.canonical_expression"),
        )


FilterValue: TypeAlias = str | int | float | bool | None


@dataclass(frozen=True, slots=True)
class NormalizedFilterCondition:
    """已规范化的、可安全展示的过滤条件。"""

    column: ColumnRef
    operator: str
    value: FilterValue

    def __post_init__(self) -> None:
        if not isinstance(self.column, ColumnRef):
            raise TypeError("filter.column 必须是 ColumnRef")
        object.__setattr__(self, "operator", _required_text(self.operator, "filter.operator"))
        if not isinstance(self.value, (str, int, float, bool)) and self.value is not None:
            raise TypeError("filter.value 只能是受控标量")


@dataclass(frozen=True, slots=True)
class TimeFieldRef:
    """指标日期字段的中立引用。"""

    source_table: TableRef
    source_column: str
    target_table: TableRef
    filter_column: str

    def __post_init__(self) -> None:
        if not isinstance(self.source_table, TableRef):
            raise TypeError("time_field.source_table 必须是 TableRef")
        if not isinstance(self.target_table, TableRef):
            raise TypeError("time_field.target_table 必须是 TableRef")
        object.__setattr__(
            self,
            "source_column",
            _required_text(self.source_column, "time_field.source_column"),
        )
        object.__setattr__(
            self,
            "filter_column",
            _required_text(self.filter_column, "time_field.filter_column"),
        )


@dataclass(frozen=True, slots=True)
class MetricDefinition:
    """同一发布版本中唯一的权威指标业务事实。"""

    asset_version: str
    document_id: str
    metric_name: str
    aliases: tuple[str, ...]
    semantic_text: str
    data_source: TableRef
    formula: FormulaStructure
    time_field: TimeFieldRef
    filters: tuple[NormalizedFilterCondition, ...]
    depends_on: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "asset_version",
            _required_text(self.asset_version, "metric.asset_version"),
        )
        object.__setattr__(
            self,
            "document_id",
            _required_text(self.document_id, "metric.document_id"),
        )
        object.__setattr__(
            self,
            "metric_name",
            _required_text(self.metric_name, "metric.metric_name"),
        )
        object.__setattr__(self, "aliases", _text_tuple(self.aliases, "metric.aliases"))
        object.__setattr__(
            self,
            "semantic_text",
            _required_text(self.semantic_text, "metric.semantic_text"),
        )
        if not isinstance(self.data_source, TableRef):
            raise TypeError("metric.data_source 必须是 TableRef")
        if not isinstance(self.formula, FormulaStructure):
            raise TypeError("metric.formula 必须是 FormulaStructure")
        if not isinstance(self.time_field, TimeFieldRef):
            raise TypeError("metric.time_field 必须是 TimeFieldRef")
        filters = tuple(self.filters)
        if any(not isinstance(item, NormalizedFilterCondition) for item in filters):
            raise TypeError("metric.filters 必须全部是 NormalizedFilterCondition")
        object.__setattr__(self, "filters", filters)
        object.__setattr__(self, "depends_on", _text_tuple(self.depends_on, "metric.depends_on"))


@dataclass(frozen=True, slots=True)
class SnapshotBinding:
    """把值对象绑定到同一个已发布 Snapshot（快照）。"""

    snapshot_identity: OpaqueSnapshotIdentity
    asset_version: str

    def __post_init__(self) -> None:
        if not isinstance(self.snapshot_identity, OpaqueSnapshotIdentity):
            raise TypeError("snapshot_identity 必须是 OpaqueSnapshotIdentity")
        object.__setattr__(
            self,
            "asset_version",
            _required_text(self.asset_version, "snapshot.asset_version"),
        )


@dataclass(frozen=True, slots=True)
class SnapshotBoundMetricDefinition:
    """已经绑定 Snapshot 来源的指标定义。"""

    binding: SnapshotBinding
    value: MetricDefinition

    def __post_init__(self) -> None:
        if not isinstance(self.binding, SnapshotBinding):
            raise TypeError("binding 必须是 SnapshotBinding")
        if not isinstance(self.value, MetricDefinition):
            raise TypeError("value 必须是 MetricDefinition")
        if self.value.asset_version != self.binding.asset_version:
            raise ValueError("MetricDefinition 与 Snapshot 的 asset_version 不一致")

    @property
    def snapshot_identity(self) -> OpaqueSnapshotIdentity:
        return self.binding.snapshot_identity

    @property
    def asset_version(self) -> str:
        return self.binding.asset_version


@dataclass(frozen=True, slots=True)
class TableCatalogEntry:
    """Snapshot-owned 的已校验 TABLE 目录事实。"""

    document_id: str
    table_ref: TableRef
    semantic_text: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "document_id", _required_text(self.document_id, "table.document_id"))
        if not isinstance(self.table_ref, TableRef):
            raise TypeError("table.table_ref 必须是 TableRef")
        object.__setattr__(self, "semantic_text", _required_text(self.semantic_text, "table.semantic_text"))


@dataclass(frozen=True, slots=True)
class ColumnCatalogEntry:
    """Snapshot-owned 的已校验 COLUMN 目录事实。"""

    document_id: str
    table_ref: TableRef
    column_name: str
    semantic_text: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "document_id", _required_text(self.document_id, "column.document_id"))
        if not isinstance(self.table_ref, TableRef):
            raise TypeError("column.table_ref 必须是 TableRef")
        object.__setattr__(self, "column_name", _required_text(self.column_name, "column.column_name"))
        object.__setattr__(self, "semantic_text", _required_text(self.semantic_text, "column.semantic_text"))


@dataclass(frozen=True, slots=True)
class SnapshotResourceCatalog:
    """一个发布 Snapshot 中的 TABLE/COLUMN 目录。"""

    tables: tuple[TableCatalogEntry, ...]
    columns: tuple[ColumnCatalogEntry, ...]

    def __post_init__(self) -> None:
        tables = tuple(self.tables)
        columns = tuple(self.columns)
        if any(not isinstance(item, TableCatalogEntry) for item in tables):
            raise TypeError("resource_catalog.tables 必须全部是 TableCatalogEntry")
        if any(not isinstance(item, ColumnCatalogEntry) for item in columns):
            raise TypeError("resource_catalog.columns 必须全部是 ColumnCatalogEntry")
        object.__setattr__(self, "tables", tables)
        object.__setattr__(self, "columns", columns)


class RequestShape(StrEnum):
    """读取在线资产前可确定的请求形态。"""

    BASELINE = "BASELINE"
    EXPLICIT_MULTI = "EXPLICIT_MULTI"
    POSSIBLE_MULTI = "POSSIBLE_MULTI"


@dataclass(frozen=True, slots=True)
class MetricMention:
    """用户问题中一个已映射的指标提及。"""

    requested_text: str
    start: int
    end: int
    document_id: str
    metric_name: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "requested_text", _required_text(self.requested_text, "mention.requested_text"))
        if self.start < 0 or self.end < self.start:
            raise ValueError("mention 的文本范围无效")
        object.__setattr__(self, "document_id", _required_text(self.document_id, "mention.document_id"))
        object.__setattr__(self, "metric_name", _required_text(self.metric_name, "mention.metric_name"))


class MetricPlanStatus(StrEnum):
    """确定性指标计划结果。"""

    NOT_MULTI = "NOT_MULTI"
    SUCCESS = "SUCCESS"
    AMBIGUOUS = "AMBIGUOUS"
    NO_METRIC = "NO_METRIC"
    TOO_MANY = "TOO_MANY"
    UNSUPPORTED_COMBINATION = "UNSUPPORTED_COMBINATION"
    INVALID_ASSET = "INVALID_ASSET"


@dataclass(frozen=True, slots=True)
class MetricPlan:
    """绑定同一个 Snapshot 的有序指标计划。"""

    snapshot_identity: OpaqueSnapshotIdentity
    asset_version: str
    request_shape: RequestShape
    ordered_metric_definitions: tuple[SnapshotBoundMetricDefinition, ...]
    raw_mentions: tuple[MetricMention, ...]
    ordered_mentions: tuple[MetricMention, ...]
    status: MetricPlanStatus
    reason: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.snapshot_identity, OpaqueSnapshotIdentity):
            raise TypeError("metric_plan.snapshot_identity 必须是 OpaqueSnapshotIdentity")
        object.__setattr__(self, "asset_version", _required_text(self.asset_version, "metric_plan.asset_version"))
        shape = self.request_shape if isinstance(self.request_shape, RequestShape) else RequestShape(self.request_shape)
        status = self.status if isinstance(self.status, MetricPlanStatus) else MetricPlanStatus(self.status)
        object.__setattr__(self, "request_shape", shape)
        object.__setattr__(self, "status", status)
        definitions = tuple(self.ordered_metric_definitions)
        raw_mentions = tuple(self.raw_mentions)
        ordered_mentions = tuple(self.ordered_mentions)
        if any(not isinstance(item, SnapshotBoundMetricDefinition) for item in definitions):
            raise TypeError("metric_plan.ordered_metric_definitions 类型无效")
        if any(
            item.snapshot_identity is not self.snapshot_identity or item.asset_version != self.asset_version
            for item in definitions
        ):
            raise ValueError("MetricPlan 中的定义必须来自同一 Snapshot 和 asset_version")
        if any(not isinstance(item, MetricMention) for item in raw_mentions + ordered_mentions):
            raise TypeError("metric_plan mentions 类型无效")
        if len(definitions) != len(ordered_mentions):
            raise ValueError("MetricPlan 的定义与有序指标提及数量不一致")
        object.__setattr__(self, "ordered_metric_definitions", definitions)
        object.__setattr__(self, "raw_mentions", raw_mentions)
        object.__setattr__(self, "ordered_mentions", ordered_mentions)


class ProvisionalMetricRequestStatus(StrEnum):
    """指标尚未完成目录解析时的唯一状态。"""

    PENDING_RESOLUTION = "PENDING_RESOLUTION"


@dataclass(frozen=True, slots=True)
class ProvisionalMetricRequest:
    """检索前的请求计划，不声称已经确定指标事实。"""

    snapshot_identity: OpaqueSnapshotIdentity
    asset_version: str
    request_shape: RequestShape
    ordered_mentions: tuple[MetricMention, ...]
    status: ProvisionalMetricRequestStatus = ProvisionalMetricRequestStatus.PENDING_RESOLUTION

    def __post_init__(self) -> None:
        if not isinstance(self.snapshot_identity, OpaqueSnapshotIdentity):
            raise TypeError("provisional.snapshot_identity 必须是 OpaqueSnapshotIdentity")
        object.__setattr__(self, "asset_version", _required_text(self.asset_version, "provisional.asset_version"))
        shape = self.request_shape if isinstance(self.request_shape, RequestShape) else RequestShape(self.request_shape)
        status = self.status if isinstance(self.status, ProvisionalMetricRequestStatus) else ProvisionalMetricRequestStatus(self.status)
        if status is not ProvisionalMetricRequestStatus.PENDING_RESOLUTION:
            raise ValueError("ProvisionalMetricRequest 只能处于 PENDING_RESOLUTION")
        mentions = tuple(self.ordered_mentions)
        if any(not isinstance(item, MetricMention) for item in mentions):
            raise TypeError("provisional.ordered_mentions 类型无效")
        object.__setattr__(self, "request_shape", shape)
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "ordered_mentions", mentions)


@dataclass(frozen=True, slots=True)
class JoinEdge:
    """Relationship Graph（关系图）中的一条结构事实。"""

    edge_id: str
    source_table: str
    target_table: str
    source_columns: tuple[str, ...]
    target_columns: tuple[str, ...]
    constraint_name: str
    direction: str

    def __post_init__(self) -> None:
        for field_name in ("edge_id", "source_table", "target_table", "constraint_name", "direction"):
            object.__setattr__(self, field_name, _required_text(getattr(self, field_name), f"join.{field_name}"))
        object.__setattr__(self, "source_columns", _text_tuple(self.source_columns, "join.source_columns"))
        object.__setattr__(self, "target_columns", _text_tuple(self.target_columns, "join.target_columns"))
        if len(self.source_columns) != len(self.target_columns):
            raise ValueError("Join 两端字段数量必须一致")


class CardinalityProofKind(StrEnum):
    """已发布关系图中的 Join 基数证明类型。"""

    FOREIGN_KEY_TO_PRIMARY_KEY = "FOREIGN_KEY_TO_PRIMARY_KEY"
    FOREIGN_KEY_TO_UNIQUE = "FOREIGN_KEY_TO_UNIQUE"


@dataclass(frozen=True, slots=True)
class CardinalityProof:
    """Relationship Graph 已验证基数事实的中立投影。"""

    snapshot_identity: OpaqueSnapshotIdentity
    asset_version: str
    edge_id: str
    source_table: str
    source_columns: tuple[str, ...]
    target_table: str
    target_columns: tuple[str, ...]
    proof_kind: CardinalityProofKind

    def __post_init__(self) -> None:
        if not isinstance(self.snapshot_identity, OpaqueSnapshotIdentity):
            raise TypeError("proof.snapshot_identity 必须是 OpaqueSnapshotIdentity")
        object.__setattr__(self, "asset_version", _required_text(self.asset_version, "proof.asset_version"))
        for field_name in ("edge_id", "source_table", "target_table"):
            object.__setattr__(self, field_name, _required_text(getattr(self, field_name), f"proof.{field_name}"))
        object.__setattr__(self, "source_columns", _text_tuple(self.source_columns, "proof.source_columns"))
        object.__setattr__(self, "target_columns", _text_tuple(self.target_columns, "proof.target_columns"))
        kind = self.proof_kind if isinstance(self.proof_kind, CardinalityProofKind) else CardinalityProofKind(self.proof_kind)
        object.__setattr__(self, "proof_kind", kind)
        if len(self.source_columns) != len(self.target_columns):
            raise ValueError("基数证明两端字段数量必须一致")


@dataclass(frozen=True, slots=True)
class RelationshipGraphFacts:
    """已校验的关系边和基数证明集合。"""

    edges: tuple[JoinEdge, ...] = ()
    cardinality_proofs: tuple[CardinalityProof, ...] = ()

    def __post_init__(self) -> None:
        edges = tuple(self.edges)
        proofs = tuple(self.cardinality_proofs)
        if any(not isinstance(item, JoinEdge) for item in edges):
            raise TypeError("graph.edges 必须全部是 JoinEdge")
        if any(not isinstance(item, CardinalityProof) for item in proofs):
            raise TypeError("graph.cardinality_proofs 必须全部是 CardinalityProof")
        object.__setattr__(self, "edges", edges)
        object.__setattr__(self, "cardinality_proofs", proofs)


@dataclass(frozen=True, slots=True)
class EmbeddingFingerprint:
    """发布 Snapshot 的 Embedding 配置指纹。"""

    model: str
    dimension: int
    retrieval_profile: str = "dense+sparse"

    def __post_init__(self) -> None:
        object.__setattr__(self, "model", _required_text(self.model, "embedding.model"))
        if not isinstance(self.dimension, int) or self.dimension <= 0:
            raise ValueError("embedding.dimension 必须是正整数")
        object.__setattr__(self, "retrieval_profile", _required_text(self.retrieval_profile, "embedding.retrieval_profile"))
