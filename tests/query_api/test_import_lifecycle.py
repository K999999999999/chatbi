"""真实入口导入不得触发配置加载或运行资源创建。"""

import os
import subprocess
import sys


def test_api_import_without_configuration_has_no_runtime_side_effects():
    script = """
from unittest.mock import patch
with (
    patch('src.query_api.config.load_local_environment', side_effect=AssertionError('import loaded configuration')),
    patch('src.chatbi_control.database.create_control_engine', side_effect=AssertionError('import created engine')),
    patch('src.observability.tracing.create_trace_recorder', side_effect=AssertionError('import created tracing')),
):
    from src.query_api.main import app
    assert app.state.auth_service is None
    assert app.state.query_service is None
print('IMPORT_WITHOUT_RUNTIME_OK')
"""
    environment = os.environ.copy()
    for key in tuple(environment):
        if key.startswith(("CHATBI_", "LLM_", "POSTGRES_", "RAG_", "OTEL_")):
            environment.pop(key)
    result = subprocess.run(
        [sys.executable, "-c", script],
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert "IMPORT_WITHOUT_RUNTIME_OK" in result.stdout
