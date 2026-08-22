"""POC 命令行入口。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.executor import QueryExecutionError, QueryExecutor
from src.llm_client import OpenAICompatibleLlmClient, SqlGenerationError
from src.pipeline import PocQueryPipeline, PocResponse
from src.prompt_builder import PromptBuilder
from src.query_parser import QueryParser
from src.semantic import MetricCatalog
from src.sql_guard import SqlGuard
from src.structure import StructureCatalog


ROOT = Path(__file__).resolve().parents[1]
STRUCTURE_DIR = ROOT / "src" / "structure" / "generated"
METRICS_FILE = ROOT / "src" / "semantic" / "metrics.json"


def build_pipeline() -> PocQueryPipeline:
    structure = StructureCatalog.from_directory(STRUCTURE_DIR)
    metrics = MetricCatalog.from_file(METRICS_FILE)
    metrics.validate_against_structure(structure)
    prompt_builder = PromptBuilder(structure, metrics)
    llm_client = OpenAICompatibleLlmClient.from_env_file(ROOT / ".env")
    executor = QueryExecutor.from_env(ROOT / ".env")
    return PocQueryPipeline(
        query_parser=QueryParser(),
        prompt_builder=prompt_builder,
        llm_client=llm_client,
        sql_guard=SqlGuard(structure),
        executor=executor,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="ChatBI mart_sales Text2SQL POC")
    parser.add_argument("question", nargs="+", help="自然语言查询问题")
    args = parser.parse_args()
    question = " ".join(args.question)
    try:
        response = build_pipeline().run(question)
    except (QueryExecutionError, SqlGenerationError, ValueError) as exc:
        response = PocResponse(
            success=False,
            question=question,
            error_code="configuration_error",
            error=str(exc),
        )
    print(json.dumps(response.to_dict(), ensure_ascii=False, indent=2, default=str))
    return 0 if response.success else 1


if __name__ == "__main__":
    raise SystemExit(main())
