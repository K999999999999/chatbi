"""ChatBI 用户名规范化 Contract。"""

from __future__ import annotations


class UsernameConfigurationError(ValueError):
    """用户名不符合 ChatBI 账号 Contract。"""


def normalize_username(username: str) -> str:
    """规范化用户名，避免大小写造成重复账号。"""

    if not isinstance(username, str):
        raise UsernameConfigurationError("用户名必须是字符串")
    normalized = username.strip().lower()
    if (
        not normalized
        or len(normalized) > 128
        or any(char.isspace() for char in normalized)
    ):
        raise UsernameConfigurationError(
            "用户名不能为空、不能包含空白字符且长度不能超过 128 位"
        )
    return normalized
