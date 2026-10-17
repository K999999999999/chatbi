"""本机敏感配置文件的属主和权限检查。"""

import os
from pathlib import Path
import stat


_UNSAFE_ENVIRONMENT_FILE = (
    "本地配置必须由当前用户拥有且仅当前用户可读；请检查属主并执行 chmod 600 <配置文件> 后重试。"
)


def validate_environment_file(path: Path) -> None:
    """在读取配置前拒绝非普通文件、非当前用户文件和宽松权限。"""

    try:
        metadata = path.stat()
    except OSError:
        raise PermissionError(_UNSAFE_ENVIRONMENT_FILE) from None

    mode = stat.S_IMODE(metadata.st_mode)
    if (
        not stat.S_ISREG(metadata.st_mode)
        or metadata.st_uid != os.getuid()
        or not mode & 0o400
        or mode & ~0o600
    ):
        raise PermissionError(_UNSAFE_ENVIRONMENT_FILE)
