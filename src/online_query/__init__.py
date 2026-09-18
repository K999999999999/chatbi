"""Online Query（在线查询）模块的稳定数据 Contract。"""

from .contracts import (
    QueryFailure,
    QueryRequest,
    QueryResult,
    QuerySuccess,
)

__all__ = [
    "QueryFailure",
    "QueryRequest",
    "QueryResult",
    "QuerySuccess",
]
