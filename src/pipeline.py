"""POC 问题到查询结果的同步编排链路。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.executor import QueryExecutionError, QueryExecutor, QueryResult
from src.llm_client import LlmClient, SqlGenerationError
from src.prompt_builder import PromptBuilder
from src.query_parser import QueryParser
from src.sql_guard import SqlGuard, SqlValidationError


@dataclass(frozen=True)
class PocResponse:
    """POC 对外返回的统一结构。"""

    success: bool
    question: str
    metric_codes: tuple[str, ...] = ()
    sql: str | None = None
    columns: tuple[str, ...] = ()
    rows: tuple[tuple[Any, ...], ...] = ()
    error_code: str | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "question": self.question,
            "metric_codes": list(self.metric_codes),
            "sql": self.sql,
            "columns": list(self.columns),
            "rows": [list(row) for row in self.rows],
            "error_code": self.error_code,
            "error": self.error,
        }


class PocQueryPipeline:
    """question -> parse -> Prompt -> LLM SQL -> Guard -> read-only result。"""

    def __init__(
        self,
        query_parser: QueryParser,
        prompt_builder: PromptBuilder,
        llm_client: LlmClient,
        sql_guard: SqlGuard,
        executor: QueryExecutor,
    ) -> None:
        self.query_parser = query_parser
        self.prompt_builder = prompt_builder
        self.llm_client = llm_client
        self.sql_guard = sql_guard
        self.executor = executor

    def run(self, question: str) -> PocResponse:
        normalized = question.strip()
        generated_sql: str | None = None

        try:
            parsed = self.query_parser.parse(normalized)
            context = self.prompt_builder.build(parsed.question)
            system_message, user_prompt = context.render_messages()
            generated_sql = self.llm_client.generate_sql(
                system_message,
                user_prompt,
            )
            validated = self.sql_guard.validate(generated_sql)
            result = self.executor.execute(validated)
        except (ValueError, SqlGenerationError, SqlValidationError) as exc:
            return PocResponse(
                success=False,
                question=normalized,
                error_code=getattr(exc, "code", "query_rejected"),
                error=str(exc),
            )
        except QueryExecutionError as exc:
            return PocResponse(
                success=False,
                question=normalized,
                sql=generated_sql,
                error_code="query_execution_failed",
                error=str(exc),
            )

        return PocResponse(
            success=True,
            question=normalized,
            metric_codes=context.metric_codes,
            sql=validated.sql,
            columns=result.columns,
            rows=result.rows,
        )
