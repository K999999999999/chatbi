"""容器验收的专用账号与证据；只在一次性工具中执行。"""

import argparse
import json
import os
import pty
import select as io_select
import secrets
import subprocess
import sys
import time
from pathlib import Path
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from src.authorization import hash_password
from src.authorization.auth_service import AuthService
from src.chatbi_control.database import ControlDatabaseConfig, create_control_engine
from src.chatbi_control.models import Role, User, UserSession
from tests.browser_real_reference import reference

REPORT = Path("/reports")


def prepare():
    engine = create_control_engine(
        ControlDatabaseConfig.from_environment(require_migrator=False)
    )
    username = f"web-e2e-container-{uuid4().hex}"
    password = secrets.token_hex(24)
    try:
        with Session(engine) as session, session.begin():
            role = session.scalar(select(Role).where(Role.name == "analyst"))
            if role is None:
                raise RuntimeError("缺少 analyst 角色，先显式 migrate")
            user = User(
                username=username,
                password_hash=hash_password(password),
                is_active=True,
                must_change_password=False,
                roles=[role],
            )
            session.add(user)
            session.flush()
            user_id = user.id
        REPORT.mkdir(exist_ok=True)
        account = REPORT / "account.json"
        account.write_text(json.dumps({"username": username, "id": user_id}))
        reference_data = reference()
        credentials = REPORT / "credentials.env"
        credentials.touch(mode=0o600)
        credentials.write_text(
            f"CHATBI_REAL_E2E_USERNAME={username}\nCHATBI_REAL_E2E_PASSWORD={password}\n"
            f"CHATBI_CONTAINER_REFERENCE={json.dumps(reference_data, ensure_ascii=False)}\n"
        )
    finally:
        engine.dispose()
    print("容器验收账号与只读参考已准备。")


def cleanup():
    account = json.loads((REPORT / "account.json").read_text())
    if not account["username"].startswith("web-e2e-container-"):
        raise RuntimeError("禁止修改非本次验收账号")
    engine = create_control_engine(
        ControlDatabaseConfig.from_environment(require_migrator=False)
    )
    try:
        with Session(engine) as session:
            user = session.get(User, account["id"])
            if user is None or user.username != account["username"]:
                raise RuntimeError("账号身份不一致")
        AuthService(sessionmaker(engine)).disable_user(account["id"])
        with Session(engine) as session:
            disabled = not session.get(User, account["id"]).is_active
            active = session.scalar(
                select(func.count())
                .select_from(UserSession)
                .where(
                    UserSession.user_id == account["id"],
                    UserSession.revoked_at.is_(None),
                )
            )
        result = {"disabled": disabled, "active_sessions": active}
        (REPORT / "cleanup.json").write_text(json.dumps(result))
        if not disabled or active != 0:
            raise RuntimeError("验收账号未完整清理")
        browser = REPORT / "browser.json"
        if browser.exists():
            evidence = json.loads(browser.read_text())
            evidence["cleanup"] = result
            metadata = REPORT / "runtime.json"
            if metadata.exists():
                evidence["runtime"] = json.loads(metadata.read_text())
            hot_reload = REPORT / "hot-reload.json"
            if hot_reload.exists():
                evidence["hot_reload"] = json.loads(hot_reload.read_text())
            images = REPORT / "images.jsonl"
            if images.exists():
                evidence["image_ids"] = [
                    json.loads(line) for line in images.read_text().splitlines()
                ]
            evidence["suite_status"] = evidence.get("status", "failed")
            browser.write_text(json.dumps(evidence, ensure_ascii=False, indent=2))
    finally:
        engine.dispose()
        (REPORT / "credentials.env").unlink(missing_ok=True)
    print("容器验收账号已禁用，活跃 Session 为0。")


def initialize_admin():
    if os.environ.get("CHATBI_CONTAINER_ISOLATED") != "1":
        raise RuntimeError("首次管理员验收仅允许隔离环境")
    master, slave = pty.openpty()
    password = secrets.token_hex(24)
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "src.bootstrap",
            "create-admin",
            "--username",
            "container-check-admin",
        ],
        stdin=slave,
        stdout=slave,
        stderr=slave,
    )
    os.close(slave)
    captured = b""
    prompts = ["首个管理员密码", "再次输入首个管理员密码"]
    deadline = time.monotonic() + 30
    try:
        while process.poll() is None and time.monotonic() < deadline:
            if io_select.select([master], [], [], 0.2)[0]:
                try:
                    captured += os.read(master, 4096)
                except OSError:
                    break
                if prompts and prompts[0].encode() in captured:
                    os.write(master, (password + "\n").encode())
                    prompts.pop(0)
                    captured = b""
        if process.wait(timeout=5) != 0 or prompts:
            raise RuntimeError("交互管理员创建未成功；诊断不回显密码或终端记录")
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
        os.close(master)
    print("隔离环境交互管理员创建通过。")


def verify_persistence():
    evidence = json.loads((REPORT / "browser.json").read_text())
    current = reference()
    for key in ("net_sales", "runtime_identity"):
        if current[key] != evidence["reference"][key]:
            raise RuntimeError("停止重启后的业务结果或RAG资产身份改变")
    print("停止重启后的业务数据与RAG资产身份保持。")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "action", choices=["prepare", "cleanup", "admin", "persistence"]
    )
    args = parser.parse_args()
    if args.action == "prepare":
        prepare()
    elif args.action == "cleanup":
        cleanup()
    elif args.action == "admin":
        initialize_admin()
    else:
        verify_persistence()
