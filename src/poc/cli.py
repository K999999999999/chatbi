"""POC 命令行入口。"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from src.poc.context import ContextBuilder
from src.poc.executor import QueryExecutor
from src.poc.pipeline import PocQueryPipeline
from src.poc.semantic import MetricCatalog
from src.poc.sql_generator import (
    HttpChatCompletionSqlGenerator,
    RuleBasedSqlGenerator,
)
from src.poc.sql_guard import SqlGuard
from src.poc.structure import StructureCatalog


ROOT = Path(__file__).resolve().parents[2]
STRUCTURE_DIR = ROOT / "src" / "poc" / "structure" / "generated"
METRICS_FILE = ROOT / "src" / "poc" / "semantic" / "metrics.json"


def build_pipeline() -> PocQueryPipeline:
    structure = StructureCatalog.from_directory(STRUCTURE_DIR)
    metrics = MetricCatalog.from_file(METRICS_FILE)
    metrics.validate_against_structure(structure)
    context_builder = ContextBuilder(structure, metrics)
    generator_name = os.getenv("POC_SQL_GENERATOR", "rule_based").lower()
    if generator_name == "rule_based":
        generator = RuleBasedSqlGenerator()
    elif generator_name == "http":
        generator = HttpChatCompletionSqlGenerator.from_environment()
    else:
        raise ValueError("POC_SQL_GENERATOR 只支持 rule_based 或 http")
    executor = QueryExecutor.from_env(ROOT / ".env")
    return PocQueryPipeline(
        context_builder=context_builder,
        sql_generator=generator,
        sql_guard=SqlGuard(structure),
        executor=executor,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="ChatBI mart_sales Text2SQL POC")
    parser.add_argument("question", nargs="+", help="自然语言查询问题")
    args = parser.parse_args()
    response = build_pipeline().run(" ".join(args.question))
    print(json.dumps(response.to_dict(), ensure_ascii=False, indent=2, default=str))
    return 0 if response.success else 1


if __name__ == "__main__":
    raise SystemExit(main())
