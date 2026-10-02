"""Query API 的真实入口；资源在 lifespan 启动阶段创建。"""

from src.bootstrap.runtime import create_runtime

from .app import create_app

app = create_app(runtime_factory=create_runtime)
