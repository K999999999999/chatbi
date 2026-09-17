"""使用 LangChain（语言链）调用 LLM（大模型）生成 SQL 候选。"""

import os
import re
from collections.abc import Mapping
from math import isfinite
from typing import Protocol

from langchain_openai import ChatOpenAI

from ..observability.contracts import TraceRecorder


class LLMError(RuntimeError):
    """LLM 配置、调用或返回内容不满足最小契约。"""

    def __init__(self, message: str, *, reason: str = "LLM_ERROR") -> None:
        super().__init__(message)
        self.reason = reason


_MAX_LLM_TIMEOUT_SECONDS = 30.0


class _InvokableModel(Protocol):
    def invoke(self, input: object) -> object:
        """同步调用模型。"""


class LangChainSQLGenerator:
    """只负责把完整 Prompt 交给模型并返回文本。"""

    def __init__(
        self,
        model: _InvokableModel,
        trace_recorder: TraceRecorder | None = None,
        model_name: str | None = None,
    ) -> None:
        self._model = model
        self._trace_recorder = trace_recorder
        self._model_name = _safe_model_name(model_name)

    @classmethod
    def from_env(
        cls,
        environ: Mapping[str, str] | None = None,
        *,
        trace_recorder: TraceRecorder | None = None,
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
        if max_tokens <= 0 or not isfinite(timeout) or timeout <= 0:
            raise LLMError("LLM 数字配置无效")
        timeout = min(timeout, _MAX_LLM_TIMEOUT_SECONDS)

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
        return cls(
            model,
            trace_recorder=trace_recorder,
            model_name=model_name,
        )

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
        self._enrich_current(response)
        return result

    def _enrich_current(self, response: object) -> None:
        if self._trace_recorder is None:
            return

        attributes: dict[str, str | int] = {
            "gen_ai.operation.name": "chat",
        }
        if self._model_name is not None:
            attributes["gen_ai.request.model"] = self._model_name

        response_metadata = _safe_mapping(response, "response_metadata")
        response_model = None
        if response_metadata is not None:
            for model_key in ("model_name", "model"):
                response_model = _safe_model_name(
                    _mapping_value(response_metadata, model_key)
                )
                if response_model is not None:
                    break
        if response_model is not None:
            attributes["gen_ai.response.model"] = response_model

        usage_metadata = _safe_mapping(response, "usage_metadata")
        token_usage = _safe_mapping_value(response_metadata, "token_usage")
        for attribute_name, usage_key, fallback_key in (
            ("gen_ai.usage.input_tokens", "input_tokens", "prompt_tokens"),
            ("gen_ai.usage.output_tokens", "output_tokens", "completion_tokens"),
            ("gen_ai.usage.total_tokens", "total_tokens", "total_tokens"),
        ):
            value = _valid_non_negative_int(
                _mapping_value(usage_metadata, usage_key)
            )
            if value is None:
                value = _valid_non_negative_int(
                    _mapping_value(token_usage, fallback_key)
                )
            if value is not None:
                attributes[attribute_name] = value

        try:
            self._trace_recorder.enrich_current(attributes=attributes)
        except Exception:
            pass


_SAFE_MODEL_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/+@-]{0,127}$")
_UNSAFE_MODEL_NAME_RE = re.compile(
    r"(?:api[-_ ]?key|authorization|bearer|password|secret|"
    r"access[-_ ]?token|prompt|sql|raw(?:[-_ ]?response)?|sk-)",
    re.IGNORECASE,
)


def _safe_model_name(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    candidate = value.strip()
    if (
        not candidate
        or "\n" in candidate
        or "\r" in candidate
        or _UNSAFE_MODEL_NAME_RE.search(candidate) is not None
        or _SAFE_MODEL_NAME_RE.fullmatch(candidate) is None
    ):
        return None
    return candidate


def _safe_mapping(value: object, attribute: str) -> Mapping[str, object] | None:
    try:
        candidate = getattr(value, attribute, None)
    except Exception:
        return None
    return candidate if isinstance(candidate, Mapping) else None


def _safe_mapping_value(
    value: Mapping[str, object] | None,
    key: str,
) -> Mapping[str, object] | None:
    if value is None:
        return None
    candidate = _mapping_value(value, key)
    return candidate if isinstance(candidate, Mapping) else None


def _mapping_value(value: Mapping[str, object] | None, key: str) -> object | None:
    if value is None:
        return None
    try:
        return value.get(key)
    except Exception:
        return None


def _valid_non_negative_int(value: object) -> int | None:
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    return None
