"""验证 POC 对超出当前契约问题的受控失败行为。"""

from __future__ import annotations

import json
from pathlib import Path
import unittest

from src.poc.context import ContextBuilder
from src.poc.executor import QueryExecutor
from src.poc.pipeline import PocQueryPipeline
from src.poc.semantic import MetricCatalog
from src.poc.sql_generator import RuleBasedSqlGenerator
from src.poc.sql_guard import SqlGuard
from src.poc.structure import StructureCatalog


ROOT = Path(__file__).resolve().parents[2]


class AcceptanceBoundaryTest(unittest.TestCase):
    """边界问题不能生成或执行未经确认的查询。"""

    @classmethod
    def setUpClass(cls) -> None:
        structure = StructureCatalog.from_directory(
            ROOT / "src" / "poc" / "structure" / "generated"
        )
        metrics = MetricCatalog.from_file(
            ROOT / "src" / "poc" / "semantic" / "metrics.json"
        )
        metrics.validate_against_structure(structure)
        cls.pipeline = PocQueryPipeline(
            context_builder=ContextBuilder(structure, metrics),
            sql_generator=RuleBasedSqlGenerator(),
            sql_guard=SqlGuard(structure),
            executor=QueryExecutor.from_env(ROOT / ".env"),
        )
        cls.cases = json.loads(
            (ROOT / "tests" / "poc" / "fixtures" / "boundary_cases.json")
            .read_text(encoding="utf-8")
        )

    def test_boundary_cases_are_controlled_failures(self) -> None:
        failures: list[str] = []
        for case in self.cases:
            response = self.pipeline.run(case["question"])
            if response.success:
                failures.append(f"{case['id']}: unexpected success")
                continue
            if response.error_code != case["expected_error_code"]:
                failures.append(
                    f"{case['id']}: error_code={response.error_code!r}, "
                    f"expected={case['expected_error_code']!r}"
                )
            if response.sql is not None:
                failures.append(f"{case['id']}: rejected case returned SQL")
            if not response.error:
                failures.append(f"{case['id']}: rejected case has no error detail")
        self.assertFalse(
            failures,
            "Acceptance boundary failures: " + " | ".join(failures),
        )


if __name__ == "__main__":
    unittest.main()
