"""Query API 启动配置加载。"""

import json
import os
from collections.abc import Mapping
from pathlib import Path

from dotenv import dotenv_values

from src.authorization import (
    IdentityProviderAdapter,
    StaticAuthorizationPolicyStore,
    StaticIdentityProviderAdapter,
)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_SUPPORTED_STATIC_PROVIDERS = frozenset({"demo", "test"})
_SUPPORTED_NON_PRODUCTION_ENVIRONMENTS = frozenset(
    {"development", "dev", "test", "testing"}
)
_PRODUCTION_ENVIRONMENTS = frozenset({"production", "prod"})


class IdentityProviderConfigurationError(RuntimeError):
    """身份 Provider 配置不完整或不安全。"""


class AuthorizationPolicyConfigurationError(RuntimeError):
    """授权策略文件缺失、不可读或格式不符合 Contract。"""


class RuntimeConfigurationError(RuntimeError):
    """真实 Query API 运行模式缺失或包含已废弃的静态身份配置。"""


_SUPPORTED_RUNTIME_ENVIRONMENTS = frozenset(
    {"development", "dev", "test", "testing", "staging", "production", "prod"}
)
_STATIC_AUTH_KEYS = frozenset(
    {
        "CHATBI_IDENTITY_PROVIDER",
        "CHATBI_IDENTITY_SUBJECT_ID",
        "CHATBI_AUTH_POLICY_FILE",
    }
)
_DATABASE_MIGRATION_KEYS = frozenset(
    {
        "POSTGRES_MIGRATOR_USER",
        "POSTGRES_MIGRATOR_PASSWORD",
        "POSTGRES_CONTROL_MIGRATOR_USER",
    }
)


def load_local_environment(env_file: Path | None = None) -> None:
    """加载本地 .env，并保留外部环境变量的优先级。

    本地开发时默认读取项目根目录的 .env。正式环境通常不提供该文件，
    而是由部署平台注入环境变量或 Secret，因此缺少文件本身不会导致启动失败。
    必填配置仍由各自的配置工厂负责校验。
    """

    path = _PROJECT_ROOT / ".env" if env_file is None else env_file
    for key in _DATABASE_MIGRATION_KEYS:
        os.environ.pop(key, None)

    for key, value in dotenv_values(path).items():
        if key not in _DATABASE_MIGRATION_KEYS and value is not None:
            os.environ.setdefault(key, value)


def validate_runtime_configuration(
    environ: Mapping[str, str] | None = None,
) -> str:
    """校验真实入口的运行模式；静态身份配置只允许测试代码直接调用。"""

    values = os.environ if environ is None else environ
    environment = values.get("CHATBI_ENV", "").strip().lower()
    if environment not in _SUPPORTED_RUNTIME_ENVIRONMENTS:
        raise RuntimeConfigurationError(
            "CHATBI_ENV 必须显式设置为 development、staging 或 production"
        )
    if environment in _PRODUCTION_ENVIRONMENTS and any(
        values.get(key, "").strip() for key in _STATIC_AUTH_KEYS
    ):
        raise RuntimeConfigurationError(
            "production 运行入口不支持 CHATBI_IDENTITY_* 或 CHATBI_AUTH_POLICY_FILE"
        )
    return environment


def build_identity_provider(
    environ: Mapping[str, str] | None = None,
) -> IdentityProviderAdapter:
    """构造显式配置的 Demo/Test Provider，不允许隐式身份回退。"""

    values = os.environ if environ is None else environ
    environment = values.get("CHATBI_ENV", "").strip().lower()
    provider_name = values.get("CHATBI_IDENTITY_PROVIDER", "").strip().lower()
    subject_id = values.get("CHATBI_IDENTITY_SUBJECT_ID", "").strip()

    if environment in _PRODUCTION_ENVIRONMENTS:
        raise IdentityProviderConfigurationError(
            "production 环境不能启用 demo 或 test Identity Provider"
        )
    if environment not in _SUPPORTED_NON_PRODUCTION_ENVIRONMENTS:
        raise IdentityProviderConfigurationError(
            "CHATBI_ENV 必须显式设置为 development 或 test"
        )
    if provider_name not in _SUPPORTED_STATIC_PROVIDERS:
        raise IdentityProviderConfigurationError(
            "CHATBI_IDENTITY_PROVIDER 必须显式设置为 demo 或 test"
        )
    if not subject_id:
        raise IdentityProviderConfigurationError(
            "CHATBI_IDENTITY_SUBJECT_ID 必须显式设置"
        )

    return StaticIdentityProviderAdapter(
        identity_provider=provider_name,
        subject_id=subject_id,
    )


def build_policy_store(
    environ: Mapping[str, str] | None = None,
) -> StaticAuthorizationPolicyStore:
    """从外部 JSON 文件加载 V1 静态授权白名单。"""

    values = os.environ if environ is None else environ
    configured_path = values.get("CHATBI_AUTH_POLICY_FILE", "").strip()
    if not configured_path:
        raise AuthorizationPolicyConfigurationError(
            "CHATBI_AUTH_POLICY_FILE 必须显式设置"
        )

    path = Path(configured_path)
    if not path.is_absolute():
        path = _PROJECT_ROOT / path
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise AuthorizationPolicyConfigurationError(
            f"无法读取授权策略文件: {path}"
        ) from exc

    if not isinstance(payload, dict):
        raise AuthorizationPolicyConfigurationError("授权策略文件必须是 JSON object")
    policy_version = payload.get("policy_version")
    allowed_subjects = payload.get("allowed_subjects")
    if (
        not isinstance(policy_version, str)
        or not policy_version.strip()
        or not isinstance(allowed_subjects, list)
        or any(
            not isinstance(subject, str) or not subject.strip()
            for subject in allowed_subjects
        )
    ):
        raise AuthorizationPolicyConfigurationError(
            "授权策略必须包含非空 policy_version 和字符串数组 allowed_subjects"
        )

    return StaticAuthorizationPolicyStore(
        allowed_subjects=frozenset(subject.strip() for subject in allowed_subjects),
        policy_version=policy_version.strip(),
    )
