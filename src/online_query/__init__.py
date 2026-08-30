"""Online Query（在线查询）模块公共入口。"""

from .contracts import (
    QueryFailure,
    QueryRequest,
    QueryResult,
    QuerySuccess,
)
from .service import OnlineQueryService


__all__ = [
    "OnlineQueryService",
    "QueryFailure",
    "QueryRequest",
    "QueryResult",
    "QuerySuccess",
]
