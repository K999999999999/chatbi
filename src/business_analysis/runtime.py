"""Business Analysis 语义上下文加载与模型适配配置。"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from datetime import datetime
from math import isfinite
from pathlib import Path

from langchain_openai import ChatOpenAI

from src.online_query.contracts import QueryErrorCode, QueryFailure
from src.online_query.query_understanding import FilterOperator, TimeGranularity

from .attribution import (
    BusinessAnalysisAttribution,
    FactorContribution,
    ProductContribution,
)
from .contracts import (
    AnalysisDecompositionContext,
    AnalysisFilter,
    AnalysisPlan,
    AnalysisRequest,
    AnalysisRequestCandidate,
    AnalysisSemanticCatalog,
    AnalysisTask,
    AnalysisTaskCandidate,
    AnalysisTaskType,
    AnalysisTimeRange,
)
from .execution import TaskError, TaskResult, TaskStatus
from .reporting import (
    AnalysisReportError,
    BusinessAnalysisReport,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_METRICS_PATH = PROJECT_ROOT / "src" / "semantic" / "metrics.json"
DEFAULT_DIMENSIONS_PATH = PROJECT_ROOT / "src" / "semantic" / "dimensions.json"


def _checkpoint_allowed_types() -> list[tuple[str, str]]:
    """仅允许反序列化经营分析图实际写入的 Python 类型。"""

    allowed = (
        BusinessAnalysisAttribution,
        FactorContribution,
        ProductContribution,
        AnalysisDecompositionContext,
        AnalysisFilter,
        AnalysisPlan,
        AnalysisRequest,
        AnalysisRequestCandidate,
        AnalysisSemanticCatalog,
        AnalysisTask,
        AnalysisTaskCandidate,
        AnalysisTaskType,
        AnalysisTimeRange,
        TaskError,
        TaskResult,
        TaskStatus,
        QueryErrorCode,
        QueryFailure,
        BusinessAnalysisReport,
        AnalysisReportError,
        FilterOperator,
        TimeGranularity,
    )
    return [(item.__module__, item.__name__) for item in allowed]


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


def _build_chat_model(
    environ: Mapping[str, str] | None,
    *,
    http_client: object | None = None,
    http_async_client: object | None = None,
) -> object:
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
    client_options = {}
    if http_client is not None:
        client_options["http_client"] = http_client
    if http_async_client is not None:
        client_options["http_async_client"] = http_async_client
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
            **client_options,
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
