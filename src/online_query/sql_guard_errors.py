"""SQL Guard 的公共异常 Contract。"""


class SQLRejectedError(RuntimeError):
    """SQL 候选不满足只读白名单契约。"""
