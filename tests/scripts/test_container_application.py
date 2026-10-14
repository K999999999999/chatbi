"""标准容器配置的凭据、资源、初始化和运行边界。"""

import json
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_standard_compose_does_not_need_a_release_or_stable_resource(tmp_path):
    template = (ROOT / ".env.example").read_text()
    template = template.replace(
        "CHATBI_ADMIN_SECRET_KEY=\n", "CHATBI_ADMIN_SECRET_KEY=test-key\n"
    )
    template = template.replace("LLM_API_KEY=\n", "LLM_API_KEY=test-key\n")
    config = tmp_path / "test.env"
    config.write_text(template)
    result = subprocess.run(
        [
            "docker",
            "compose",
            "--env-file",
            str(config),
            "-f",
            str(ROOT / "docker-compose.app.yml"),
            "--profile",
            "tools",
            "config",
            "--format",
            "json",
        ],
        cwd=ROOT,
        env={"PATH": os.environ["PATH"]},
        capture_output=True,
        text=True,
        check=True,
    )
    compose = json.loads(result.stdout)
    services = compose["services"]
    assert set(services) == {"api", "postgres", "qdrant", "tools", "migrator"}
    assert all(
        services[name]["restart"] == "unless-stopped"
        for name in ("api", "postgres", "qdrant")
    )
    assert all(services[name]["restart"] == "no" for name in ("tools", "migrator"))
    api = services["api"]
    assert api["build"]["target"] == "api"
    assert api["depends_on"]["postgres"]["condition"] == "service_healthy"
    assert "depends_on" not in services["migrator"]
    assert not any("MIGRATOR" in key for key in api["environment"])
    assert "POSTGRES_MIGRATOR_PASSWORD" in services["migrator"]["environment"]
    assert all(volume["read_only"] for volume in api["volumes"])
    assert not any(
        volume.get("external", False) for volume in compose["volumes"].values()
    )
    assert all("stable" not in volume["name"] for volume in compose["volumes"].values())
    assert all(port["host_ip"] == "127.0.0.1" for port in api["ports"])
    assert "ports" not in services["postgres"] and "ports" not in services["qdrant"]
