"""POC 配置：从 ``.env`` 和进程环境读取 LLM 配置。"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from scripts.metadata.export_schema import load_env


class LlmConfigurationError(ValueError):
    """LLM 配置不完整或不是有效值。"""


@dataclass(frozen=True)
class LlmConfig:
    """OpenAI-compatible LLM（兼容 OpenAI 接口的大模型）调用参数。"""

    api_key: str
    base_url: str
    model: str
    temperature: float = 0.1
    max_tokens: int = 1200
    timeout_seconds: float = 30.0

    @classmethod
    def from_env_file(cls, env_file: Path) -> "LlmConfig":
        """读取本地配置；进程环境变量优先于 ``.env``。"""

        values = load_env(env_file)
        for key in (
            "LLM_API_KEY",
            "OPENAI_API_KEY",
            "LLM_BASE_URL",
            "OPENAI_BASE_URL",
            "LLM_MODEL",
            "LLM_TEMPERATURE",
            "LLM_MAX_TOKENS",
            "LLM_TIMEOUT_SECONDS",
        ):
            if key in os.environ:
                values[key] = os.environ[key]

        api_key = values.get("LLM_API_KEY") or values.get("OPENAI_API_KEY", "")
        if not api_key:
            raise LlmConfigurationError(
                "缺少 LLM_API_KEY（或 OPENAI_API_KEY），无法直接调用 LLM"
            )

        base_url = values.get("LLM_BASE_URL") or values.get(
            "OPENAI_BASE_URL", "https://api.openai.com/v1"
        )
        model = values.get("LLM_MODEL", "gpt-4o")
        if not base_url:
            raise LlmConfigurationError("LLM_BASE_URL 不能为空")
        if not model:
            raise LlmConfigurationError("LLM_MODEL 不能为空")

        return cls(
            api_key=api_key,
            base_url=base_url,
            model=model,
            temperature=_parse_float(values, "LLM_TEMPERATURE", 0.1),
            max_tokens=_parse_positive_int(values, "LLM_MAX_TOKENS", 1200),
            timeout_seconds=_parse_positive_float(
                values, "LLM_TIMEOUT_SECONDS", 30.0
            ),
        )


def _parse_float(values: dict[str, str], key: str, default: float) -> float:
    raw = values.get(key, "")
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise LlmConfigurationError(f"{key} 必须是数字") from exc
    if value < 0:
        raise LlmConfigurationError(f"{key} 不能小于 0")
    return value


def _parse_positive_float(
    values: dict[str, str], key: str, default: float
) -> float:
    value = _parse_float(values, key, default)
    if value <= 0:
        raise LlmConfigurationError(f"{key} 必须大于 0")
    return value


def _parse_positive_int(values: dict[str, str], key: str, default: int) -> int:
    raw = values.get(key, "")
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise LlmConfigurationError(f"{key} 必须是整数") from exc
    if value <= 0:
        raise LlmConfigurationError(f"{key} 必须大于 0")
    return value
