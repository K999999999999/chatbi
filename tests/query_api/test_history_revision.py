"""完整条件只能由明确delta改变；短期失效不改变持久状态。"""

from dataclasses import replace
from types import SimpleNamespace

import pytest

from src.online_query.query_understanding import candidate_from_payload
from src.online_query.restoration_conditions import BusinessOrder, RestorationConditions
from src.query_api.history_codec import decode_query_state
from src.query_api.semantic_revision import (
    SemanticRevisionError,
    revise_history_semantic_query,
)
from tests.query_api.history_fixtures import query_state


def previous():
    state = decode_query_state(query_state())
    return replace(
        state,
        dimensions=("产品",),
        restoration_conditions=RestorationConditions(
            (
                BusinessOrder("metric", "人民币净销售额", "desc", "first"),
                BusinessOrder("dimension", "产品", "asc", "last"),
            ),
            10,
            (),
            None,
        ),
    )


def adapter(*, metrics=(), operations=None):
    candidate = candidate_from_payload(
        {
            "query_type": "metric_analysis",
            "subjects": [],
            "metrics": list(metrics),
            "dimensions": [],
            "time": None,
            "filters": [],
        }
    )
    changes = {
        name: ("keep", None)
        for name in ("order_by", "row_limit", "aggregate_filters", "selection")
    }
    changes.update(operations or {})
    return SimpleNamespace(
        understand_history_revision=lambda *args: (candidate, changes)
    )


def test_metric_replacement_keeps_topn_and_retargets_unique_metric_order():
    result = revise_history_semantic_query(
        previous(), "改成毛利", query_understanding=adapter(metrics=("人民币毛利",))
    )
    assert result.metrics == ("人民币毛利",)
    assert result.restoration_conditions.row_limit == 10
    assert result.restoration_conditions.order_by[0] == BusinessOrder(
        "metric", "人民币毛利", "desc", "first"
    )
    assert result.dimensions == ("产品",)


def test_limit_only_delta_changes_count_and_preserves_order():
    result = revise_history_semantic_query(
        previous(),
        "只看前20项",
        query_understanding=adapter(operations={"row_limit": ("set", 20)}),
    )
    assert result.restoration_conditions.row_limit == 20
    assert (
        result.restoration_conditions.order_by
        == previous().restoration_conditions.order_by
    )


def test_empty_delta_requires_clarification_without_executing():
    with pytest.raises(SemanticRevisionError):
        revise_history_semantic_query(previous(), "继续", query_understanding=adapter())


def test_rank_limit_cannot_use_display_order_as_implicit_business_order():
    unranked = replace(
        previous(),
        restoration_conditions=RestorationConditions((), None, (), None),
    )

    with pytest.raises(SemanticRevisionError, match="明确排序依据"):
        revise_history_semantic_query(
            unranked,
            "只看前10项",
            query_understanding=adapter(operations={"row_limit": ("set", 10)}),
        )


def test_clearing_rank_order_requires_clearing_limit_or_setting_an_order():
    with pytest.raises(SemanticRevisionError, match="取消排序时"):
        revise_history_semantic_query(
            previous(),
            "不再排序",
            query_understanding=adapter(operations={"order_by": ("clear", None)}),
        )
