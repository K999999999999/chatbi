"""把 Provider 异常映射为有限、无正文的 Trace 分类。"""

from enum import StrEnum
from typing import Any


class ProviderErrorCategory(StrEnum):
    TIMEOUT = "TIMEOUT"
    CONNECTION = "CONNECTION"
    RATE_LIMITED = "RATE_LIMITED"
    AUTHENTICATION = "AUTHENTICATION"
    CLIENT_ERROR = "CLIENT_ERROR"
    SERVER_ERROR = "SERVER_ERROR"
    UNKNOWN = "UNKNOWN"


_TYPE_CATEGORIES = {
    "APITimeoutError": ProviderErrorCategory.TIMEOUT,
    "TimeoutError": ProviderErrorCategory.TIMEOUT,
    "TimeoutException": ProviderErrorCategory.TIMEOUT,
    "ConnectTimeout": ProviderErrorCategory.TIMEOUT,
    "ReadTimeout": ProviderErrorCategory.TIMEOUT,
    "WriteTimeout": ProviderErrorCategory.TIMEOUT,
    "PoolTimeout": ProviderErrorCategory.TIMEOUT,
    "APIConnectionError": ProviderErrorCategory.CONNECTION,
    "ConnectionError": ProviderErrorCategory.CONNECTION,
    "ConnectError": ProviderErrorCategory.CONNECTION,
    "NetworkError": ProviderErrorCategory.CONNECTION,
    "ReadError": ProviderErrorCategory.CONNECTION,
    "WriteError": ProviderErrorCategory.CONNECTION,
    "RemoteProtocolError": ProviderErrorCategory.CONNECTION,
    "RateLimitError": ProviderErrorCategory.RATE_LIMITED,
    "AuthenticationError": ProviderErrorCategory.AUTHENTICATION,
    "PermissionDeniedError": ProviderErrorCategory.AUTHENTICATION,
}
_CATEGORY_PRIORITY = {
    ProviderErrorCategory.TIMEOUT: 0,
    ProviderErrorCategory.RATE_LIMITED: 1,
    ProviderErrorCategory.AUTHENTICATION: 2,
    ProviderErrorCategory.SERVER_ERROR: 3,
    ProviderErrorCategory.CLIENT_ERROR: 4,
    ProviderErrorCategory.CONNECTION: 5,
    ProviderErrorCategory.UNKNOWN: 9,
}
_RETRYABLE_CATEGORIES = frozenset(
    {
        ProviderErrorCategory.TIMEOUT,
        ProviderErrorCategory.CONNECTION,
        ProviderErrorCategory.RATE_LIMITED,
        ProviderErrorCategory.SERVER_ERROR,
    }
)


def provider_failure_attributes(error: BaseException) -> dict[str, Any]:
    """提取固定错误分类、有限 HTTP 状态和可重试分类，不输出原始异常。"""

    categories: list[ProviderErrorCategory] = []
    status_code = None
    for item in _exception_chain(error):
        category = _TYPE_CATEGORIES.get(type(item).__name__)
        if category is not None:
            categories.append(category)
        candidate_status = _http_status_code(item)
        if status_code is None and candidate_status is not None:
            status_code = candidate_status
        if candidate_status is not None:
            status_category = _status_category(candidate_status)
            if status_category is not None:
                categories.append(status_category)

    category = (
        min(categories, key=_CATEGORY_PRIORITY.__getitem__)
        if categories
        else ProviderErrorCategory.UNKNOWN
    )
    attributes: dict[str, Any] = {
        "chatbi.provider.error_category": category.value,
    }
    if status_code is not None:
        attributes["chatbi.provider.http_status_code"] = status_code
    if category != ProviderErrorCategory.UNKNOWN:
        attributes["chatbi.provider.retryable"] = category in _RETRYABLE_CATEGORIES
    return attributes


def _exception_chain(error: BaseException):
    seen: set[int] = set()
    current: BaseException | None = error
    for _ in range(8):
        if current is None or id(current) in seen:
            return
        seen.add(id(current))
        yield current
        current = current.__cause__ or current.__context__


def _http_status_code(error: BaseException) -> int | None:
    try:
        value = getattr(error, "status_code", None)
    except Exception:  # noqa: BLE001 - diagnostic extraction must never mask provider failure.
        return None
    if isinstance(value, int) and not isinstance(value, bool) and 100 <= value <= 599:
        return value
    return None


def _status_category(status_code: int) -> ProviderErrorCategory | None:
    if status_code in {408, 504}:
        return ProviderErrorCategory.TIMEOUT
    if status_code == 429:
        return ProviderErrorCategory.RATE_LIMITED
    if status_code in {401, 403}:
        return ProviderErrorCategory.AUTHENTICATION
    if status_code >= 500:
        return ProviderErrorCategory.SERVER_ERROR
    if status_code >= 400:
        return ProviderErrorCategory.CLIENT_ERROR
    return None
