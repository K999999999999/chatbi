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
