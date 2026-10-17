"""版本化公开快照及私有状态编码；不恢复凭证或任意Python对象。"""

import json
from dataclasses import replace
from datetime import datetime
from decimal import Decimal, InvalidOperation
import math

from src.online_query.query_understanding import (
    TimeGranularity,
    ValidatedTime,
    candidate_from_payload,
    validate_candidate,
)

from .history_contracts import HistoryError

MAX_SNAPSHOT_BYTES = 5 * 1024 * 1024


def encode_snapshot(
    kind: str,
    result: dict,
    *,
    query_state: dict | None = None,
    original_question: str | None = None,
    source_question: str | None = None,
) -> dict:
    _validate_public_result(kind, result)
    envelope = {"version": 1, "kind": kind, "result": result}
    if kind == "query":
        if (
            query_state is None
            or not isinstance(source_question, str)
            or not source_question.strip()
        ):
            raise HistoryError(
                "HISTORY_SNAPSHOT_UNAVAILABLE", "完整恢复状态或来源问题不可用"
            )
        decode_query_state(query_state)
        envelope["query_state"] = query_state
        envelope["source_question"] = source_question.strip()
    elif kind == "analysis":
        if not original_question:
            raise HistoryError("HISTORY_SNAPSHOT_UNAVAILABLE", "原分析问题不可用")
        envelope["original_question"] = original_question
    else:
        raise HistoryError("HISTORY_SNAPSHOT_UNAVAILABLE", "快照类型不可用")
    try:
        encoded = json.dumps(
            envelope, ensure_ascii=False, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError):
        raise HistoryError("HISTORY_SNAPSHOT_UNAVAILABLE", "快照无法安全编码") from None
    if len(encoded) > MAX_SNAPSHOT_BYTES:
        raise HistoryError(
            "HISTORY_SNAPSHOT_TOO_LARGE", "结果快照超过5 MiB，未保存本次成功状态"
        )
    return json.loads(encoded)


def public_snapshot(envelope: dict) -> dict:
    kind = envelope.get("kind") if isinstance(envelope, dict) else None
    if (
        not isinstance(envelope, dict)
        or type(envelope.get("version")) is not int
        or envelope.get("version") != 1
        or not isinstance(kind, str)
        or kind not in {"query", "analysis"}
        or not isinstance(envelope.get("result"), dict)
    ):
        raise HistoryError("HISTORY_SNAPSHOT_UNAVAILABLE", "结果快照版本或内容不可用")
    base_fields = {"version", "kind", "result"}
    if kind == "query":
        allowed_fields = {
            frozenset(base_fields | {"query_state"}),
            frozenset(base_fields | {"query_state", "source_question"}),
        }
    else:
        allowed_fields = {frozenset(base_fields | {"original_question"})}
    if frozenset(envelope) not in allowed_fields:
        raise HistoryError("HISTORY_SNAPSHOT_UNAVAILABLE", "快照来源字段非法")
    if kind == "query":
        if not isinstance(envelope["query_state"], dict):
            raise HistoryError("HISTORY_SNAPSHOT_UNAVAILABLE", "查询恢复状态非法")
        if "source_question" in envelope and (
            not isinstance(envelope["source_question"], str)
            or not envelope["source_question"].strip()
        ):
            raise HistoryError("HISTORY_SNAPSHOT_UNAVAILABLE", "查询来源问题非法")
    elif (
        not isinstance(envelope["original_question"], str)
        or not envelope["original_question"].strip()
    ):
        raise HistoryError("HISTORY_SNAPSHOT_UNAVAILABLE", "分析来源问题非法")
    _validate_public_result(kind, envelope["result"])
    return envelope["result"]


def decode_query_state(state: dict):
    """重新进行结构校验；保留已确认绝对时间，不重解释相对文本。"""
    try:
        if (
            not isinstance(state, dict)
            or set(state) != {"state_version", "semantic_query", "provenance"}
            or type(state["state_version"]) is not int
            or state["state_version"] != 1
        ):
            raise ValueError("未知状态版本")
        if not isinstance(state["provenance"], dict) or set(state["provenance"]) != {
            "metrics",
            "bindings",
            "columns",
            "joins",
        }:
            raise ValueError("认证来源不完整")
        provenance = state["provenance"]
        if (
            not isinstance(provenance["metrics"], list)
            or not isinstance(provenance["joins"], list)
            or not isinstance(provenance["bindings"], dict)
            or not isinstance(provenance["columns"], dict)
        ):
            raise TypeError("认证来源类型非法")
        payload = dict(state["semantic_query"])
        absolute_time = payload.get("time")
        payload["time"] = None
        semantic = validate_candidate(
            candidate_from_payload(payload, require_restorable=True),
            original_question="历史结构化查询",
        )
        if absolute_time is not None:
            if set(absolute_time) != {"text", "granularity", "start", "end"}:
                raise ValueError("绝对时间字段非法")
            if (
                not isinstance(absolute_time["text"], str)
                or not absolute_time["text"].strip()
            ):
                raise ValueError("绝对时间说明非法")
            start, end = (
                datetime.fromisoformat(absolute_time["start"]),
                datetime.fromisoformat(absolute_time["end"]),
            )
            if start.tzinfo is None or end.tzinfo is None or start >= end:
                raise ValueError("绝对时间区间非法")
            semantic = replace(
                semantic,
                time=ValidatedTime(
                    absolute_time["text"],
                    TimeGranularity(absolute_time["granularity"]),
                    start,
                    end,
                ),
            )
        return semantic
    except (ValueError, TypeError, KeyError, AttributeError):
        raise HistoryError(
            "HISTORY_CONTEXT_INCOMPATIBLE",
            "历史查询条件不可恢复，请新开对话并补全问题",
        ) from None


def _validate_public_result(kind: str, result: dict) -> None:
    if kind == "query":
        required = {"request_id", "sql", "columns", "rows", "row_count", "truncated"}
        if not _has_exact_fields(result, required, {"result_metadata"}):
            _invalid_snapshot()
        columns, rows = result["columns"], result["rows"]
        if (
            not _is_string_list(columns)
            or not _valid_rows(rows, columns, maximum=100)
            or type(result["row_count"]) is not int
            or result["row_count"] != len(rows)
            or type(result["truncated"]) is not bool
            or not isinstance(result["sql"], str)
            or not isinstance(result["request_id"], str)
        ):
            _invalid_snapshot("快照表格内容非法")
        if "result_metadata" in result:
            _validate_result_metadata(result["result_metadata"], columns, len(rows))
        return

    required = {
        "request_id",
        "analysis_run_id",
        "mode",
        "report",
        "task_results",
    }
    if (
        not _has_exact_fields(result, required)
        or not _is_nonempty_string(result["request_id"])
        or not _is_nonempty_string(result["analysis_run_id"])
        or result["mode"] != "analysis"
        or not isinstance(result["task_results"], list)
    ):
        _invalid_snapshot("分析快照公开字段非法")

    task_ids: set[str] = set()
    completed_task_ids: set[str] = set()
    for task in result["task_results"]:
        _validate_analysis_task(task)
        task_id = task["task_id"]
        if task_id in task_ids:
            _invalid_snapshot("分析任务身份重复")
        task_ids.add(task_id)
        if task["status"] == "completed":
            completed_task_ids.add(task_id)
    _validate_analysis_report(result["report"], task_ids, completed_task_ids)


def _validate_analysis_report(
    report: object,
    task_ids: set[str],
    completed_task_ids: set[str],
) -> None:
    required = {
        "title",
        "executive_summary",
        "key_findings",
        "trend_judgment",
        "root_causes",
        "action_suggestions",
        "evidence_task_ids",
        "incomplete_tasks",
    }
    if not _has_exact_fields(report, required, {"attribution"}):
        _invalid_snapshot("分析报告结构非法")
    if not all(
        _is_nonempty_string(report[key])
        for key in ("title", "executive_summary", "trend_judgment")
    ) or not all(
        _is_string_list(report[key])
        for key in (
            "key_findings",
            "root_causes",
            "action_suggestions",
            "evidence_task_ids",
        )
    ):
        _invalid_snapshot("分析报告字段非法")
    evidence_ids = report["evidence_task_ids"]
    if len(set(evidence_ids)) != len(evidence_ids) or not set(evidence_ids).issubset(
        completed_task_ids
    ):
        _invalid_snapshot("分析报告证据引用非法")

    incomplete = report["incomplete_tasks"]
    if not isinstance(incomplete, list):
        _invalid_snapshot("分析报告不完整任务非法")
    incomplete_ids: set[str] = set()
    for item in incomplete:
        if (
            not _has_exact_fields(item, {"task_id", "reasons"})
            or not _is_nonempty_string(item["task_id"])
            or item["task_id"] not in task_ids
            or item["task_id"] in incomplete_ids
            or not _is_string_list(item["reasons"])
            or not item["reasons"]
            or not set(item["reasons"]).issubset(
                {"failed", "skipped", "empty_result", "truncated"}
            )
        ):
            _invalid_snapshot("分析报告不完整任务非法")
        incomplete_ids.add(item["task_id"])
    if "attribution" in report:
        _validate_attribution(report["attribution"])


def _validate_analysis_task(task: object) -> None:
    required = {
        "task_id",
        "status",
        "columns",
        "rows",
        "row_count",
        "truncated",
        "error",
    }
    if not _has_exact_fields(task, required, {"result_metadata"}):
        _invalid_snapshot("分析任务结构非法")
    columns, rows = task["columns"], task["rows"]
    row_count, truncated = task["row_count"], task["truncated"]
    if (
        not _is_nonempty_string(task["task_id"])
        or not isinstance(task["status"], str)
        or task["status"] not in {"completed", "failed", "skipped"}
        or not _is_string_list(columns)
        or not _valid_rows(rows, columns, maximum=100)
        or type(row_count) is not int
        or row_count < len(rows)
        or (not truncated and row_count != len(rows))
        or type(truncated) is not bool
    ):
        _invalid_snapshot("分析任务结果非法")
    error = task["error"]
    if error is not None and (
        not _has_exact_fields(error, {"code", "message"})
        or not _is_nonempty_string(error["code"])
        or not isinstance(error["message"], str)
    ):
        _invalid_snapshot("分析任务错误结构非法")
    if "result_metadata" in task:
        _validate_result_metadata(task["result_metadata"], columns, len(rows))


def _validate_attribution(value: object) -> None:
    required = {
        "metric_name",
        "comparison_period",
        "current_period",
        "comparison_value",
        "current_value",
        "total_change",
        "direction",
        "products",
        "omitted_product_count",
        "reconciliation_passed",
    }
    if not _has_exact_fields(value, required):
        _invalid_snapshot("分析归因结构非法")
    if (
        not isinstance(value["metric_name"], str)
        or value["metric_name"] not in {"人民币毛利", "人民币净销售额"}
        or not _is_nonempty_string(value["comparison_period"])
        or not _is_nonempty_string(value["current_period"])
        or any(
            not _is_decimal_text(value[key])
            for key in ("comparison_value", "current_value", "total_change")
        )
        or not isinstance(value["direction"], str)
        or value["direction"] not in {"increase", "decrease", "unchanged"}
        or type(value["omitted_product_count"]) is not int
        or value["omitted_product_count"] < 0
        or value["reconciliation_passed"] is not True
        or not isinstance(value["products"], list)
    ):
        _invalid_snapshot("分析归因字段非法")
    for product in value["products"]:
        if not _has_exact_fields(
            product,
            {
                "product_name",
                "change",
                "effect_on_metric",
                "classification",
                "factors",
            },
        ):
            _invalid_snapshot("产品归因结构非法")
        if (
            not isinstance(product["product_name"], str)
            or not _is_decimal_text(product["change"])
            or not isinstance(product["effect_on_metric"], str)
            or product["effect_on_metric"] not in _METRIC_EFFECTS
            or not isinstance(product["classification"], str)
            or product["classification"]
            not in {
                "continuing",
                "new_product",
                "exited_product",
                "new",
                "discontinued",
            }
            or not isinstance(product["factors"], list)
        ):
            _invalid_snapshot("产品归因字段非法")
        for factor in product["factors"]:
            if (
                not _has_exact_fields(factor, {"name", "amount", "effect_on_metric"})
                or not isinstance(factor["name"], str)
                or not _is_decimal_text(factor["amount"])
                or not isinstance(factor["effect_on_metric"], str)
                or factor["effect_on_metric"] not in _METRIC_EFFECTS
            ):
                _invalid_snapshot("因素归因结构非法")


_METRIC_EFFECTS = frozenset(
    {
        "increases_target_metric",
        "decreases_target_metric",
        "no_change_to_target_metric",
    }
)


def _validate_result_metadata(
    value: object, result_columns: list[str], row_count: int
) -> None:
    if (
        not _has_exact_fields(
            value, {"version", "status", "columns", "scope", "time_axis"}
        )
        or type(value["version"]) is not int
        or not isinstance(value["status"], str)
        or not isinstance(value["columns"], list)
        or len(value["columns"]) != len(result_columns)
    ):
        _invalid_snapshot("结果说明结构非法")
    known_version = value["version"] == 1
    if known_version and value["status"] not in {
        "complete",
        "partial",
        "unavailable",
    }:
        _invalid_snapshot("结果说明状态非法")
    for index, (column, result_name) in enumerate(
        zip(value["columns"], result_columns, strict=True)
    ):
        if not _has_exact_fields(
            column,
            {
                "index",
                "name",
                "data_type",
                "role",
                "semantic_name",
                "definition",
                "unit",
                "format",
                "certified",
                "reason_code",
            },
        ):
            _invalid_snapshot("结果说明列结构非法")
        unit = column["unit"]
        if unit is not None and (
            not _has_exact_fields(unit, {"key", "label"})
            or not isinstance(unit["key"], str)
            or not isinstance(unit["label"], str)
        ):
            _invalid_snapshot("结果说明单位非法")
        if (
            type(column["index"]) is not int
            or column["index"] != index
            or column["name"] != result_name
            or not isinstance(column["data_type"], str)
            or not isinstance(column["role"], str)
            or not isinstance(column["name"], str)
            or not _optional_string(column["semantic_name"])
            or not _optional_string(column["definition"])
            or not isinstance(column["format"], str)
            or type(column["certified"]) is not bool
            or not _optional_string(column["reason_code"])
        ):
            _invalid_snapshot("结果说明列字段非法")
        if known_version and (
            column["data_type"]
            not in {"number", "string", "boolean", "date", "unknown"}
            or column["role"] not in {"metric", "dimension", "identifier", "unknown"}
            or column["format"] not in {"money", "count", "ratio", "number", "raw"}
        ):
            _invalid_snapshot("结果说明列枚举值非法")

    scope = value["scope"]
    if not _has_exact_fields(
        scope,
        {"status", "time", "time_status", "filters", "grouping", "warnings"},
    ):
        _invalid_snapshot("结果说明范围结构非法")
    if (
        not isinstance(scope["status"], str)
        or not isinstance(scope["time_status"], str)
        or not isinstance(scope["filters"], list)
        or not isinstance(scope["grouping"], list)
        or not _is_string_list(scope["warnings"])
    ):
        _invalid_snapshot("结果说明范围字段非法")
    if known_version and (
        scope["status"] not in {"complete", "partial", "unavailable"}
        or scope["time_status"] not in {"confirmed", "unbounded", "unknown"}
    ):
        _invalid_snapshot("结果说明范围枚举值非法")
    time = scope["time"]
    if time is not None and (
        not _has_exact_fields(time, {"start", "end_exclusive", "time_basis"})
        or not all(
            isinstance(time[key], str)
            for key in ("start", "end_exclusive", "time_basis")
        )
    ):
        _invalid_snapshot("结果说明时间范围非法")
    for item in scope["filters"]:
        if (
            not _has_exact_fields(item, {"label", "operator", "values"})
            or not isinstance(item["label"], str)
            or not isinstance(item["operator"], str)
            or not _is_string_list(item["values"])
            or not item["values"]
        ):
            _invalid_snapshot("结果说明筛选结构非法")
        if known_version and item["operator"] not in {"=", ">", ">=", "<", "<=", "IN"}:
            _invalid_snapshot("结果说明筛选操作符非法")
    for item in scope["grouping"]:
        indices = item.get("column_indices") if isinstance(item, dict) else None
        if (
            not _has_exact_fields(item, {"semantic_name", "kind", "column_indices"})
            or not isinstance(item["semantic_name"], str)
            or not isinstance(item["kind"], str)
            or not isinstance(indices, list)
            or not indices
            or any(
                type(index) is not int or not 0 <= index < len(result_columns)
                for index in indices
            )
            or len(set(indices)) != len(indices)
        ):
            _invalid_snapshot("结果说明分组结构非法")
        if known_version and item["kind"] not in {"time", "category"}:
            _invalid_snapshot("结果说明分组类型非法")

    axis = value["time_axis"]
    if axis is not None and (
        not _has_exact_fields(axis, {"granularity", "keys"})
        or not isinstance(axis["granularity"], str)
        or not _is_string_list(axis["keys"])
        or len(axis["keys"]) != row_count
    ):
        _invalid_snapshot("结果说明时间轴非法")
    if (
        known_version
        and axis is not None
        and axis["granularity"] not in {"day", "week", "month", "quarter", "year"}
    ):
        _invalid_snapshot("结果说明时间粒度非法")


def _has_exact_fields(
    value: object,
    required: set[str],
    optional: set[str] | None = None,
) -> bool:
    if not isinstance(value, dict):
        return False
    allowed = required | (optional or set())
    return required.issubset(value) and set(value).issubset(allowed)


def _is_nonempty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _optional_string(value: object) -> bool:
    return value is None or isinstance(value, str)


def _is_string_list(value: object) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def _valid_rows(value: object, columns: list[str], *, maximum: int) -> bool:
    return (
        isinstance(value, list)
        and len(value) <= maximum
        and all(
            isinstance(row, list)
            and len(row) == len(columns)
            and all(_is_json_scalar(cell) for cell in row)
            for row in value
        )
    )


def _is_json_scalar(value: object) -> bool:
    if value is None or type(value) in {str, int, bool}:
        return True
    return type(value) is float and math.isfinite(value)


def _is_decimal_text(value: object) -> bool:
    if not isinstance(value, str) or not value:
        return False
    try:
        return Decimal(value).is_finite()
    except (InvalidOperation, ValueError):
        return False


def _invalid_snapshot(message: str = "结果快照不可用") -> None:
    raise HistoryError("HISTORY_SNAPSHOT_UNAVAILABLE", message)
