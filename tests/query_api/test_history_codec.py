"""快照的公开白名单、大小边界与不可执行私有状态。"""

import json
from decimal import Decimal

import pytest

from src.online_query.contracts import QuerySuccess
from src.query_api.history_codec import (
    MAX_SNAPSHOT_BYTES,
    encode_snapshot,
    public_snapshot,
)
from src.query_api.history_contracts import HistoryError
from src.query_api.query_response import query_payload
from tests.query_api.history_fixtures import query_state


def snapshot_result():
    return query_payload(
        QuerySuccess(
            "r",
            "SELECT 1",
            ("n",),
            ((Decimal("12345678901234567890.123456"),),),
            1,
            False,
        )
    )


def _unavailable_metadata(columns, rows):
    return {
        "version": 1,
        "status": "unavailable",
        "columns": [
            {
                "index": index,
                "name": name,
                "data_type": "unknown",
                "role": "unknown",
                "semantic_name": None,
                "definition": None,
                "unit": None,
                "format": "raw",
                "certified": False,
                "reason_code": "SEMANTICS_UNCONFIRMED",
            }
            for index, name in enumerate(columns)
        ],
        "scope": {
            "status": "unavailable",
            "time": None,
            "time_status": "unknown",
            "filters": [],
            "grouping": [],
            "warnings": ["SCOPE_UNCONFIRMED"],
        },
        "time_axis": None,
    }


def analysis_result(*, include_metadata=True):
    task = {
        "task_id": "trend",
        "status": "completed",
        "columns": ["product", "notes"],
        "rows": [["A", "ordinary sql and connection_info text"]],
        "row_count": 1,
        "truncated": False,
        "error": None,
    }
    if include_metadata:
        task["result_metadata"] = _unavailable_metadata(task["columns"], task["rows"])
    return {
        "request_id": "analysis-request",
        "analysis_run_id": "analysis-run",
        "mode": "analysis",
        "report": {
            "title": "毛利变化",
            "executive_summary": "毛利增加。",
            "key_findings": ["毛利增加。"],
            "trend_judgment": "毛利增加。",
            "root_causes": [],
            "action_suggestions": [],
            "evidence_task_ids": ["trend"],
            "incomplete_tasks": [],
            "attribution": {
                "metric_name": "人民币毛利",
                "comparison_period": "2025年",
                "current_period": "2026年",
                "comparison_value": "10.00",
                "current_value": "12.00",
                "total_change": "2.00",
                "direction": "increase",
                "products": [
                    {
                        "product_name": "A",
                        "change": "2.00",
                        "effect_on_metric": "increases_target_metric",
                        "classification": "continuing",
                        "factors": [
                            {
                                "name": "实际成交单价",
                                "amount": "2.00",
                                "effect_on_metric": "increases_target_metric",
                            }
                        ],
                    }
                ],
                "omitted_product_count": 0,
                "reconciliation_passed": True,
            },
        },
        "task_results": [task],
    }


def analysis_envelope(result=None):
    return {
        "version": 1,
        "kind": "analysis",
        "original_question": "毛利为什么变化？",
        "result": analysis_result() if result is None else result,
    }


def test_snapshot_preserves_decimal_json_value_and_hides_private_state():
    result = snapshot_result()
    snapshot = encode_snapshot(
        "query", result, query_state=query_state(), source_question="销售额前10个产品"
    )
    assert public_snapshot(snapshot)["rows"] == [["12345678901234567890.123456"]]
    assert "query_state" not in public_snapshot(snapshot)
    assert "source_question" not in public_snapshot(snapshot)


def test_exact_5mib_boundary_is_not_silently_truncated():
    result = snapshot_result()
    result["sql"] = ""
    snapshot = encode_snapshot(
        "query", result, query_state=query_state(), source_question="销售额"
    )
    overhead = len(
        json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")).encode()
    )
    result["sql"] = "x" * (MAX_SNAPSHOT_BYTES - overhead)
    assert (
        len(
            encode_snapshot(
                "query", result, query_state=query_state(), source_question="销售额"
            )["result"]["sql"]
        )
        == MAX_SNAPSHOT_BYTES - overhead
    )
    result["sql"] += "x"
    with pytest.raises(HistoryError, match="超过5 MiB"):
        encode_snapshot(
            "query", result, query_state=query_state(), source_question="销售额"
        )


def test_unknown_public_fields_cannot_expose_internal_values():
    result = snapshot_result()
    result["auth_context"] = {"private": "must not appear"}
    with pytest.raises(HistoryError):
        encode_snapshot(
            "query", result, query_state=query_state(), source_question="销售额"
        )


def test_query_snapshot_requires_source_question_for_condition_requery():
    with pytest.raises(HistoryError, match="来源问题不可用"):
        encode_snapshot("query", snapshot_result(), query_state=query_state())


def test_legacy_v1_query_snapshot_without_source_question_remains_displayable():
    snapshot = encode_snapshot(
        "query", snapshot_result(), query_state=query_state(), source_question="销售额"
    )
    del snapshot["source_question"]

    assert public_snapshot(snapshot)["rows"] == [["12345678901234567890.123456"]]


def test_unknown_snapshot_version_is_never_read_as_current():
    with pytest.raises(HistoryError):
        public_snapshot({"version": 2, "kind": "query", "result": snapshot_result()})


@pytest.mark.parametrize(
    ("path", "key", "canary"),
    [
        (("result", "task_results", 0), "sql", "NESTED_SQL_CANARY"),
        (
            ("result", "report", "attribution", "products", 0),
            "connection_info",
            "NESTED_CONNECTION_CANARY",
        ),
        (
            ("result", "task_results", 0, "result_metadata", "columns", 0),
            "secret",
            "NESTED_SECRET_CANARY",
        ),
    ],
)
def test_analysis_snapshots_reject_nested_internal_fields_without_echoing_payload(
    path, key, canary
):
    envelope = analysis_envelope()
    target = envelope
    for part in path:
        target = target[part]
    target[key] = canary

    with pytest.raises(HistoryError) as failure:
        public_snapshot(envelope)

    assert failure.value.code == "HISTORY_SNAPSHOT_UNAVAILABLE"
    assert canary not in str(failure.value)

    with pytest.raises(HistoryError) as encode_failure:
        encode_snapshot("analysis", envelope["result"], original_question="毛利")

    assert encode_failure.value.code == "HISTORY_SNAPSHOT_UNAVAILABLE"
    assert canary not in str(encode_failure.value)


def test_legal_legacy_analysis_snapshot_without_optional_metadata_remains_readable():
    result = analysis_result(include_metadata=False)

    assert public_snapshot(analysis_envelope(result)) == result


def test_valid_analysis_metadata_and_ordinary_sql_text_are_preserved():
    result = analysis_result()

    assert public_snapshot(analysis_envelope(result)) == result
    assert result["task_results"][0]["rows"][0][1] == (
        "ordinary sql and connection_info text"
    )


@pytest.mark.parametrize("classification", ["new", "discontinued"])
def test_legacy_analysis_product_classification_remains_readable(classification):
    result = analysis_result()
    result["report"]["attribution"]["products"][0]["classification"] = classification

    assert public_snapshot(analysis_envelope(result)) == result


def test_unknown_metadata_version_preserves_supported_table_snapshot_shape():
    result = analysis_result()
    result["task_results"][0]["result_metadata"]["version"] = 2
    result["task_results"][0]["result_metadata"]["status"] = "future_status"

    assert public_snapshot(analysis_envelope(result)) == result


def test_query_sql_and_cell_text_are_not_filtered_as_nested_field_names():
    result = snapshot_result()
    result["sql"] = "SELECT 1 -- connection_info is a query comment"
    result["rows"] = [["ordinary sql and connection_info text"]]

    snapshot = encode_snapshot(
        "query", result, query_state=query_state(), source_question="销售额"
    )

    assert public_snapshot(snapshot) == result


@pytest.mark.parametrize("kind", [[], {}])
def test_unknown_unhashable_snapshot_kind_returns_controlled_error(kind):
    with pytest.raises(HistoryError) as failure:
        public_snapshot({"version": 1, "kind": kind, "result": {}})

    assert failure.value.code == "HISTORY_SNAPSHOT_UNAVAILABLE"
