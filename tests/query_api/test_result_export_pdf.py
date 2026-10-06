from __future__ import annotations

import copy

import pytest

from src.query_api.export_pdf import (
    ExportRenderFailure,
    _expected_coverage,
    _safe_document,
)


@pytest.fixture
def analysis_document():
    return {
        "kind": "analysis",
        "title": "十月经营分析",
        "question": "分析十月销售额变化",
        "result_time": "2026-10-06T10:00:00+00:00",
        "saved_time": None,
        "export_time": "2026-10-06T11:00:00+00:00",
        "result": {
            "request_id": "private-request-id",
            "sql": "must never be rendered",
            "prompt": "must never be rendered",
            "report": {
                "title": "十月经营分析",
                "executive_summary": "销售额有所增长。",
                "key_findings": ["北区增长"],
                "trend_judgment": "整体上升",
                "root_causes": [],
                "action_suggestions": ["继续观察"],
                "evidence_task_ids": ["current-sales"],
                "incomplete_tasks": [{"task_id": "failed-cost", "reasons": ["failed"]}],
                "internal_reason": "must never be rendered",
                "attribution": {
                    "metric_name": "人民币净销售额",
                    "comparison_period": "2026年9月",
                    "current_period": "2026年10月",
                    "comparison_value": "100.00",
                    "current_value": "125.00",
                    "total_change": "25.00",
                    "direction": "increase",
                    "products": [
                        {
                            "product_name": "茶饮",
                            "change": "25.00",
                            "effect_on_metric": "increases_target_metric",
                            "classification": "continuing",
                            "factors": [
                                {
                                    "name": "销量变化",
                                    "amount": "25.00",
                                    "effect_on_metric": "increases_target_metric",
                                }
                            ],
                        }
                    ],
                    "omitted_product_count": 2,
                    "reconciliation_passed": True,
                },
            },
            "task_results": [
                {
                    "task_id": "current-sales",
                    "status": "completed",
                    "columns": ["月份", "销售额"],
                    "rows": [["2026-10", "<script>不执行</script>"]],
                    "row_count": 1,
                    "truncated": False,
                    "error": None,
                    "result_metadata": {
                        "columns": [
                            {
                                "index": 1,
                                "name": "销售额",
                                "definition": "销售额定义",
                                "unit": {"label": "元"},
                            },
                        ],
                        "scope": {
                            "status": "complete",
                            "time_status": "confirmed",
                            "time": {
                                "start": "2026-10-01",
                                "end_exclusive": "2026-11-01",
                                "time_basis": "订单日期",
                                "secret": "must never be rendered",
                            },
                            "filters": [
                                {"label": "区域", "operator": "=", "values": ["北区"]}
                            ],
                            "grouping": [{"semantic_name": "月份", "kind": "time"}],
                            "warnings": [],
                            "sql": "must never be rendered",
                        },
                        "internal": "must never be rendered",
                    },
                },
                {
                    "task_id": "failed-cost",
                    "status": "failed",
                    "columns": [],
                    "rows": [],
                    "row_count": 0,
                    "truncated": False,
                    "error": {"code": "DATABASE_ERROR", "message": "成本任务失败"},
                },
            ],
        },
    }


def test_pdf_document_contains_only_public_report_and_task_fields(analysis_document):
    safe = _safe_document(analysis_document)

    assert set(safe) == {
        "kind",
        "question",
        "result_time",
        "saved_time",
        "export_time",
        "result",
    }
    assert "sql" not in safe["result"]
    assert "prompt" not in safe["result"]
    assert "internal_reason" not in safe["result"]["report"]
    assert safe["result"]["task_results"][0]["rows"][0][1] == "<script>不执行</script>"
    metadata = safe["result"]["task_results"][0]["result_metadata"]
    assert "sql" not in metadata and "internal" not in metadata
    assert "secret" not in metadata["scope"]["time"]
    assert safe["result"]["task_results"][1]["error"] == "成本任务失败"


def test_pdf_coverage_accounts_for_report_blocks_all_tables_and_factors(
    analysis_document,
):
    safe = _safe_document(analysis_document)
    coverage = _expected_coverage(safe, "a" * 64)

    assert coverage["block_ids"] == [
        "title",
        "executive-summary",
        "key-findings",
        "trend-judgment",
        "root-causes",
        "action-suggestions",
        "attribution",
        "evidence",
        "limitations",
    ]
    assert coverage["tasks"] == [
        {
            "task_id": "current-sales",
            "column_count": 2,
            "row_count": 1,
            "table_blocks": 1,
            "rendered_rows": 1,
        },
        {
            "task_id": "failed-cost",
            "column_count": 0,
            "row_count": 0,
            "table_blocks": 0,
            "rendered_rows": 0,
        },
    ]
    assert coverage["product_count"] == 1
    assert coverage["factor_count"] == 1
    assert coverage["attribution_chart"] is True


def test_pdf_document_fails_closed_on_incomplete_or_invalid_task_shape(
    analysis_document,
):
    invalid = copy.deepcopy(analysis_document)
    invalid["result"]["task_results"][0]["rows"][0].pop()

    with pytest.raises(ExportRenderFailure, match="行列数不一致"):
        _safe_document(invalid)
