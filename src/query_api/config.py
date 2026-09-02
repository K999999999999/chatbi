"""Query API 启动配置加载。"""

from pathlib import Path

from dotenv import load_dotenv


_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def load_local_environment(env_file: Path | None = None) -> None:
    """加载本地 .env，并保留外部环境变量的优先级。

    本地开发时默认读取项目根目录的 .env。正式环境通常不提供该文件，
    而是由部署平台注入环境变量或 Secret，因此缺少文件本身不会导致启动失败。
    必填配置仍由各自的配置工厂负责校验。
    """

    path = _PROJECT_ROOT / ".env" if env_file is None else env_file
    load_dotenv(dotenv_path=path, override=False)
