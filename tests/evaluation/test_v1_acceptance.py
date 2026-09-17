"""Online Retrieval V1（在线检索 V1）确定性验收汇总。"""

import unittest
from pathlib import Path

from src.evaluation.evaluator import load_evaluation_cases
from src.evaluation.runner import CaseStatus, run_evaluation
from src.online_query.context import load_query_context
from src.online_query.contracts import QueryData, ValidatedSQL
from src.online_query.service import OnlineQueryService


class _SequentialSQLGenerator:
    def __init__(self, sqls: tuple[str, ...]) -> None:
        self._sqls = list(sqls)
        self.calls = 0

    def generate(self, prompt: str) -> str:
        del prompt
        if not self._sqls:
            raise AssertionError("评测案例数量超过标准 SQL 数量")
        self.calls += 1
        return self._sqls.pop(0)


class _EmptyResultExecutor:
    def __init__(self) -> None:
        self.calls: list[ValidatedSQL] = []

    def execute(self, sql: ValidatedSQL) -> QueryData:
        self.calls.append(sql)
        return QueryData(
            columns=("value",),
            rows=(),
            truncated=False,
        )


class V1AcceptanceTest(unittest.TestCase):
    def test_standard_corpus_passes_v1_guard_and_empty_result_contract(
        self,
    ) -> None:
        root = Path(__file__).resolve().parents[2]
        cases = load_evaluation_cases(root / "src" / "evaluation" / "eval_cases.json")
        context = load_query_context()
        generator = _SequentialSQLGenerator(tuple(case.expected_sql for case in cases))
        executor = _EmptyResultExecutor()
        service = OnlineQueryService(
            generator,
            executor,
            context_loader=lambda: context,
        )

        run = run_evaluation(cases, service, executor, context)

        self.assertEqual(run.summary.total_cases, 21)
        self.assertEqual(run.summary.valid_cases, 21)
        self.assertEqual(run.summary.passed, 21)
        self.assertEqual(run.summary.failed, 0)
        self.assertEqual(run.summary.invalid_cases, 0)
        self.assertEqual(run.summary.execution_accuracy, 1.0)
        self.assertTrue(all(case.status == CaseStatus.PASS for case in run.cases))
        self.assertEqual(generator.calls, 21)
        self.assertEqual(len(executor.calls), 42)
        self.assertEqual(len(context.join_constraints), 9)


if __name__ == "__main__":
    unittest.main()
