"""POC 问题到查询结果的同步编排链路。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.poc.context import ContextBuilder
from src.poc.executor import QueryExecutionError, QueryExecutor, QueryResult
from src.poc.sql_generator import SqlGenerationError, SqlGenerator
from src.poc.sql_guard import SqlGuard, SqlValidationError


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
    """question -> context -> candidate SQL -> Guard -> read-only result。"""

    def __init__(
        self,
        context_builder: ContextBuilder,
        sql_generator: SqlGenerator,
        sql_guard: SqlGuard,
        executor: QueryExecutor,
    ) -> None:
        self.context_builder = context_builder
        self.sql_generator = sql_generator
        self.sql_guard = sql_guard
        self.executor = executor

    def run(self, question: str) -> PocResponse:
        normalized = question.strip()
        if not normalized:
            return PocResponse(
                success=False,
                question=question,
                error_code="empty_question",
                error="用户问题不能为空",
            )

        try:
            context = self.context_builder.build(normalized)
            generated_sql = self.sql_generator.generate(context)
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
                sql=generated_sql if "generated_sql" in locals() else None,
                error_code="query_execution_failed",
                error=str(exc),
            )

        return PocResponse(
            success=True,
            question=normalized,
            metric_codes=(context.metric.metric_code,),
            sql=validated.sql,
            columns=result.columns,
            rows=result.rows,
        )
