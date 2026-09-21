"""Business Analysis 报告和 Summary LLM 测试。"""

import unittest

from src.business_analysis.execution import TaskError, TaskResult, TaskStatus
from src.business_analysis.reporting import (
    AnalysisReportError,
    BusinessAnalysisReport,
    LangChainAnalysisSummarizer,
)


class ReportingTest(unittest.TestCase):
    def test_summary_returns_human_readable_report_with_completed_evidence(self) -> None:
        model = _FakeModel(
            {
                "title": "销售额趋势分析",
                "executive_summary": "销售额在观察期内下降。",
                "key_findings": ["整体销售额下降"],
                "trend_judgment": "呈下降趋势",
                "root_causes": ["华东区域贡献下降"],
                "action_suggestions": ["进一步检查华东区域产品结构"],
                "evidence_task_ids": ["trend"],
                "incomplete_tasks": [],
            }
        )

        report = LangChainAnalysisSummarizer(model).summarize(
            "最近三个月销售额为什么下降",
            (_result("trend", rows=(("2026-09", 90),)),),
        )

        self.assertIsInstance(report, BusinessAnalysisReport)
        self.assertEqual(report.title, "销售额趋势分析")
        self.assertEqual(report.evidence_task_ids, ("trend",))
        self.assertEqual(report.incomplete_tasks, ())
        self.assertNotIn("SELECT", model.prompt.upper())
        self.assertIn('"rows"', model.prompt)

    def test_evidence_must_reference_completed_task(self) -> None:
        model = _FakeModel(_payload(evidence_task_ids=["failed"]))

        with self.assertRaises(AnalysisReportError) as raised:
            LangChainAnalysisSummarizer(model).summarize(
                "分析销售额",
                (
                    _result("completed", rows=((1,),)),
                    _result(
                        "failed",
                        status=TaskStatus.FAILED,
                        error=TaskError("DATABASE_ERROR", "查询失败"),
                    ),
                ),
            )

        self.assertEqual(raised.exception.code, "LLM_ERROR")
        self.assertEqual(raised.exception.reason, "EVIDENCE_TASK_INVALID")

    def test_all_tasks_incomplete_returns_cannot_answer_without_calling_model(self) -> None:
        model = _FakeModel(_payload())

        with self.assertRaises(AnalysisReportError) as raised:
            LangChainAnalysisSummarizer(model).summarize(
                "分析销售额",
                (_result("failed", status=TaskStatus.FAILED),),
            )

        self.assertEqual(raised.exception.code, "CANNOT_ANSWER")
        self.assertEqual(model.calls, 0)

    def test_program_computes_incomplete_tasks_for_empty_and_truncated_results(self) -> None:
        model = _FakeModel(_payload(incomplete_tasks=["empty", "truncated"]))

        report = LangChainAnalysisSummarizer(model).summarize(
            "分析销售额",
            (
                _result("empty"),
                _result("truncated", rows=((1,),), truncated=True),
                _result("good", rows=((2,),)),
            ),
        )

        self.assertEqual(
            [item.task_id for item in report.incomplete_tasks],
            ["empty", "truncated"],
        )
        self.assertEqual(report.incomplete_tasks[0].reasons, ("empty_result",))
        self.assertEqual(report.incomplete_tasks[1].reasons, ("truncated",))

    def test_provider_or_invalid_output_is_llm_error(self) -> None:
        model = _FakeModel("not-json")

        with self.assertRaises(AnalysisReportError) as raised:
            LangChainAnalysisSummarizer(model).summarize(
                "分析销售额",
                (_result("good", rows=((1,),)),),
            )

        self.assertEqual(raised.exception.code, "LLM_ERROR")
        self.assertEqual(raised.exception.reason, "RESPONSE_NOT_JSON")

    def test_missing_incomplete_tasks_is_rejected(self) -> None:
        payload = _payload()
        payload.pop("incomplete_tasks")
        model = _FakeModel(payload)

        with self.assertRaises(AnalysisReportError) as raised:
            LangChainAnalysisSummarizer(model).summarize(
                "分析销售额",
                (_result("good", rows=((1,),)),),
            )

        self.assertEqual(raised.exception.code, "LLM_ERROR")
        self.assertEqual(raised.exception.reason, "REPORT_FIELDS_INVALID")


class _FakeModel:
    def __init__(self, content: object) -> None:
        self.content = content
        self.calls = 0
        self.prompt = ""

    def invoke(self, prompt: str):
        self.calls += 1
        self.prompt = prompt
        return type("Response", (), {"content": _content(self.content)})()


def _content(value: object) -> str:
    if isinstance(value, str):
        return value
    import json

    return json.dumps(value, ensure_ascii=False)


def _payload(
    *,
    evidence_task_ids: list[str] | None = None,
    incomplete_tasks: list[str] | None = None,
) -> dict[str, object]:
    return {
        "title": "销售额分析",
        "executive_summary": "基于已完成查询结果生成。",
        "key_findings": ["发现一"],
        "trend_judgment": "趋势待结合数据判断",
        "root_causes": ["原因待进一步验证"],
        "action_suggestions": ["建议继续核查"],
        "evidence_task_ids": [] if evidence_task_ids is None else evidence_task_ids,
        "incomplete_tasks": [] if incomplete_tasks is None else incomplete_tasks,
    }


def _result(
    task_id: str,
    *,
    status: TaskStatus = TaskStatus.COMPLETED,
    rows: tuple[tuple[object, ...], ...] = (),
    truncated: bool = False,
    error: TaskError | None = None,
) -> TaskResult:
    return TaskResult(
        task_id=task_id,
        status=status,
        columns=("value",),
        rows=rows,
        row_count=len(rows),
        truncated=truncated,
        error=error,
    )


if __name__ == "__main__":
    unittest.main()
