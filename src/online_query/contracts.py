"""Online Query（在线查询）的稳定类型契约。"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Mapping, Protocol, TypeAlias


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


@dataclass(frozen=True, slots=True)
class QueryContext:
    """Prompt（提示词）上下文及 SQL Guard（SQL 安全校验）白名单。"""

    prompt_context: str
    allowed_tables: frozenset[str]
    allowed_columns: Mapping[str, frozenset[str]]


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
