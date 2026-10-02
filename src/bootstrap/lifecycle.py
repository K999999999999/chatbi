"""本次装配持有的资源清理；不隐藏原始启动错误。"""

import logging
from collections.abc import Awaitable, Callable
from contextlib import AsyncExitStack, ExitStack

_LOGGER = logging.getLogger(__name__)


def register_cleanup(
    stack: ExitStack | AsyncExitStack, name: str, close: Callable[[], None]
) -> None:
    """获取成功后登记逆序释放，单个失败不阻止其他资源释放。"""

    def cleanup() -> None:
        try:
            close()
        except Exception as error:
            _LOGGER.warning(
                "Resource cleanup failed: resource=%s error_type=%s",
                name,
                type(error).__name__,
            )

    stack.callback(cleanup)


def register_async_cleanup(
    stack: AsyncExitStack, name: str, close: Callable[[], Awaitable[None]]
) -> None:
    """在应用事件循环内等待异步客户端关闭，失败时仍继续清理。"""

    async def cleanup() -> None:
        try:
            await close()
        except Exception as error:
            _LOGGER.warning(
                "Resource cleanup failed: resource=%s error_type=%s",
                name,
                type(error).__name__,
            )

    stack.push_async_callback(cleanup)
