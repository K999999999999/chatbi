"""历史成功状态必须在SQL生成前具备完整业务条件。"""

import pytest

from src.online_query.query_understanding import (
    SemanticQueryStructureError,
    candidate_from_payload,
    validate_candidate,
)


def ranked_payload():
    return {
        "query_type": "metric_analysis",
        "subjects": [],
        "metrics": ["人民币净销售额"],
        "dimensions": ["产品"],
        "time": None,
        "filters": [],
        "conditions": {
            "order_by": [
                {
                    "target_kind": "metric",
                    "target": "人民币净销售额",
                    "direction": "desc",
                    "nulls": "first",
                }
            ],
            "row_limit": 10,
            "aggregate_filters": [],
            "selection": None,
        },
    }


def test_history_keeps_business_ranking_in_validated_state():
    candidate = candidate_from_payload(ranked_payload(), require_restorable=True)
    state = validate_candidate(candidate, original_question="按销售额降序前10产品")
    assert state.restoration_conditions.row_limit == 10
    assert state.restoration_conditions.order_by[0].target == "人民币净销售额"
    assert state.restoration_conditions.order_by[0].direction == "desc"


def test_legacy_candidate_contract_still_rejects_history_fields():
    with pytest.raises(SemanticQueryStructureError):
        candidate_from_payload(ranked_payload())


@pytest.mark.parametrize("invalid_limit", [True, 0, -1, 2.5, "10"])
def test_history_rejects_invalid_business_row_limit(invalid_limit):
    payload = ranked_payload()
    payload["conditions"]["row_limit"] = invalid_limit
    with pytest.raises(SemanticQueryStructureError):
        candidate_from_payload(payload, require_restorable=True)


def test_history_cannot_omit_complete_conditions():
    payload = ranked_payload()
    del payload["conditions"]
    with pytest.raises(SemanticQueryStructureError):
        candidate_from_payload(payload, require_restorable=True)
