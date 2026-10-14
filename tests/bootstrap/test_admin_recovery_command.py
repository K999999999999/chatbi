"""恢复CLI输入失败先于数据库和账号写入。"""

import getpass
import io
import warnings
from unittest.mock import patch

import pytest

from src.bootstrap.admin_recovery import recover_admin


class Terminal(io.StringIO):
    def isatty(self):
        return True


def test_nonterminal_input_is_rejected_without_database(monkeypatch):
    with patch("sys.stdin", io.StringIO()), patch("sys.stdout", io.StringIO()):
        assert recover_admin("admin", environment="dev", project="test-project") == 2


def test_mismatched_passwords_are_hidden_and_do_not_create_database_resources(
    monkeypatch,
):
    monkeypatch.setattr(
        "src.bootstrap.admin_recovery.create_control_engine",
        lambda *args: pytest.fail("不能连接数据库"),
    )
    passwords = iter(["test-hidden-password", "different-test-password"])
    monkeypatch.setattr(getpass, "getpass", lambda prompt: next(passwords))
    output = Terminal()
    with patch("sys.stdin", Terminal()), patch("sys.stdout", output):
        assert recover_admin("admin", environment="dev", project="test-project") == 2
    assert "test-hidden-password" not in output.getvalue()


def test_getpass_cannot_fall_back_to_echo(monkeypatch):
    def unsafe_input(prompt):
        warnings.warn("echo fallback", getpass.GetPassWarning)
        pytest.fail("应在回显前拒绝")

    monkeypatch.setattr(getpass, "getpass", unsafe_input)
    with patch("sys.stdin", Terminal()), patch("sys.stdout", Terminal()):
        assert recover_admin("admin", environment="app", project="test-project") == 2


def test_interrupted_input_is_nonzero(monkeypatch):
    def interrupted(prompt):
        raise KeyboardInterrupt

    monkeypatch.setattr(getpass, "getpass", interrupted)
    with patch("sys.stdin", Terminal()), patch("sys.stdout", Terminal()):
        assert recover_admin("admin", environment="dev", project="test-project") == 130
