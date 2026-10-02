"""统一入口的分发、参数和依赖隔离 Contract。"""

import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

from src.bootstrap import commands, control, model, rag


def test_help_lists_all_commands_without_importing_runtime_or_model():
    script = """
import sys
from src.bootstrap.commands import main
try:
    main(['--help'])
except SystemExit as error:
    assert error.code == 0
assert 'src.bootstrap.runtime' not in sys.modules
assert 'src.bootstrap.model' not in sys.modules
assert 'src.bootstrap.rag' not in sys.modules
assert 'langchain_openai' not in sys.modules
assert 'FlagEmbedding' not in sys.modules
"""
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, timeout=30
    )
    assert result.returncode == 0, result.stderr
    assert "migrate,create-admin,prepare-model,build-rag" in result.stdout


def test_database_commands_do_not_import_runtime_or_embedding():
    script = """
import sys
from unittest.mock import patch
from src.bootstrap.commands import main
with patch('src.bootstrap.commands.load_dotenv'), patch('src.bootstrap.control.migrate', return_value=0):
    assert main(['migrate']) == 0
assert 'src.bootstrap.runtime' not in sys.modules
assert 'src.bootstrap.model' not in sys.modules
assert 'FlagEmbedding' not in sys.modules
"""
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, timeout=30
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    "operation,handler", [("migrate", "migrate"), ("create-admin", "create_admin")]
)
def test_database_command_dispatch_preserves_exit_code(monkeypatch, operation, handler):
    monkeypatch.setattr(commands, "load_dotenv", Mock())
    execute = Mock(return_value=1)
    monkeypatch.setattr(control, handler, execute)
    assert commands.main([operation]) == 1


def test_model_and_rag_dispatch_preserve_arguments_and_exit_code(monkeypatch):
    monkeypatch.setattr(commands, "load_dotenv", Mock())
    prepare = Mock(return_value=1)
    build = Mock(return_value=0)
    monkeypatch.setattr(model, "prepare_model", prepare)
    monkeypatch.setattr(rag, "build_rag", build)
    assert commands.main(["prepare-model"]) == 1
    assert (
        commands.main(
            [
                "build-rag",
                "--structure-dir",
                "structure",
                "--metrics-path",
                "metrics.json",
                "--output-dir",
                "assets",
                "--build-id",
                "candidate",
            ]
        )
        == 0
    )
    args = build.call_args.args[0]
    assert args.structure_dir == Path("structure")
    assert args.metrics_path == Path("metrics.json")
    assert args.output_dir == Path("assets")
    assert args.build_id == "candidate"


@pytest.mark.parametrize(
    "argv",
    [
        [],
        ["unknown"],
        ["build-rag", "--unknown"],
        ["prepare-model", "--username", "admin"],
    ],
)
def test_invalid_commands_fail_before_configuration_loading(monkeypatch, argv):
    load = Mock()
    monkeypatch.setattr(commands, "load_dotenv", load)
    with pytest.raises(SystemExit) as error:
        commands.main(argv)
    assert error.value.code == 2
    load.assert_not_called()


@pytest.mark.parametrize(
    "old_module",
    ["src.chatbi_control", "scripts.prepare_embedding_model", "src.rag_offline"],
)
def test_old_command_entrypoints_are_removed(old_module):
    result = subprocess.run(
        [sys.executable, "-m", old_module, "--help"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode != 0
    assert "No module named" in result.stderr
