from contextlib import nullcontext
from unittest.mock import MagicMock, patch

import pytest

from src.chatbi_control import cli


def test_migrate_command_initializes_only_schema_and_rbac(capsys) -> None:
    config = object()
    with (
        patch.object(cli, "load_dotenv"),
        patch.object(
            cli.ControlDatabaseConfig, "from_environment", return_value=config
        ),
        patch.object(cli, "initialize_control_database") as initialize,
        patch.object(cli, "create_control_engine") as create_engine,
        patch.object(cli, "create_first_admin") as create_admin,
    ):
        assert cli.main(["migrate"]) == 0

    initialize.assert_called_once_with(config)
    create_engine.assert_not_called()
    create_admin.assert_not_called()
    assert "没有创建管理员" in capsys.readouterr().out


def test_create_admin_uses_runtime_database_without_running_migrations(capsys) -> None:
    config = object()
    engine = MagicMock()
    session = MagicMock()
    session_context = MagicMock()
    session_context.__enter__.return_value = session
    session.begin.return_value = nullcontext()

    with (
        patch.object(cli, "load_dotenv"),
        patch.object(
            cli.ControlDatabaseConfig,
            "from_environment",
            return_value=config,
        ) as from_environment,
        patch.object(cli, "create_control_engine", return_value=engine),
        patch.object(cli, "verify_control_schema") as verify_schema,
        patch.object(cli, "Session", return_value=session_context),
        patch.object(cli, "create_first_admin") as create_admin,
        patch.object(
            cli.getpass,
            "getpass",
            side_effect=["initial-password-123", "initial-password-123"],
        ),
        patch.object(cli, "initialize_control_database") as initialize,
    ):
        assert cli.main(["create-admin", "--username", "admin-1"]) == 0

    from_environment.assert_called_once_with(require_migrator=False)
    verify_schema.assert_called_once_with(engine)
    create_admin.assert_called_once_with(
        session,
        username="admin-1",
        password="initial-password-123",
    )
    initialize.assert_not_called()
    engine.dispose.assert_called_once_with()
    output = capsys.readouterr().out
    assert "initial-password-123" not in output


def test_mismatched_admin_passwords_stop_before_database_access(capsys) -> None:
    with (
        patch.object(cli, "load_dotenv"),
        patch.object(
            cli.getpass,
            "getpass",
            side_effect=["initial-password-123", "different-password-123"],
        ),
        patch.object(cli.ControlDatabaseConfig, "from_environment") as from_environment,
    ):
        assert cli.main(["create-admin", "--username", "admin-1"]) == 2

    from_environment.assert_not_called()
    assert "两次密码不一致" in capsys.readouterr().err


def test_cli_requires_an_explicit_subcommand() -> None:
    with pytest.raises(SystemExit) as error:
        cli.main([])

    assert error.value.code == 2
