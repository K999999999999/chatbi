"""使用真实 LLM 和 mart_sales 数据验证 Execution Accuracy。"""

from __future__ import annotations

import json
import os
from pathlib import Path
import unittest

from src.poc.evaluation import results_equivalent
from src.poc.executor import QueryExecutor
from src.poc.llm_client import OpenAICompatibleLlmClient
from src.poc.pipeline import PocQueryPipeline
from src.poc.prompt_builder import PromptBuilder
from src.poc.query_parser import QueryParser
from src.poc.semantic import MetricCatalog
from src.poc.sql_guard import SqlGuard
from src.poc.structure import StructureCatalog


ROOT = Path(__file__).resolve().parents[2]


@unittest.skipUnless(
    os.getenv("RUN_REAL_LLM_ACCEPTANCE") == "1",
    "设置 RUN_REAL_LLM_ACCEPTANCE=1 后运行真实 LLM 评估",
)
class ExecutionAccuracyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.structure = StructureCatalog.from_directory(
            ROOT / "src" / "poc" / "structure" / "generated"
        )
        cls.metrics = MetricCatalog.from_file(
            ROOT / "src" / "poc" / "semantic" / "metrics.json"
        )
        cls.metrics.validate_against_structure(cls.structure)
        cls.executor = QueryExecutor.from_env(ROOT / ".env")
        cls.guard = SqlGuard(cls.structure)
        cls.pipeline = PocQueryPipeline(
            query_parser=QueryParser(),
            prompt_builder=PromptBuilder(cls.structure, cls.metrics),
            llm_client=OpenAICompatibleLlmClient.from_env_file(ROOT / ".env"),
            sql_guard=cls.guard,
            executor=cls.executor,
        )
        cls.cases = json.loads(
            (
                ROOT / "tests" / "poc" / "fixtures" / "execution_cases.json"
            ).read_text(encoding="utf-8")
        )

    def test_all_fixed_cases_match_expected_results(self) -> None:
        failures: list[str] = []
        for case in self.cases:
            expected = self.executor.execute(
                self.guard.validate(case["expected_sql"])
            )
            response = self.pipeline.run(case["question"])
            if not response.success:
                failures.append(f"{case['id']}: pipeline failed: {response.error}")
                continue
            actual = self.executor.execute(self.guard.validate(response.sql or ""))
            if not results_equivalent(expected, actual):
                failures.append(
                    f"{case['id']}: results differ; sql={response.sql}"
                )
        self.assertFalse(failures, "Execution Accuracy failures: " + " | ".join(failures))


if __name__ == "__main__":
    unittest.main()
