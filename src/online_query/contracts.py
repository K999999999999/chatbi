"""Online Query（在线查询）的稳定类型契约。"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Mapping, Protocol, TypeAlias

from .query_understanding import ValidatedSemanticQuery


class QueryErrorCode(StrEnum):
    """Module Spec（模块规格）定义的公开错误码。"""

    INVALID_REQUEST = "INVALID_REQUEST"
    CONTEXT_ERROR = "CONTEXT_ERROR"
    LLM_ERROR = "LLM_ERROR"
    CANNOT_ANSWER = "CANNOT_ANSWER"
    SQL_REJECTED = "SQL_REJECTED"
    DATABASE_ERROR = "DATABASE_ERROR"
    QUERY_TIMEOUT = "QUERY_TIMEOUT"


@dataclass(frozen=True, slots=True)
class QueryRequest:
    question: str
    request_id: str | None = None


@dataclass(frozen=True, slots=True)
class QuerySuccess:
    request_id: str
    sql: str
    columns: tuple[str, ...]
    rows: tuple[tuple[object, ...], ...]
    row_count: int
    truncated: bool


@dataclass(frozen=True, slots=True)
class QueryFailure:
    request_id: str
    error_code: QueryErrorCode
    error_message: str


QueryResult: TypeAlias = QuerySuccess | QueryFailure


class RequestShape(StrEnum):
    """读取在线资产前可确定的请求形态。"""

    BASELINE = "BASELINE"
    EXPLICIT_MULTI = "EXPLICIT_MULTI"
    POSSIBLE_MULTI = "POSSIBLE_MULTI"


class FallbackPolicy(StrEnum):
    """技术故障时是否允许使用静态上下文。"""

    ALLOW_STATIC = "ALLOW_STATIC"
    FAIL_CLOSED = "FAIL_CLOSED"


@dataclass(frozen=True, slots=True)
class RetrievalRequest:
    """Online Retrieval 使用的内部请求。"""

    question: str
    request_shape: RequestShape
    fallback_policy: FallbackPolicy
    semantic_query: ValidatedSemanticQuery | None = None


@dataclass(frozen=True, slots=True)
class MetricMention:
    """用户问题中一个已映射的指标提及。"""

    requested_text: str
    start: int
    end: int
    document_id: str
    metric_name: str


@dataclass(frozen=True, slots=True)
class MetricConstraint:
    """一个请求指标的认证业务约束。"""

    ordinal: int
    requested_text: str
    document_id: str
    metric_name: str
    formula: str
    data_source: str
    time_field: str
    filters: tuple[str, ...]
    depends_on: tuple[str, ...]


class MetricPlanStatus(StrEnum):
    """确定性指标请求计划结果。"""

    SUCCESS = "SUCCESS"
    AMBIGUOUS = "AMBIGUOUS"
    NO_METRIC = "NO_METRIC"
    TOO_MANY = "TOO_MANY"
    UNSUPPORTED_COMBINATION = "UNSUPPORTED_COMBINATION"
    INVALID_ASSET = "INVALID_ASSET"


@dataclass(frozen=True, slots=True)
class MetricRequestPlan:
    """指标解析、去重和兼容检查的输出。"""

    status: MetricPlanStatus
    request: RetrievalRequest
    mentions: tuple[MetricMention, ...] = ()
    constraints: tuple[MetricConstraint, ...] = ()
    reason: str = ""


class RetrievalStatus(StrEnum):
    """Online Retrieval（在线检索）对外暴露的状态。"""

    SUCCESS = "SUCCESS"
    NO_TABLE_HIT = "NO_TABLE_HIT"
    NO_REQUIRED_COLUMN_HIT = "NO_REQUIRED_COLUMN_HIT"
    NO_METRIC_HIT = "NO_METRIC_HIT"
    PARTIAL_UNREACHABLE = "PARTIAL_UNREACHABLE"
    AMBIGUOUS = "AMBIGUOUS"
    ASSET_UNAVAILABLE = "ASSET_UNAVAILABLE"
    RETRIEVAL_UNAVAILABLE = "RETRIEVAL_UNAVAILABLE"
    EMBEDDING_UNAVAILABLE = "EMBEDDING_UNAVAILABLE"
    FALLBACK_STATIC_SCHEMA = "FALLBACK_STATIC_SCHEMA"


@dataclass(frozen=True, slots=True)
class RetrievalConfig:
    """V1 在线 Dense Retrieval（稠密检索）配置。"""

    table_top_k: int = 5
    column_top_k: int = 20
    metric_top_k: int = 10
    table_score_threshold: float = 0.30
    column_score_threshold: float = 0.25
    metric_score_threshold: float = 0.30

    def __post_init__(self) -> None:
        if self.table_top_k <= 0 or self.column_top_k <= 0 or self.metric_top_k <= 0:
            raise ValueError("Retrieval Top-K 必须为正数")
        thresholds = (
            self.table_score_threshold,
            self.column_score_threshold,
            self.metric_score_threshold,
        )
        if any(not 0.0 <= value <= 1.0 for value in thresholds):
            raise ValueError("Retrieval score threshold 必须位于 0 到 1 之间")


@dataclass(frozen=True, slots=True)
class TableHit:
    """一条 TABLE 检索命中。"""

    document_id: str
    schema_name: str
    table_name: str
    table_role: str
    score: float
    rank: int
    metadata: Mapping[str, Any]
    page_content: str = ""

    @property
    def qualified_name(self) -> str:
        return f"{self.schema_name}.{self.table_name}"


@dataclass(frozen=True, slots=True)
class ColumnHit:
    """一条 COLUMN 检索命中。"""

    document_id: str
    schema_name: str
    table_name: str
    column_name: str
    data_type: str
    score: float
    rank: int
    metadata: Mapping[str, Any]
    page_content: str = ""

    @property
    def qualified_table(self) -> str:
        return f"{self.schema_name}.{self.table_name}"


@dataclass(frozen=True, slots=True)
class MetricHit:
    """一条 METRIC 检索命中。"""

    document_id: str
    metric_name: str
    score: float
    rank: int
    metadata: Mapping[str, Any]
    page_content: str


@dataclass(frozen=True, slots=True)
class JoinEdge:
    """Relationship Graph（关系图）中的一条可解释 Join 边。"""

    edge_id: str
    source_table: str
    target_table: str
    source_columns: tuple[str, ...]
    target_columns: tuple[str, ...]
    constraint_name: str
    direction: str


@dataclass(frozen=True, slots=True)
class JoinConstraint:
    """SQL 允许使用的一条安全 Join 约束。"""

    source_table: str
    source_columns: tuple[str, ...]
    target_table: str
    target_columns: tuple[str, ...]
    uniqueness_basis: str
    direction: str


@dataclass(frozen=True, slots=True)
class QueryContext:
    """Prompt（提示词）上下文及 SQL Guard（SQL 安全校验）白名单。"""

    prompt_context: str
    allowed_tables: frozenset[str]
    allowed_columns: Mapping[str, frozenset[str]]
    request_shape: RequestShape = RequestShape.BASELINE
    metric_constraints: tuple[MetricConstraint, ...] = ()
    join_constraints: tuple[JoinConstraint, ...] = ()


@dataclass(frozen=True, slots=True)
class JoinPath:
    """从 Anchor 到目标表的一条直接合法路径。"""

    tables: tuple[str, ...]
    edges: tuple[JoinEdge, ...]


@dataclass(frozen=True, slots=True)
class JoinResolution:
    """关系图解析后的路径和最终 Join 边。"""

    anchor_table: str | None
    paths: tuple[JoinPath, ...]
    joins: tuple[JoinEdge, ...]
    unreachable_tables: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MetricRetrievalEvidence:
    """一个用户指标项在一次综合 METRIC 检索中的覆盖证据。"""

    requested_text: str
    target_document_id: str
    hits: tuple[MetricHit, ...]


@dataclass(frozen=True, slots=True)
class RetrievalEvidence:
    """用于评测、调试和追踪的原始检索证据。"""

    table_hits: tuple[TableHit, ...] = ()
    column_hits: tuple[ColumnHit, ...] = ()
    metric_hits: tuple[MetricHit, ...] = ()
    metric_queries: tuple[MetricRetrievalEvidence, ...] = ()
    join_paths: tuple[JoinPath, ...] = ()


@dataclass(frozen=True, slots=True)
class OnlineRetrievalResult:
    """Online Retrieval（在线检索）的完整结果包。"""

    status: RetrievalStatus
    request_shape: RequestShape = RequestShape.BASELINE
    fallback_policy: FallbackPolicy = FallbackPolicy.FAIL_CLOSED
    internal_reason: str | None = None
    asset_version: str | None = None
    tables: tuple[TableHit, ...] = ()
    fields: tuple[ColumnHit, ...] = ()
    metrics: tuple[MetricHit, ...] = ()
    join_path: JoinResolution | None = None
    dynamic_schema: str = ""
    indicator_context: str = ""
    evidence: RetrievalEvidence = RetrievalEvidence()
    warnings: tuple[str, ...] = ()
    query_context: QueryContext | None = None
    metric_constraints: tuple[MetricConstraint, ...] = ()
    join_constraints: tuple[JoinConstraint, ...] = ()

    def to_query_context(self) -> QueryContext:
        """返回成功检索生成的动态 QueryContext。"""

        if self.query_context is None:
            raise ValueError("检索结果没有可用的 QueryContext")
        return self.query_context


class RetrievalProvider(Protocol):
    """Online Query（在线查询）使用的最小检索依赖。"""

    def retrieve(
        self,
        question: str | RetrievalRequest,
    ) -> OnlineRetrievalResult:
        """根据用户问题或已判定的内部请求返回检索结果。"""


@dataclass(frozen=True, slots=True)
class ValidatedSQL:
    """已经通过 SQL Guard（SQL 安全校验）的 SQL。"""

    sql: str


@dataclass(frozen=True, slots=True)
class QueryData:
    columns: tuple[str, ...]
    rows: tuple[tuple[object, ...], ...]
    truncated: bool


class SQLGenerator(Protocol):
    def generate(self, prompt: str) -> str:
        """生成一条 SQL 候选或精确的 ``CANNOT_ANSWER``。"""


class QueryExecutor(Protocol):
    def execute(self, sql: ValidatedSQL) -> QueryData:
        """执行已经通过校验的 SQL。"""
