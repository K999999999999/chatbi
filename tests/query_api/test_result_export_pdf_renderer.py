from __future__ import annotations

import os
import unicodedata
from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader

from src.authorization.contracts import AuthContext, AuthorizationDecision
from src.query_api.app import create_app

pytestmark = pytest.mark.skipif(
    os.environ.get("CHATBI_EXPORT_PDF_RENDER_TEST") != "1",
    reason="requires the isolated Playwright Chromium renderer image",
)


class Provider:
    identity_provider = "test"

    def authenticate(self, request):
        return AuthContext(
            "local:1", "test", user_id=1, permissions=frozenset({"query.execute"})
        )


class Policy:
    def authorize(self, context, **kwargs):
        return AuthorizationDecision(True, "AUTHORIZED", "test")


class Audit:
    def emit(self, event):
        pass


def _analysis_snapshot(*, attribution: bool):
    columns = [f"经营指标第{i + 1}列" for i in range(8)]
    rows = [
        [
            f"2026-{i + 1:03d}",
            f"销售额-{i + 1:03d}",
            "北区",
            str(i * 100 + 25),
            "中文证据",
            "完整保留",
            "金额单位元",
            f"行{i + 1:03d}-末列",
        ]
        for i in range(100)
    ]
    rows[0][4] = "居民消费和民生数据"
    rows[0][7] = '<img src="file:///etc/passwd" onerror="throw 1">'
    metadata = {
        "columns": [
            {
                "index": index,
                "name": name,
                "semantic_name": name,
                "definition": f"{name} 的业务定义",
                "unit": {"label": "元"},
            }
            for index, name in enumerate(columns)
        ],
        "scope": {
            "status": "complete",
            "time_status": "confirmed",
            "time": {
                "start": "2026-01-01",
                "end_exclusive": "2027-01-01",
                "time_basis": "订单日期",
            },
            "filters": [{"label": "区域", "operator": "=", "values": ["北区"]}],
            "grouping": [{"semantic_name": "月份", "kind": "time"}],
            "warnings": [],
        },
    }
    report = {
        "title": "十月经营分析报告",
        "executive_summary": "本报告来自已保存的成功分析快照，销售额呈现稳定增长。",
        "key_findings": ["北区销售额增长。", "数据按订单日期逐月汇总。"],
        "trend_judgment": "观察期内销售额整体上升。",
        "root_causes": ["销量提升带来主要正向变化。"],
        "action_suggestions": ["继续观察后续月份表现。"],
        "evidence_task_ids": ["monthly-sales"],
        "incomplete_tasks": [
            {"task_id": "empty-task", "reasons": ["empty_result"]},
            {"task_id": "failed-task", "reasons": ["failed"]},
            {"task_id": "skipped-task", "reasons": ["skipped"]},
            {"task_id": "limited-task", "reasons": ["truncated"]},
        ],
    }
    if attribution:
        report["attribution"] = {
            "metric_name": "人民币净销售额",
            "comparison_period": "2026年9月",
            "current_period": "2026年10月",
            "comparison_value": "100.00",
            "current_value": "145.00",
            "total_change": "45.00",
            "direction": "increase",
            "products": [
                {
                    "product_name": f"归因产品{i}",
                    "change": str(20 - i * 7),
                    "classification": "continuing",
                    "effect_on_metric": "increases_target_metric"
                    if i < 2
                    else "decreases_target_metric",
                    "factors": [
                        {
                            "name": f"销量因素{i}",
                            "amount": str(24 - i * 7),
                            "effect_on_metric": "increases_target_metric",
                        },
                        {
                            "name": f"单价因素{i}",
                            "amount": "-4",
                            "effect_on_metric": "decreases_target_metric",
                        },
                    ],
                }
                for i in range(4)
            ],
            "omitted_product_count": 1,
            "reconciliation_passed": True,
        }
    return {
        "kind": "analysis",
        "title": "测试经营分析",
        "question": "分析2026年经营表现，完整保留引用证据",
        "result_time": "2026-10-06T10:00:00+00:00",
        "saved_time": None,
        "result": {
            "request_id": "internal-request-id-must-not-print",
            "analysis_run_id": "internal-analysis-id-must-not-print",
            "mode": "analysis",
            "report": report,
            "task_results": [
                {
                    "task_id": "monthly-sales",
                    "status": "completed",
                    "columns": columns,
                    "rows": rows,
                    "row_count": 100,
                    "truncated": False,
                    "error": None,
                    "result_metadata": metadata,
                },
                {
                    "task_id": "empty-task",
                    "status": "completed",
                    "columns": ["月份", "销售额"],
                    "rows": [],
                    "row_count": 0,
                    "truncated": False,
                    "error": None,
                },
                {
                    "task_id": "failed-task",
                    "status": "failed",
                    "columns": [],
                    "rows": [],
                    "row_count": 0,
                    "truncated": False,
                    "error": {
                        "code": "DATABASE_ERROR",
                        "message": "任务失败，保留公开说明",
                    },
                },
                {
                    "task_id": "skipped-task",
                    "status": "skipped",
                    "columns": [],
                    "rows": [],
                    "row_count": 0,
                    "truncated": False,
                    "error": {"code": "DEPENDENCY_FAILED", "message": "依赖任务未完成"},
                },
                {
                    "task_id": "limited-task",
                    "status": "completed",
                    "columns": ["商品"],
                    "rows": [["长单元格 " + "中文数据 " * 500]],
                    "row_count": 20,
                    "truncated": True,
                    "error": None,
                },
            ],
        },
    }


class AnalysisStore:
    def __init__(self):
        self.include_attribution = True

    def export_snapshot(self, owner, source_kind, source_id, turn_id):
        assert owner == 1
        assert source_kind == "saved_result"
        return _analysis_snapshot(attribution=self.include_attribution)


def _client(store):
    app = create_app(
        service=object(),
        identity_provider=Provider(),
        policy_store=Policy(),
        audit_sink=Audit(),
        history_store=store,
        history_runtime=object(),
    )
    return TestClient(app)


def test_real_pdf_download_extracts_cjk_complete_evidence_and_attribution(tmp_path):
    store = AnalysisStore()
    with _client(store) as client:
        response = client.post(
            "/api/v1/result-exports",
            json={
                "source": {
                    "kind": "saved_result",
                    "saved_result_id": "e53ba3b9-1f11-4024-90f9-a7f2713cd56b",
                },
                "format": "pdf",
            },
        )
        assert response.status_code == 200, response.text
        assert response.headers["content-type"] == "application/pdf"
        output = os.environ.get("CHATBI_TEST_PDF_PATH")
        if output:
            Path(output).write_bytes(response.content)
        reader = PdfReader(BytesIO(response.content))
        text = unicodedata.normalize(
            "NFKC", "\n".join(page.extract_text() or "" for page in reader.pages)
        )
        assert len(reader.pages) >= 4
        assert "十月经营分析报告" in text
        assert "原分析问题" in text and "2026-10-06T10:00:00+00:00" in text
        assert "销售额" in text and "订单日期" in text and "2027-01-01" in text
        assert "居民消费和民生数据" in text
        assert "产品变化贡献图" in text and "归因产品3" in text and "单价因素3" in text
        assert "第8列" in text and "行100-末列" in text
        assert "empty-task" in text and "月份" in text
        assert "file:///etc/passwd" in text
        assert (
            "任务失败" in text
            and "保留公开说明" in text
            and "查询任务结果已截断" in text
        )
        assert "internal-request-id-must-not-print" not in text
        assert "internal-analysis-id-must-not-print" not in text


def test_real_pdf_without_attribution_omits_attribution_section():
    store = AnalysisStore()
    store.include_attribution = False
    with _client(store) as client:
        response = client.post(
            "/api/v1/result-exports",
            json={
                "source": {
                    "kind": "saved_result",
                    "saved_result_id": "e53ba3b9-1f11-4024-90f9-a7f2713cd56b",
                },
                "format": "pdf",
            },
        )
    assert response.status_code == 200, response.text
    text = unicodedata.normalize(
        "NFKC",
        "\n".join(
            page.extract_text() or ""
            for page in PdfReader(BytesIO(response.content)).pages
        ),
    )
    assert "两期指标归因与产品因素" not in text
    assert "证据附录" in text
