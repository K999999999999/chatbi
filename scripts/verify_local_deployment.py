"""Run R6 acceptance on disposable resources and Windows Microsoft Edge."""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import shutil
import socket
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from scripts.local_acceptance import (
    LocalAcceptanceError,
    acceptance_volume_names,
    clean_compose_environment,
    parse_env_text,
    prepare,
    project_name,
)

ROOT = Path(__file__).resolve().parents[1]


def _ps_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


class Acceptance:
    def __init__(self, root: Path, commit: str) -> None:
        self.root = root
        self.commit = commit
        self.run_id = (
            datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + secrets.token_hex(4)
        )
        self.project = project_name(self.run_id)
        self.work = root / ".local" / "acceptance" / self.run_id
        self.report = self.work / "report"
        self.env = clean_compose_environment(dict(os.environ))
        self.windows_workspace: Path | None = None
        self.compose: list[str] = []
        self.sequence = 0
        self.failures: dict[str, int] = {}

    def run(
        self,
        args: list[str],
        *,
        check: bool = True,
        timeout: int = 600,
        sensitive: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            args,
            cwd=self.root,
            env=self.env,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
        self.sequence += 1
        log = self.work / f"step-{self.sequence:03d}.log"
        log.write_text(
            "敏感状态仅在内存中核验，未写入诊断。\n"
            if sensitive
            else result.stdout + result.stderr,
            encoding="utf-8",
        )
        log.chmod(0o600)
        if check and result.returncode:
            raise LocalAcceptanceError(
                f"验收第 {self.sequence} 步失败，退出码 {result.returncode}；私有诊断：{log}"
            )
        return result

    def dc(self, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        return self.run([*self.compose, *args], check=check)

    def support(self, action: str) -> subprocess.CompletedProcess[str]:
        return self.dc(
            "run",
            "--rm",
            "--no-deps",
            "-T",
            "--entrypoint",
            "python",
            "admin",
            "-m",
            "tests.container_dev_support",
            action,
        )

    def phase(self, message: str) -> None:
        print(message, flush=True)

    def save(self, name: str, value: object) -> None:
        (self.report / name).write_text(
            json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def external_state(self) -> list[dict]:
        ids = self.run(
            ["docker", "ps", "--all", "--quiet", "--no-trunc"]
        ).stdout.split()
        if not ids:
            return []
        objects = json.loads(
            self.run(["docker", "inspect", *ids], sensitive=True).stdout
        )
        return sorted(
            [
                {
                    "id": item["Id"],
                    "image_id": item["Image"],
                    "running": item["State"]["Running"],
                    "project": item["Config"]
                    .get("Labels", {})
                    .get("com.docker.compose.project"),
                }
                for item in objects
                if item["Config"].get("Labels", {}).get("com.docker.compose.project")
                != self.project
            ],
            key=lambda item: item["id"],
        )

    def assert_container(self, container_id: str) -> dict:
        item = json.loads(
            self.run(["docker", "inspect", container_id], sensitive=True).stdout
        )[0]
        labels = item["Config"].get("Labels", {})
        if (
            labels.get("com.docker.compose.project") != self.project
            or labels.get("com.chatbi.acceptance.run_id") != self.run_id
            or labels.get("com.chatbi.environment") != "acceptance"
        ):
            raise LocalAcceptanceError("容器归属不一致；拒绝操作")
        return item

    def cleanup_resources(self) -> None:
        ids = self.run(
            [
                "docker",
                "ps",
                "--all",
                "--quiet",
                "--filter",
                f"label=com.docker.compose.project={self.project}",
            ]
        ).stdout.split()
        for container_id in ids:
            self.assert_container(container_id)
        expected = set(acceptance_volume_names(self.run_id))
        names = self.run(
            [
                "docker",
                "volume",
                "ls",
                "--quiet",
                "--filter",
                f"label=com.docker.compose.project={self.project}",
            ]
        ).stdout.split()
        for name in names:
            volume = json.loads(self.run(["docker", "volume", "inspect", name]).stdout)[
                0
            ]
            labels = volume.get("Labels", {})
            if (
                name not in expected
                or labels.get("com.docker.compose.project") != self.project
                or labels.get("com.chatbi.acceptance.run_id") != self.run_id
            ):
                raise LocalAcceptanceError("卷归属不一致；保留资源")
        networks = self.run(
            [
                "docker",
                "network",
                "ls",
                "--quiet",
                "--filter",
                f"label=com.docker.compose.project={self.project}",
            ]
        ).stdout.split()
        for network_id in networks:
            network = json.loads(
                self.run(["docker", "network", "inspect", network_id]).stdout
            )[0]
            if network["Name"] != f"{self.project}_default":
                raise LocalAcceptanceError("网络归属不一致；保留资源")
        self.dc("down", "--volumes")
        remaining = self.run(
            [
                "docker",
                "volume",
                "ls",
                "--quiet",
                "--filter",
                f"label=com.docker.compose.project={self.project}",
            ]
        ).stdout.strip()
        if remaining:
            raise LocalAcceptanceError("验收卷清理未完成")
        if self.run(
            [
                "docker",
                "ps",
                "--all",
                "--quiet",
                "--filter",
                f"label=com.docker.compose.project={self.project}",
            ]
        ).stdout.strip():
            raise LocalAcceptanceError("验收容器清理未完成")
        if self.run(
            [
                "docker",
                "network",
                "ls",
                "--quiet",
                "--filter",
                f"label=com.docker.compose.project={self.project}",
            ]
        ).stdout.strip():
            raise LocalAcceptanceError("验收网络清理未完成")

    def expected_failure(
        self, name: str, args: list[str], message: str | None = None
    ) -> None:
        result = self.run(args, check=False)
        if not result.returncode or (
            message and message not in result.stdout + result.stderr
        ):
            raise LocalAcceptanceError(f"失败场景 {name} 未按预期拒绝；保留诊断")
        self.failures[name] = result.returncode

    def edge_workspace(self) -> str:
        command = (
            'Set-Location "$env:SystemRoot\\System32"; '
            f'Write-Output (Join-Path $env:TEMP "chatbi-r6-edge-{self.run_id}")'
        )
        windows_root = self.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command]
        ).stdout.strip()
        unix_root = Path(self.run(["wslpath", "-u", windows_root]).stdout.strip())
        if unix_root.exists():
            raise LocalAcceptanceError("Windows 验收目录已存在，拒绝覆盖")
        unix_root.mkdir()
        (unix_root / "run-id").write_text(self.run_id)
        self.windows_workspace = unix_root
        shutil.copytree(
            self.root / "frontend",
            unix_root / "frontend",
            ignore=shutil.ignore_patterns(
                "node_modules",
                "dist",
                "dist-export",
                "test-results",
                "playwright-report",
            ),
        )
        windows_frontend = windows_root + "\\frontend"
        command = (
            f'$ErrorActionPreference="Stop"; [Console]::OutputEncoding=[System.Text.Encoding]::UTF8; Set-Location -LiteralPath {_ps_quote(windows_frontend)}; '
            "& npm.cmd ci --ignore-scripts; exit $LASTEXITCODE"
        )
        self.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command]
        )
        return windows_frontend

    def edge(self, frontend: str, phase: int) -> None:
        windows_report = self.run(["wslpath", "-w", str(self.report)]).stdout.strip()
        settings = {
            "CHATBI_CONTAINER_REAL_E2E": "1",
            "CHATBI_CONTAINER_RESTART_PHASE": str(phase),
            "CHATBI_CONTAINER_BASE_URL": f"http://127.0.0.1:{self.port}",
            "CHATBI_CONTAINER_COMMIT": self.commit,
            "CHATBI_CONTAINER_GIT_DIRTY": "false",
            "CHATBI_CONTAINER_TARGET": "local-fixed-image-windows-edge",
            "CHATBI_CONTAINER_REPORT_DIR": windows_report,
            "CHATBI_CONTAINER_CREDENTIALS_FILE": windows_report + "\\credentials.env",
        }
        command = f'$ErrorActionPreference="Stop"; [Console]::OutputEncoding=[System.Text.Encoding]::UTF8; Set-Location -LiteralPath {_ps_quote(frontend)}; '
        command += "; ".join(
            f"$env:{key}={_ps_quote(value)}" for key, value in settings.items()
        )
        command += "; & .\\node_modules\\.bin\\playwright.cmd test --config playwright.local-deployment.config.ts; exit $LASTEXITCODE"
        self.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
            timeout=1800,
        )

    def failure_checks(self) -> None:
        self.phase("检查配置、索引、兼容性、端口和容器启动失败。")
        override = self.work / "invalid-config.yml"
        override.write_text(
            "services:\n  verify:\n    environment:\n      CHATBI_ENV: production\n"
        )
        self.expected_failure(
            "configuration",
            [
                *self.compose,
                "-f",
                str(override),
                "run",
                "--rm",
                "--no-deps",
                "-T",
                "verify",
            ],
            "CHATBI_ENV",
        )
        pointer = self.work / "rag" / "current.json"
        held = pointer.with_suffix(".held")
        pointer.rename(held)
        try:
            self.expected_failure(
                "missing-index",
                [*self.compose, "run", "--rm", "--no-deps", "-T", "verify"],
                "RAG 索引未准备",
            )
        finally:
            held.rename(pointer)
        before = json.loads(self.support("acceptance-snapshot").stdout)
        sql_args = (
            "exec",
            "-T",
            "postgres",
            "psql",
            "-U",
            "chatbi_migrator",
            "-d",
            "chatbi_control",
            "-v",
            "ON_ERROR_STOP=1",
            "-c",
        )
        self.dc(
            *sql_args,
            "INSERT INTO schema_migrations(version) VALUES ('chatbi-control-v999')",
        )
        try:
            self.expected_failure(
                "incompatible-migration",
                [*self.compose, "run", "--rm", "--no-deps", "-T", "verify"],
                "control migration marker",
            )
        finally:
            self.dc(
                *sql_args,
                "DELETE FROM schema_migrations WHERE version='chatbi-control-v999'",
            )
        after = json.loads(self.support("acceptance-snapshot").stdout)
        if before != after:
            raise LocalAcceptanceError("拒绝不兼容状态后持久状态改变")
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen()
            occupied = listener.getsockname()[1]
            self.expected_failure(
                "occupied-loopback-port",
                [
                    "bash",
                    "-c",
                    'source "$1"; local_loopback_port_is_free "$2"',
                    "acceptance-port",
                    str(self.root / "scripts" / "local_port.sh"),
                    str(occupied),
                ],
            )
        self.expected_failure(
            "container-start",
            [
                *self.compose,
                "run",
                "--rm",
                "--no-deps",
                "-T",
                "--entrypoint",
                "/bin/false",
                "api",
            ],
        )
        self.dc("run", "--rm", "--no-deps", "-T", "verify")
        self.save(
            "failure-checks.json",
            {
                "expected_nonzero": self.failures,
                "persistent_state_unchanged": before == after,
            },
        )

    def execute(self) -> None:
        with socket.socket() as reservation:
            reservation.bind(("127.0.0.1", 0))
            self.port = reservation.getsockname()[1]
        prepare(self.root, self.work, self.run_id, self.port)
        release_path = self.root / ".local" / "releases" / f"{self.commit}.env"
        release = parse_env_text(release_path.read_text())
        if release.get("CHATBI_SOURCE_COMMIT") != self.commit:
            raise LocalAcceptanceError("发布身份与当前 clean candidate 不一致")
        for role in ("API", "DATABASE"):
            image = release[f"CHATBI_{role}_IMAGE"]
            actual = self.run(
                ["docker", "image", "inspect", "--format", "{{.Id}}", image]
            ).stdout.strip()
            revision = self.run(
                [
                    "docker",
                    "image",
                    "inspect",
                    "--format",
                    '{{index .Config.Labels "org.opencontainers.image.revision"}}',
                    image,
                ]
            ).stdout.strip()
            if actual != release[f"CHATBI_{role}_IMAGE_ID"] or revision != self.commit:
                raise LocalAcceptanceError("镜像 ID / revision 与发布记录不一致")
        self.compose = [
            "docker",
            "compose",
            "--project-name",
            self.project,
            "--project-directory",
            str(self.root),
            "--profile",
            "tools",
            "-f",
            str(self.root / "docker-compose.local.yml"),
            "-f",
            str(self.work / "compose.acceptance.yml"),
            "--env-file",
            str(self.work / "acceptance.env"),
            "--env-file",
            str(self.work / "acceptance.secrets.env"),
            "--env-file",
            str(release_path),
        ]
        self.dc("config", "--quiet")
        external_before = self.external_state()
        self.save("external-before.json", external_before)
        passed = False
        cleanup_done = False
        try:
            self.run(
                [
                    sys.executable,
                    "-c",
                    "import openpyxl, pypdf; print('独立文件解析依赖已就绪。')",
                ]
            )
            self.phase(f"空环境安装：{self.project}；API 回环端口 {self.port}。")
            self.dc("up", "-d", "postgres", "qdrant")
            self.dc(
                "exec",
                "-T",
                "postgres",
                "sh",
                "/workspace/database/init/wait_for_base_initialization.sh",
            )
            self.dc("run", "--rm", "--no-deps", "-T", "qdrant-check")
            self.dc("run", "--rm", "--no-deps", "-T", "migrator")
            self.dc(
                "run",
                "--rm",
                "--no-deps",
                "-T",
                "-e",
                "CHATBI_CONTAINER_ISOLATED=1",
                "--entrypoint",
                "python",
                "admin",
                "-m",
                "tests.container_dev_support",
                "admin",
            )
            self.phase("构建隔离 RAG 索引，固定模型缓存只读复用。")
            self.dc("run", "--rm", "--no-deps", "-T", "model", "build-rag")
            self.dc("run", "--rm", "--no-deps", "-T", "verify")
            self.failure_checks()
            self.dc("up", "-d", "--wait", "--wait-timeout", "180", "api")
            self.phase("验证 Chromium sandbox 后开始真实业务，渲染失败会立即停止。")
            self.dc(
                "exec",
                "-T",
                "api",
                "python",
                "-c",
                "import os; from playwright.sync_api import sync_playwright; "
                "p=sync_playwright().start(); b=p.chromium.launch(headless=True,chromium_sandbox=True, "
                "env={'PATH':os.environ['PATH'],'HOME':'/tmp'}); b.close(); p.stop(); print('sandbox启动通过。')",
            )
            self.support("prepare")
            frontend = self.edge_workspace()
            self.phase(
                "运行 Windows Edge：真实问数 / 追问 / 分析 / 历史 / 成果 / 三种导出。"
            )
            self.edge(frontend, 0)
            before = json.loads(self.support("acceptance-snapshot").stdout)
            self.save("before-restart.json", before)
            api_id = self.dc("ps", "-q", "api").stdout.strip()
            self.assert_container(api_id)
            self.phase("停止并手动恢复本次验收项目，核对持久数据和未完成执行恢复。")
            self.run(["docker", "kill", api_id])
            self.dc("stop", "api", "postgres", "qdrant")
            self.dc("up", "-d", "postgres", "qdrant")
            self.dc("run", "--rm", "--no-deps", "-T", "qdrant-check")
            self.dc("run", "--rm", "--no-deps", "-T", "verify")
            self.dc("up", "-d", "--wait", "--wait-timeout", "180", "api")
            after = json.loads(self.support("acceptance-snapshot").stdout)
            self.save("after-restart.json", after)
            if before != after:
                raise LocalAcceptanceError("重启后账号 / 历史 / 成果 / Seed 状态改变")
            self.support("execution-recovery")
            self.support("expire-analysis")
            self.edge(frontend, 1)
            self.support("persistence")
            # Independent parsers belong to the host dev environment, not the runtime image.
            self.run(
                [
                    sys.executable,
                    "-c",
                    (
                        "import sys; from pathlib import Path; from tests import container_dev_support as support; "
                        "support.REPORT = Path(sys.argv[1]); support.verify_exports()"
                    ),
                    str(self.report),
                ]
            )
            self.dc(
                "exec",
                "-T",
                "api",
                "python",
                "-c",
                "import os,pathlib,tempfile; p=pathlib.Path(tempfile.gettempdir())/'chatbi-result-exports'; "
                "assert sorted(x.name for x in p.iterdir())==['.runtime.lock']; "
                "assert (p/'.runtime.lock').stat().st_mode & 0o777 == 0o600; "
                "assert not any(b'export_worker.py' in x.read_bytes() for x in pathlib.Path('/proc').glob('[0-9]*/cmdline') "
                "if x.parent.name != str(os.getpid()) and x.exists()); print('导出临时资源已回收。')",
            )
            item = self.assert_container(self.dc("ps", "-q", "api").stdout.strip())
            api_env = dict(value.split("=", 1) for value in item["Config"]["Env"])
            if (
                any("MIGRATOR" in key for key in api_env)
                or len(item["Mounts"]) != 2
                or not all(not m["RW"] for m in item["Mounts"])
            ):
                raise LocalAcceptanceError("API 凭据或挂载隔离检查失败")
            credentials = parse_env_text((self.report / "credentials.env").read_text())
            self.support("cleanup")
            cleanup_done = True
            config = parse_env_text((self.work / "acceptance.env").read_text())
            private = parse_env_text((self.work / "acceptance.secrets.env").read_text())
            secret_values = [
                config["LLM_API_KEY"],
                *private.values(),
                credentials["CHATBI_REAL_E2E_PASSWORD"],
            ]
            api_log_result = self.run(["docker", "logs", item["Id"]], sensitive=True)
            api_logs = api_log_result.stdout + api_log_result.stderr
            for file in [*self.work.glob("step-*.log"), *self.report.glob("*.json")]:
                content = file.read_text(errors="replace")
                if any(value in content for value in secret_values):
                    raise LocalAcceptanceError("私有诊断出现凭据；报告不归档")
            if any(value in api_logs for value in secret_values):
                raise LocalAcceptanceError("API 日志出现凭据")
            external_after = self.external_state()
            self.save("external-after.json", external_after)
            if external_before != external_after:
                raise LocalAcceptanceError("其他项目容器身份或运行状态改变")
            model_dir = Path(config["CHATBI_LOCAL_MODEL_DIR"])
            self.save(
                "runtime.json",
                {
                    "source_commit": self.commit,
                    "git_dirty": False,
                    "release": release,
                    "project": self.project,
                    "volumes": acceptance_volume_names(self.run_id),
                    "browser_channel": "msedge",
                    "model_config_sha256": hashlib.sha256(
                        (model_dir / "config.json").read_bytes()
                    ).hexdigest(),
                    "model_revision": "5617a9f61b028005a4858fdac845db406aefb181",
                    "rag_pointer": json.loads(
                        (self.work / "rag" / "current.json").read_text()
                    ),
                    "rag_manifests": {
                        str(path.relative_to(self.work / "rag")): {
                            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                            "provenance": json.loads(path.read_text()).get(
                                "provenance"
                            ),
                            "embedding": json.loads(path.read_text()).get("embedding"),
                        }
                        for path in (self.work / "rag").rglob("manifest.json")
                    },
                    "rag_current_sha256": hashlib.sha256(
                        (self.work / "rag" / "current.json").read_bytes()
                    ).hexdigest(),
                    "persistent_state_preserved": before == after,
                    "external_resources_unchanged": True,
                    "api_readonly_asset_mounts": True,
                    "api_has_no_migrator_identity": True,
                    "chromium_sandbox_launch": True,
                    "export_temporary_resources_clean": True,
                    "logs_no_known_secrets": True,
                    "host_docker_reboot": "维护窗口手动验证，未执行",
                },
            )
            passed = True
        finally:
            if (self.report / "account.json").exists() and not cleanup_done:
                self.support("cleanup")
            self.cleanup_resources()
            self.save(
                "resource-cleanup.json",
                {"project": self.project, "volumes_removed": True},
            )
            (self.work / "acceptance.env").unlink(missing_ok=True)
            (self.work / "acceptance.secrets.env").unlink(missing_ok=True)
            if (
                self.windows_workspace
                and (self.windows_workspace / "run-id").read_text() == self.run_id
            ):
                shutil.rmtree(self.windows_workspace)
        if passed:
            if (self.report / "credentials.env").exists():
                raise LocalAcceptanceError("临时账号凭证未移除")
            target = (
                self.root
                / "reports"
                / "browser-real-artifacts"
                / "r6-local-deployment"
                / f"{self.commit[:12]}-{self.run_id}"
            )
            shutil.copytree(self.report, target)
            self.phase(f"完整隔离验收通过，专用账号和资源已清理。证据：{target}")


def main() -> int:
    dirty = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    if dirty:
        print(
            "完整本地部署验收要求 clean candidate；先完成相关改动、Review 和本地提交。",
            file=sys.stderr,
        )
        return 2
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    if not (ROOT / ".local" / "releases" / f"{commit}.env").is_file():
        print(
            "当前 clean candidate 尚未构建固定镜像；先运行 ./local build。",
            file=sys.stderr,
        )
        return 2
    acceptance = Acceptance(ROOT, commit)
    try:
        acceptance.execute()
    except (
        LocalAcceptanceError,
        OSError,
        subprocess.SubprocessError,
        ValueError,
    ) as error:
        print(
            f"本地部署验收未通过：{error}；私有工作目录：{acceptance.work}",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
