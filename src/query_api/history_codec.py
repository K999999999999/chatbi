"""版本化公开快照及私有状态编码；不恢复凭证或任意Python对象。"""

import json
from dataclasses import replace
from datetime import datetime

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
                "HISTORY_SNAPSHOT_UNAVAILABLE", "完整恢复状态或来源问题不可用", 422
            )
        decode_query_state(query_state)
        envelope["query_state"] = query_state
        envelope["source_question"] = source_question.strip()
    elif kind == "analysis":
        if not original_question:
            raise HistoryError("HISTORY_SNAPSHOT_UNAVAILABLE", "原分析问题不可用", 422)
        envelope["original_question"] = original_question
    else:
        raise HistoryError("HISTORY_SNAPSHOT_UNAVAILABLE", "快照类型不可用", 422)
    try:
        encoded = json.dumps(
            envelope, ensure_ascii=False, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError):
        raise HistoryError(
            "HISTORY_SNAPSHOT_UNAVAILABLE", "快照无法安全编码", 422
        ) from None
    if len(encoded) > MAX_SNAPSHOT_BYTES:
        raise HistoryError(
            "HISTORY_SNAPSHOT_TOO_LARGE", "结果快照超过5 MiB，未保存本次成功状态", 413
        )
    return json.loads(encoded)


def public_snapshot(envelope: dict) -> dict:
    if (
        not isinstance(envelope, dict)
        or type(envelope.get("version")) is not int
        or envelope.get("version") != 1
        or envelope.get("kind") not in {"query", "analysis"}
        or not isinstance(envelope.get("result"), dict)
    ):
        raise HistoryError(
            "HISTORY_SNAPSHOT_UNAVAILABLE", "结果快照版本或内容不可用", 422
        )
    base_fields = {"version", "kind", "result"}
    if envelope["kind"] == "query":
        allowed_fields = {
            frozenset(base_fields | {"query_state"}),
            frozenset(base_fields | {"query_state", "source_question"}),
        }
    else:
        allowed_fields = {frozenset(base_fields | {"original_question"})}
    if frozenset(envelope) not in allowed_fields:
        raise HistoryError("HISTORY_SNAPSHOT_UNAVAILABLE", "快照来源字段非法", 422)
    if envelope["kind"] == "query":
        if not isinstance(envelope["query_state"], dict):
            raise HistoryError("HISTORY_SNAPSHOT_UNAVAILABLE", "查询恢复状态非法", 422)
        if "source_question" in envelope and (
            not isinstance(envelope["source_question"], str)
            or not envelope["source_question"].strip()
        ):
            raise HistoryError("HISTORY_SNAPSHOT_UNAVAILABLE", "查询来源问题非法", 422)
    elif (
        not isinstance(envelope["original_question"], str)
        or not envelope["original_question"].strip()
    ):
        raise HistoryError("HISTORY_SNAPSHOT_UNAVAILABLE", "分析来源问题非法", 422)
    _validate_public_result(envelope["kind"], envelope["result"])
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
            422,
        ) from None


def _validate_public_result(kind, result):
    required = (
        {"request_id", "sql", "columns", "rows", "row_count", "truncated"}
        if kind == "query"
        else {"request_id", "analysis_run_id", "mode", "report", "task_results"}
    )
    allowed = required | ({"result_metadata"} if kind == "query" else set())
    if (
        not isinstance(result, dict)
        or not required.issubset(result)
        or not set(result).issubset(allowed)
    ):
        raise HistoryError("HISTORY_SNAPSHOT_UNAVAILABLE", "快照公开字段非法", 422)
    if kind == "query":
        rows, columns = result["rows"], result["columns"]
        if (
            not isinstance(columns, list)
            or not all(isinstance(c, str) for c in columns)
            or not isinstance(rows, list)
            or len(rows) > 100
            or type(result["row_count"]) is not int
            or result["row_count"] != len(rows)
            or type(result["truncated"]) is not bool
            or not isinstance(result["sql"], str)
            or not isinstance(result["request_id"], str)
            or any(
                not isinstance(row, list)
                or len(row) != len(columns)
                or any(
                    cell is not None and type(cell) not in {str, int, float, bool}
                    for cell in row
                )
                for row in rows
            )
        ):
            raise HistoryError("HISTORY_SNAPSHOT_UNAVAILABLE", "快照表格内容非法", 422)
