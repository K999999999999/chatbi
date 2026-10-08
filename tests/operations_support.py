"""确定性HTTP测试显式注入依赖证据与真实容量runtime。"""

import pytest

from src.query_api.app import create_app as production_app
from src.query_api.execution_runtime import ExecutionRuntime
from src.query_api.operations import DEPENDENCIES, OperationsState

_runtimes = []


def ready_operations():
    state = OperationsState(clock=lambda: 0.0)
    state.record_checks(dict.fromkeys(DEPENDENCIES, "ready"))
    return state


def create_app(*args, **kwargs):
    if kwargs.get("runtime_factory") is None:
        kwargs.setdefault("operations", ready_operations())
    app = production_app(*args, **kwargs)
    if kwargs.get("runtime_factory") is None:
        # 兼容无lifespan的窄HTTP测试；正式runtime仍由生产lifespan装配。
        runtime = ExecutionRuntime(None, None)
        app.state.execution_runtime = runtime
        _runtimes.append(runtime)
    return app


@pytest.fixture(autouse=True)
def close_test_capacity_runtimes():
    yield
    while _runtimes:
        _runtimes.pop().close()
