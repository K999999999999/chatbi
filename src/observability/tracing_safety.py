"""Observability 的安全属性、Trace ID 和 Fail-open 辅助函数。"""

from collections.abc import Mapping
import logging
import math
import re
import secrets
from typing import Any

from opentelemetry.trace import Span as OTelSpan
from opentelemetry.trace import Status, StatusCode

from .contracts import ErrorType, QuerySource, TraceOutcome


_LOGGER = logging.getLogger(__name__)
_TRACE_ID_RE = re.compile(r"^[0-9a-f]{32}$")
_ERROR_CODE_RE = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")
_SAFE_OUTCOMES = frozenset(item.value for item in TraceOutcome)
_SAFE_ERROR_TYPES = frozenset(item.value for item in ErrorType)
_SAFE_WARNING_STAGES = frozenset(
    {
        "attribute",
        "exporter_configuration",
        "exporter_export",
        "exporter_force_flush",
        "exporter_initialization",
        "exporter_shutdown",
        "instrumentation",
        "provider_shutdown",
        "query_trace",
        "safe_enrich_current",
        "safe_query_trace",
        "safe_shutdown",
        "safe_span",
        "scope_context_exit",
        "scope_context_reset",
        "scope_end",
        "scope_enter",
        "span",
        "span_start",
        "status",
    }
)
_SAFE_GEN_AI_ATTRIBUTE_RULES: dict[str, str] = {
    "gen_ai.operation.name": "gen_ai_operation",
    "gen_ai.request.model": "gen_ai_model",
    "gen_ai.response.model": "gen_ai_model",
    "gen_ai.usage.input_tokens": "gen_ai_count",
    "gen_ai.usage.output_tokens": "gen_ai_count",
    "gen_ai.usage.total_tokens": "gen_ai_count",
}
_SAFE_ATTRIBUTE_RULES: dict[str, str] = {
    "evaluation.case_id": "identifier",
    "chatbi.request.source": "source",
    "chatbi.request.id": "identifier",
    "chatbi.content_capture.enabled": "boolean",
    "chatbi.outcome": "outcome",
    "chatbi.error.type": "error_type",
    "chatbi.error_code": "error_code",
    "chatbi.status": "status",
    "chatbi.result.status": "status",
    "chatbi.retrieval.status": "status",
    "chatbi.retrieval.request_shape": "status",
    "chatbi.retrieval.fallback_policy": "status",
    "chatbi.retrieval.fallback_used": "boolean",
    "chatbi.retrieval.context_source": "identifier",
    "chatbi.retrieval.asset_version": "version",
    "chatbi.retrieval.candidate_id": "identifier",
    "chatbi.retrieval.candidate_type": "identifier",
    "chatbi.retrieval.candidate.document_ids": "identifier_list",
    "chatbi.retrieval.candidate.ranks": "count_list",
    "chatbi.retrieval.candidate.scores": "number_list",
    "chatbi.retrieval.candidate.qualified_tables": "identifier_list",
    "chatbi.retrieval.search.qualified_table": "identifier",
    "chatbi.retrieval.table_count": "count",
    "chatbi.retrieval.column_count": "count",
    "chatbi.retrieval.metric_count": "count",
    "chatbi.retrieval.join.edge_ids": "identifier_list",
    "chatbi.retrieval.join.path_ids": "identifier_list",
    "chatbi.retrieval.join.path_count": "count",
    "chatbi.query_understanding.query_type": "identifier",
    "chatbi.query_understanding.metric_count": "count",
    "chatbi.query_understanding.filter_count": "count",
    "chatbi.query_understanding.has_time": "boolean",
    "chatbi.query_understanding.reason": "reason",
    "chatbi.prompt.length": "count",
    "chatbi.prompt.question_length": "count",
    "chatbi.prompt.context_length": "count",
    "chatbi.sql.sha256": "hash",
    "chatbi.database.row_count": "count",
    "chatbi.database.truncated": "boolean",
    "chatbi.trace.version": "version",
    "chatbi.schema.version": "version",
    "chatbi.retry_count": "count",
    "chatbi.retrieval.candidate_count": "count",
    "chatbi.result.row_count": "count",
    "chatbi.duration_ms": "count",
    **_SAFE_GEN_AI_ATTRIBUTE_RULES,
}
_SAFE_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_SAFE_HASH_RE = re.compile(r"^[0-9a-fA-F]{32,128}$")
_SAFE_VERSION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,63}$")
_SAFE_REASON_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_SAFE_GEN_AI_MODEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/+@-]{0,127}$")
_UNSAFE_GEN_AI_MODEL_RE = re.compile(
    r"(?:api[-_ ]?key|authorization|bearer|password|secret|"
    r"access[-_ ]?token|prompt|sql|raw(?:[-_ ]?response)?)",
    re.IGNORECASE,
)
_SENSITIVE_VALUE_RE = re.compile(
    r"(?:raw[-_ ]?secret|password|authorization|api[-_ ]?key|bearer|access[-_ ]?token)",
    re.IGNORECASE,
)


def safe_attributes(attributes: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(attributes, Mapping):
        return {}
    result: dict[str, Any] = {}
    for raw_key, value in attributes.items():
        if not isinstance(raw_key, str):
            continue
        rule = _SAFE_ATTRIBUTE_RULES.get(raw_key)
        if rule is None:
            continue
        safe_value = safe_attribute_value(value, rule)
        if safe_value is not None:
            result[raw_key] = safe_value
    return result


def safe_attribute_value(value: Any, rule: str) -> Any:
    if rule == "boolean":
        return value if isinstance(value, bool) else None
    if rule in {"count", "gen_ai_count"}:
        return (
            value
            if isinstance(value, int) and not isinstance(value, bool) and value >= 0
            else None
        )
    if rule in {"identifier_list", "count_list", "number_list"}:
        if not isinstance(value, (list, tuple)):
            return None
        safe_values: list[Any] = []
        for item in value[:10]:
            if rule == "identifier_list":
                if (
                    isinstance(item, str)
                    and _SAFE_IDENTIFIER_RE.fullmatch(item)
                    and not _SENSITIVE_VALUE_RE.search(item)
                ):
                    safe_values.append(item)
            elif rule == "count_list":
                if isinstance(item, int) and not isinstance(item, bool) and item >= 0:
                    safe_values.append(item)
            elif (
                isinstance(item, (int, float))
                and not isinstance(item, bool)
                and math.isfinite(float(item))
            ):
                safe_values.append(item)
        return tuple(safe_values) or None
    if not isinstance(value, str):
        return None
    if len(value) > 128 or "\n" in value or "\r" in value:
        return None
    if _SENSITIVE_VALUE_RE.search(value):
        return None
    if rule == "gen_ai_operation":
        return value if value == "chat" else None
    if rule == "gen_ai_model":
        if _UNSAFE_GEN_AI_MODEL_RE.search(value) is not None:
            return None
        return value if _SAFE_GEN_AI_MODEL_RE.fullmatch(value) else None
    if rule == "source":
        return value if value in {item.value for item in QuerySource} else None
    if rule == "outcome":
        return value if value in _SAFE_OUTCOMES else None
    if rule == "error_type":
        return value if value in _SAFE_ERROR_TYPES else None
    if rule == "error_code":
        return value if is_safe_error_code(value) else None
    if rule == "identifier":
        return value if _SAFE_IDENTIFIER_RE.fullmatch(value) else None
    if rule == "hash":
        return value if _SAFE_HASH_RE.fullmatch(value) else None
    if rule == "version":
        return value if _SAFE_VERSION_RE.fullmatch(value) else None
    if rule == "reason":
        return value if _SAFE_REASON_RE.fullmatch(value) else None
    if rule == "status":
        return value if _SAFE_IDENTIFIER_RE.fullmatch(value) else None
    return None


def safe_span_name(name: str) -> str | None:
    if not isinstance(name, str):
        return None
    normalized = name.strip()
    if not normalized or len(normalized) > 128 or "\n" in normalized:
        return None
    return normalized


def safe_source(source: QuerySource | str) -> str:
    if isinstance(source, QuerySource):
        return source.value
    if isinstance(source, str) and source.strip().upper() in {
        item.value for item in QuerySource
    }:
        return source.strip().upper()
    return QuerySource.INTERNAL.value


def safe_enum_value(value: Any, allowed: frozenset[str]) -> str | None:
    candidate = value.value if isinstance(value, (TraceOutcome, ErrorType)) else value
    if isinstance(candidate, str) and candidate in allowed:
        return candidate
    return None


def is_safe_error_code(value: str | None) -> bool:
    return isinstance(value, str) and _ERROR_CODE_RE.fullmatch(value) is not None


def safe_set_attribute(span: OTelSpan, key: str, value: Any) -> None:
    try:
        span.set_attribute(key, value)
    except Exception:
        safe_warning("attribute")


def safe_set_status(span: OTelSpan, outcome: str) -> None:
    try:
        status_code = (
            StatusCode.OK
            if outcome
            in {
                TraceOutcome.SUCCESS.value,
                TraceOutcome.FALLBACK_SUCCESS.value,
            }
            else StatusCode.ERROR
            if outcome
            in {
                TraceOutcome.TECHNICAL_FAILURE.value,
                TraceOutcome.TIMEOUT.value,
            }
            else StatusCode.UNSET
        )
        span.set_status(Status(status_code))
    except Exception:
        safe_warning("status")


def trace_id_from_span(span: OTelSpan) -> str:
    try:
        return valid_trace_id(f"{span.get_span_context().trace_id:032x}")
    except Exception:
        return new_trace_id()


def valid_trace_id(value: str) -> str:
    if _TRACE_ID_RE.fullmatch(value) and int(value, 16) != 0:
        return value
    return new_trace_id()


def new_trace_id() -> str:
    value = secrets.token_hex(16)
    return value if int(value, 16) != 0 else "0" * 31 + "1"


def safe_warning(stage: str) -> None:
    try:
        safe_stage = stage if stage in _SAFE_WARNING_STAGES else "instrumentation"
        _LOGGER.warning(
            "Observability degraded: component=trace stage=%s error_type=INSTRUMENTATION",
            safe_stage,
        )
    except Exception:
        pass
