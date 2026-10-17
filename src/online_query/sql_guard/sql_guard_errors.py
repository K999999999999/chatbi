"""SQL Guard 的公共异常 Contract。"""

from enum import StrEnum


class SQLGuardRejectionCode(StrEnum):
    """Trace 允许记录的有限拒绝原因；不包含 Candidate 或原始消息。"""

    UNCLASSIFIED = "UNCLASSIFIED"
    CANDIDATE_INVALID = "CANDIDATE_INVALID"
    SQL_PARSE_ERROR = "SQL_PARSE_ERROR"
    STATEMENT_COUNT_INVALID = "STATEMENT_COUNT_INVALID"
    SELECT_ONLY = "SELECT_ONLY"
    SUBQUERY_UNSUPPORTED = "SUBQUERY_UNSUPPORTED"
    FORBIDDEN_OPERATION = "FORBIDDEN_OPERATION"
    UNSUPPORTED_FEATURE = "UNSUPPORTED_FEATURE"
    UNAPPROVED_FUNCTION = "UNAPPROVED_FUNCTION"
    TABLE_SCOPE_REJECTED = "TABLE_SCOPE_REJECTED"
    COLUMN_SCOPE_REJECTED = "COLUMN_SCOPE_REJECTED"
    JOIN_CONSTRAINT_REJECTED = "JOIN_CONSTRAINT_REJECTED"
    METRIC_CONSTRAINT_REJECTED = "METRIC_CONSTRAINT_REJECTED"
    MULTI_METRIC_CONSTRAINT_REJECTED = "MULTI_METRIC_CONSTRAINT_REJECTED"


class SQLRejectedError(RuntimeError):
    """SQL 候选不满足只读白名单契约。"""

    def __init__(
        self,
        message: str,
        *,
        reason_code: SQLGuardRejectionCode | None = None,
    ) -> None:
        super().__init__(message)
        self.reason_code = reason_code
