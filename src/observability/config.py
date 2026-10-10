"""Observability 配置解析；内容采集规则在这里统一 fail-closed。"""

import math
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from urllib.parse import urlsplit

_DEFAULT_TIMEOUT_SECONDS = 5.0
_MAX_TIMEOUT_SECONDS = 10.0
_ALLOWED_CONTENT_ENVS = frozenset({"local", "dev", "test"})
_ALLOWED_HEADER_NAMES = frozenset(
    {
        "authorization",
        "authentication",
        "x-arms-license-key",
        "x-arms-project",
        "x-cms-workspace",
    }
)
_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
_FALSE_VALUES = frozenset({"0", "false", "no", "off"})
_HEADER_PART_RE = re.compile(r"^\s*([A-Za-z][A-Za-z0-9-]{0,63})\s*=\s*(.*?)\s*$")
_RESOURCE_VALUE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_RESOURCE_SECRET_RE = re.compile(
    r"(?:api[-_ ]?key|authorization|bearer|password|secret|access[-_ ]?token)",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class ObservabilityConfig:
    """OTel 组装所需的安全配置值。"""

    enabled: bool = False
    content_capture_enabled: bool = False
    runtime_env: str | None = field(default=None, repr=False)
    service_name: str = "chatbi-engine"
    service_version: str = "0.1.0"
    deployment_environment: str | None = None
    otlp_traces_endpoint: str | None = field(default=None, repr=False)
    otlp_timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS
    otlp_headers: Mapping[str, str] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        """所有构造路径都执行内容采集的 fail-closed 校验。"""

        runtime_env = _normalized_runtime_env(self.runtime_env)
        deployment_env = _normalized_runtime_env(self.deployment_environment)
        content_allowed = (
            self.content_capture_enabled is True
            and runtime_env in _ALLOWED_CONTENT_ENVS
            and (deployment_env is None or deployment_env == runtime_env)
            and (deployment_env is None or deployment_env in _ALLOWED_CONTENT_ENVS)
        )
        if self.content_capture_enabled != content_allowed:
            object.__setattr__(self, "content_capture_enabled", content_allowed)
        object.__setattr__(
            self,
            "service_name",
            _safe_resource_value(self.service_name, "chatbi-engine"),
        )
        object.__setattr__(
            self,
            "service_version",
            _safe_resource_value(self.service_version, "0.1.0", max_length=64),
        )
        object.__setattr__(
            self,
            "deployment_environment",
            _safe_resource_value(deployment_env, ""),
        )
        object.__setattr__(
            self,
            "otlp_traces_endpoint",
            _validated_endpoint(self.otlp_traces_endpoint, runtime_env),
        )
        object.__setattr__(
            self, "otlp_timeout_seconds", _bounded_timeout(self.otlp_timeout_seconds)
        )
        object.__setattr__(
            self, "otlp_headers", MappingProxyType(_safe_headers(self.otlp_headers))
        )

    @property
    def otlp_endpoint(self) -> str | None:
        """兼容更短的内部字段名，不改变配置来源。"""

        return self.otlp_traces_endpoint

    @classmethod
    def from_env(
        cls,
        environ: Mapping[str, str] | None = None,
    ) -> "ObservabilityConfig":
        """从环境变量解析配置，未知值不会被当作安全开启。"""

        values = os.environ if environ is None else environ
        runtime_env = _normalized_runtime_env(values.get("CHATBI_RUNTIME_ENV"))
        resource_attributes, resource_conflict = _parse_resource_attributes(
            values.get("OTEL_RESOURCE_ATTRIBUTES", "")
        )
        deployment_environment = (
            resource_attributes.get("deployment.environment.name") or runtime_env
        )
        resource_env = _normalized_runtime_env(deployment_environment)
        content_requested = _parse_bool(values.get("CHATBI_TRACE_CONTENT_ENABLED"))
        content_allowed = (
            runtime_env in _ALLOWED_CONTENT_ENVS
            and content_requested is True
            and not resource_conflict
            and _no_conflicting_environment(runtime_env, resource_env)
        )

        return cls(
            enabled=_parse_bool(values.get("CHATBI_OBSERVABILITY_ENABLED")) is True,
            content_capture_enabled=content_allowed,
            runtime_env=runtime_env,
            service_name=(values.get("OTEL_SERVICE_NAME") or "chatbi-engine").strip()
            or "chatbi-engine",
            service_version=(values.get("CHATBI_SERVICE_VERSION") or "0.1.0").strip()
            or "0.1.0",
            deployment_environment=deployment_environment,
            otlp_traces_endpoint=_optional_text(
                values.get("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT")
            ),
            otlp_timeout_seconds=_parse_positive_timeout(
                values.get("CHATBI_OTLP_TIMEOUT_SECONDS")
            ),
            otlp_headers=_parse_headers(values.get("OTEL_EXPORTER_OTLP_HEADERS")),
        )


def _parse_bool(value: str | None) -> bool | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    if normalized in _TRUE_VALUES:
        return True
    if normalized in _FALSE_VALUES:
        return False
    return None


def _normalized_runtime_env(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    return normalized or None


def _no_conflicting_environment(
    runtime_env: str | None,
    resource_env: str | None,
) -> bool:
    if runtime_env is None or resource_env is None:
        return True
    return runtime_env == resource_env


def _optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _safe_resource_value(value: object, default: str, *, max_length: int = 128) -> str:
    if not isinstance(value, str):
        return default
    candidate = value.strip()
    if (
        len(candidate) > max_length
        or not _RESOURCE_VALUE_RE.fullmatch(candidate)
        or _RESOURCE_SECRET_RE.search(candidate)
    ):
        return default
    return candidate


def _parse_positive_timeout(value: str | None) -> float:
    if value is None:
        return _DEFAULT_TIMEOUT_SECONDS
    try:
        timeout = float(value.strip())
    except (AttributeError, ValueError):
        return _DEFAULT_TIMEOUT_SECONDS
    if not math.isfinite(timeout) or timeout <= 0 or timeout > _MAX_TIMEOUT_SECONDS:
        return _DEFAULT_TIMEOUT_SECONDS
    return timeout


def _bounded_timeout(value: object) -> float:
    try:
        timeout = float(value)
    except (TypeError, ValueError):
        return _DEFAULT_TIMEOUT_SECONDS
    if not math.isfinite(timeout) or timeout <= 0 or timeout > _MAX_TIMEOUT_SECONDS:
        return _DEFAULT_TIMEOUT_SECONDS
    return timeout


def _validated_endpoint(value: str | None, runtime_env: str | None) -> str | None:
    endpoint = _optional_text(value)
    if (
        endpoint is None
        or len(endpoint) > 2048
        or any(ord(char) < 32 for char in endpoint)
    ):
        return None
    try:
        parsed = urlsplit(endpoint)
        hostname = parsed.hostname
        _ = parsed.port
    except ValueError:
        return None
    if (
        hostname is None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or "?" in endpoint
        or "#" in endpoint
    ):
        return None
    if parsed.scheme.lower() == "https":
        return endpoint
    if (
        parsed.scheme.lower() == "http"
        and runtime_env in _ALLOWED_CONTENT_ENVS
        and hostname.lower() in {"localhost", "127.0.0.1", "::1"}
    ):
        return endpoint
    return None


def _safe_headers(headers: Mapping[str, str] | object) -> dict[str, str]:
    if not isinstance(headers, Mapping):
        return {}
    safe: dict[str, str] = {}
    for key, value in headers.items():
        if not isinstance(key, str) or not isinstance(value, str):
            continue
        normalized_key = key.strip().lower()
        normalized_value = value.strip()
        if (
            normalized_key not in _ALLOWED_HEADER_NAMES
            or normalized_key in safe
            or not normalized_value
            or len(normalized_value) > 1024
            or any(ord(char) < 32 or ord(char) > 126 for char in normalized_value)
            or len(safe) >= len(_ALLOWED_HEADER_NAMES)
        ):
            continue
        safe[normalized_key] = normalized_value
    return safe


def _parse_resource_attributes(value: str) -> tuple[dict[str, str], bool]:
    attributes: dict[str, str] = {}
    conflict = False
    for item in value.split(","):
        if "=" not in item:
            continue
        key, raw_value = item.split("=", 1)
        key = key.strip()
        raw_value = raw_value.strip()
        if key and raw_value:
            if key in attributes and attributes[key] != raw_value:
                conflict = True
            attributes[key] = raw_value
    return attributes, conflict


def _parse_headers(value: str | None) -> dict[str, str]:
    """解析标准 Header 配置；不在异常日志中回显其值。"""

    if not value or len(value) > 4096 or any(ord(char) < 32 for char in value):
        return {}
    headers: dict[str, str] = {}
    for item in value.split(","):
        match = _HEADER_PART_RE.match(item)
        if match:
            key, header_value = match.groups()
            normalized_key = key.lower()
            if normalized_key in _ALLOWED_HEADER_NAMES:
                if normalized_key in headers:
                    return {}
                headers[normalized_key] = header_value
    return _safe_headers(headers)
