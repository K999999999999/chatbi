"""LLM Client（大模型客户端）：直接调用 OpenAI-compatible Chat Completions。"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Protocol

from openai import OpenAI

from src.poc.config import LlmConfig


class SqlGenerationError(RuntimeError):
    """LLM 没有返回可交给 SQL Guard 的 SQL 候选。"""

    def __init__(self, message: str, code: str = "llm_generation_failed") -> None:
        super().__init__(message)
        self.code = code


class LlmClient(Protocol):
    """可替换的 LLM 调用契约。"""

    def generate_sql(self, system_message: str, user_prompt: str) -> str:
        """根据 Prompt 返回纯 SQL 候选。"""


class OpenAICompatibleLlmClient:
    """使用 OpenAI SDK 调用 OpenAI-compatible 服务。"""

    def __init__(self, config: LlmConfig, client: Any | None = None) -> None:
        self.config = config
        self.client = client or OpenAI(
            api_key=config.api_key,
            base_url=config.base_url,
            timeout=config.timeout_seconds,
        )

    @classmethod
    def from_env_file(cls, env_file: Path) -> "OpenAICompatibleLlmClient":
        return cls(LlmConfig.from_env_file(env_file))

    def generate_sql(self, system_message: str, user_prompt: str) -> str:
        try:
            response = self.client.chat.completions.create(
                model=self.config.model,
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
            )
        except Exception as exc:
            raise SqlGenerationError("LLM 请求失败，请检查 API 配置或网络连接") from exc

        try:
            content = response.choices[0].message.content
        except (AttributeError, IndexError, TypeError) as exc:
            raise SqlGenerationError("LLM 响应缺少可用内容") from exc
        if not isinstance(content, str) or not content.strip():
            raise SqlGenerationError("LLM 返回了空内容")

        cleaned = clean_sql_output(content)
        if cleaned.upper() == "UNSUPPORTED":
            raise SqlGenerationError(
                "LLM 判定当前问题超出已提供的 Schema 或指标范围",
                code="unsupported_query",
            )
        return cleaned


def clean_sql_output(raw_output: str) -> str:
    """去除 Markdown SQL 围栏；不负责放宽 SQL 安全边界。"""

    cleaned = raw_output.strip()
    fenced = re.search(
        r"```(?:sql|postgresql)?\s*(.*?)```",
        cleaned,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if fenced:
        cleaned = fenced.group(1).strip()
    else:
        cleaned = re.sub(r"^```(?:sql|postgresql)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()
