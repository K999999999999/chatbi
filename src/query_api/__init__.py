"""Query API Adapter（查询接口适配层）公共入口。"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .app import QueryService, create_app

__all__ = ["QueryService", "create_app"]


def __getattr__(name: str):
    """轻量子模块不加载 HTTP 应用；保留既有公共入口。"""
    if name not in __all__:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    from .app import QueryService, create_app

    globals().update(QueryService=QueryService, create_app=create_app)
    return globals()[name]
