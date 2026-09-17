"""SQL Guard（SQL 安全校验）子模块公共入口。"""

from .sql_guard import (
    ALLOWED_SCHEMA,
    SQLRejectedError,
    _new_validation_session,
    _parse_single_select,
    validate_candidate_scope,
    validate_multi_metric_sql,
    validate_sql,
)


__all__ = [
    "ALLOWED_SCHEMA",
    "SQLRejectedError",
    "validate_candidate_scope",
    "validate_multi_metric_sql",
    "validate_sql",
]
