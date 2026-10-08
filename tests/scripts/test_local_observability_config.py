from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def test_stable_compose_passes_only_the_explicit_trace_configuration():
    compose = yaml.safe_load((ROOT / "docker-compose.local.yml").read_text())
    api_environment = compose["services"]["api"]["environment"]

    assert api_environment["CHATBI_RUNTIME_ENV"] == "stable"
    assert api_environment["CHATBI_TRACE_CONTENT_ENABLED"] == "false"
    assert api_environment["CHATBI_OBSERVABILITY_ENABLED"] == (
        "${CHATBI_OBSERVABILITY_ENABLED:-false}"
    )
    assert api_environment["OTEL_RESOURCE_ATTRIBUTES"] == (
        "deployment.environment.name=stable"
    )
    assert {
        "CHATBI_SERVICE_VERSION",
        "CHATBI_OTLP_TIMEOUT_SECONDS",
        "OTEL_SERVICE_NAME",
        "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT",
        "OTEL_EXPORTER_OTLP_HEADERS",
    } <= api_environment.keys()
    assert "OTEL_EXPORTER_OTLP_ENDPOINT" not in api_environment


def test_stable_entry_clears_host_trace_variables_before_compose_interpolation():
    local_entry = (ROOT / "local").read_text()
    reset_block = local_entry.split(
        "# Compose reads only the dedicated stable files", 1
    )[1].split("do\n", 1)[0]

    for key in (
        "CHATBI_OBSERVABILITY_ENABLED",
        "CHATBI_TRACE_CONTENT_ENABLED",
        "CHATBI_RUNTIME_ENV",
        "CHATBI_SERVICE_VERSION",
        "CHATBI_OTLP_TIMEOUT_SECONDS",
        "OTEL_SERVICE_NAME",
        "OTEL_RESOURCE_ATTRIBUTES",
        "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT",
        "OTEL_EXPORTER_OTLP_HEADERS",
    ):
        assert key in reset_block

    secret_setup = local_entry.split("printf 'QDRANT_API_KEY='", 1)[1].split(
        '} > "$secret_tmp"', 1
    )[0]
    assert "OTEL_EXPORTER_OTLP_HEADERS" in secret_setup
