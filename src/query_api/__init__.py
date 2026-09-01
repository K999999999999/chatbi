"""Query API Adapter（查询接口适配层）公共入口。"""

from .app import QueryService, create_app

__all__ = ["QueryService", "create_app"]
