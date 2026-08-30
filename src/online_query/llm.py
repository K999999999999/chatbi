"""使用 LangChain（语言链）调用 LLM（大模型）生成 SQL 候选。"""

from collections.abc import Mapping
import os
from typing import Protocol

from langchain_openai import ChatOpenAI


class LLMError(RuntimeError):
    """LLM 配置、调用或返回内容不满足最小契约。"""


class _InvokableModel(Protocol):
    def invoke(self, input: object) -> object:
        """同步调用模型。"""


class LangChainSQLGenerator:
    """只负责把完整 Prompt 交给模型并返回文本。"""

    def __init__(self, model: _InvokableModel) -> None:
        self._model = model

    @classmethod
    def from_env(
        cls,
        environ: Mapping[str, str] | None = None,
    ) -> "LangChainSQLGenerator":
        source = os.environ if environ is None else environ
        api_key = source.get("LLM_API_KEY", "").strip()
        model_name = source.get("LLM_MODEL", "").strip()
        if not api_key:
            raise LLMError("缺少 LLM_API_KEY 配置")
        if not model_name:
            raise LLMError("缺少 LLM_MODEL 配置")

        try:
            temperature = float(source.get("LLM_TEMPERATURE", "0.1"))
            max_tokens = int(source.get("LLM_MAX_TOKENS", "1200"))
            timeout = float(source.get("LLM_TIMEOUT_SECONDS", "30"))
        except ValueError:
            raise LLMError("LLM 数字配置无效") from None
        if max_tokens <= 0 or timeout <= 0:
            raise LLMError("LLM 数字配置无效")

        base_url = source.get("LLM_BASE_URL", "").strip() or None
        try:
            model = ChatOpenAI(
                api_key=api_key,
                base_url=base_url,
                model=model_name,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout,
                max_retries=0,
                use_responses_api=False,
            )
        except Exception as exc:
            raise LLMError("LLM 配置无效") from exc
        return cls(model)

    def generate(self, prompt: str) -> str:
        try:
            response = self._model.invoke(prompt)
        except Exception as exc:
            raise LLMError("LLM 调用失败") from exc

        content = getattr(response, "content", None)
        if not isinstance(content, str):
            raise LLMError("LLM 未返回文本")
        result = content.strip()
        if not result:
            raise LLMError("LLM 返回空响应")
        return result