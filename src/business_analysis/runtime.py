"""Business Analysis 生产装配和语义上下文加载。"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from datetime import datetime
from math import isfinite
from pathlib import Path

from langchain_openai import ChatOpenAI

from .application import BusinessAnalysisApplication, AuthorizedQueryEntry
from .contracts import AnalysisDecompositionContext
from .decomposer import LangChainAnalysisPlanDecomposer
from .reporting import LangChainAnalysisSummarizer


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_METRICS_PATH = PROJECT_ROOT / "src" / "semantic" / "metrics.json"
DEFAULT_DIMENSIONS_PATH = PROJECT_ROOT / "src" / "semantic" / "dimensions.json"


def build_analysis_application(
    authorized_query_service: AuthorizedQueryEntry,
    *,
    environ: Mapping[str, str] | None = None,
    metrics_path: Path = DEFAULT_METRICS_PATH,
    dimensions_path: Path = DEFAULT_DIMENSIONS_PATH,
) -> BusinessAnalysisApplication:
    """装配真实 LLM 边缘和当前语义事实。"""

    model = _build_chat_model(environ)
    return BusinessAnalysisApplication(
        authorized_query_service,
        decomposer=LangChainAnalysisPlanDecomposer(model),
        summarizer=LangChainAnalysisSummarizer(model),
        context_provider=lambda: load_analysis_context(
            metrics_path=metrics_path,
            dimensions_path=dimensions_path,
        ),
    )


def load_analysis_context(
    *,
    metrics_path: Path = DEFAULT_METRICS_PATH,
    dimensions_path: Path = DEFAULT_DIMENSIONS_PATH,
) -> AnalysisDecompositionContext:
    metric_records = _load_records(metrics_path, "metrics")
    dimension_records = _load_records(dimensions_path, "dimensions")
    dimensions = tuple(_required_name(item, "dimension") for item in dimension_records)
    return AnalysisDecompositionContext(
        current_time=datetime.now().astimezone().isoformat(),
        metric_records=tuple(metric_records),
        dimensions=dimensions,
    )


def _build_chat_model(environ: Mapping[str, str] | None) -> object:
    source = os.environ if environ is None else environ
    api_key = source.get("LLM_API_KEY", "").strip()
    model_name = source.get("LLM_MODEL", "").strip()
    if not api_key or not model_name:
        raise RuntimeError("缺少经营分析 LLM 配置")
    try:
        temperature = float(source.get("LLM_TEMPERATURE", "0.1"))
        max_tokens = int(source.get("LLM_MAX_TOKENS", "1200"))
        timeout = min(float(source.get("LLM_TIMEOUT_SECONDS", "30")), 30.0)
    except ValueError:
        raise RuntimeError("经营分析 LLM 数字配置无效") from None
    if (
        not isfinite(temperature)
        or max_tokens <= 0
        or not isfinite(timeout)
        or timeout <= 0
    ):
        raise RuntimeError("经营分析 LLM 数字配置无效")
    base_url = source.get("LLM_BASE_URL", "").strip() or None
    try:
        return ChatOpenAI(
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
        raise RuntimeError("经营分析 LLM 配置无效") from exc


def _load_records(path: Path, label: str) -> list[dict[str, object]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"{label} 语义事实无法加载") from exc
    if not isinstance(payload, list) or not payload:
        raise RuntimeError(f"{label} 语义事实必须是非空数组")
    if any(not isinstance(item, Mapping) for item in payload):
        raise RuntimeError(f"{label} 语义事实结构无效")
    return [dict(item) for item in payload]


def _required_name(record: Mapping[str, object], label: str) -> str:
    value = record.get("name")
    if not isinstance(value, str) or not value.strip():
        raise RuntimeError(f"{label} 缺少有效 name")
    return value.strip()
