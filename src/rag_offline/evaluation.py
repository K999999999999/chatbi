"""RAG Offline Retrieval Evaluation（离线检索评测）。"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from .documents import COLUMN_COLLECTION, METRIC_COLLECTION, TABLE_COLLECTION
from .embedding import EmbeddingProvider
from .qdrant_store import SearchHit
from .sources import Facts


class RetrievalEvaluationError(RuntimeError):
    """离线检索评测配置或执行失败。"""


class RetrievalSearchStore(Protocol):
    """评测所需的最小检索接口。"""

    def search(
        self,
        collection_name: str,
        query: Any,
        *,
        limit: int = 5,
        filter_payload: Mapping[str, Any] | None = None,
    ) -> tuple[SearchHit, ...]:
        """按指定逻辑集合检索。"""


@dataclass(frozen=True, slots=True)
class RetrievalCase:
    """一个固定的离线检索问题和预期文档。"""

    case_id: str
    collection: str
    query: str
    expected_document_ids: tuple[str, ...]
    filter_payload: Mapping[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class RetrievalCaseResult:
    """单个评测案例结果。"""

    case_id: str
    passed: bool
    expected_document_ids: tuple[str, ...]
    actual_document_ids: tuple[str, ...]
    missing_document_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RetrievalEvaluationSummary:
    """评测汇总，不混同于软件测试或业务验收。"""

    total_cases: int
    passed_cases: int
    case_results: tuple[RetrievalCaseResult, ...]

    @property
    def accuracy(self) -> float:
        return self.passed_cases / self.total_cases if self.total_cases else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_cases": self.total_cases,
            "passed_cases": self.passed_cases,
            "accuracy": self.accuracy,
            "cases": [
                {
                    "case_id": result.case_id,
                    "passed": result.passed,
                    "expected_document_ids": list(result.expected_document_ids),
                    "actual_document_ids": list(result.actual_document_ids),
                    "missing_document_ids": list(result.missing_document_ids),
                }
                for result in self.case_results
            ],
        }


def evaluate_retrieval(
    embedding: EmbeddingProvider,
    store: RetrievalSearchStore,
    collection_names: Mapping[str, str],
    cases: Sequence[RetrievalCase],
    *,
    top_k: int = 5,
) -> RetrievalEvaluationSummary:
    """按案例指定的逻辑集合检索，并要求所有预期文档进入 top-k。"""

    if top_k <= 0:
        raise RetrievalEvaluationError("top_k 必须为正数")
    results: list[RetrievalCaseResult] = []
    for case in cases:
        if case.collection not in {
            TABLE_COLLECTION,
            COLUMN_COLLECTION,
            METRIC_COLLECTION,
        }:
            raise RetrievalEvaluationError(
                f"案例 {case.case_id} 使用了未知逻辑集合：{case.collection}"
            )
        collection_name = collection_names.get(case.collection)
        if not isinstance(collection_name, str) or not collection_name:
            raise RetrievalEvaluationError(
                f"案例 {case.case_id} 缺少 {case.collection} 物理集合"
            )
        if not case.query.strip() or not case.expected_document_ids:
            raise RetrievalEvaluationError(f"案例 {case.case_id} 契约不完整")

        query_embedding = embedding.embed_query(case.query)
        hits = store.search(
            collection_name,
            query_embedding,
            limit=top_k,
            filter_payload=case.filter_payload,
        )
        actual = tuple(hit.document_id for hit in hits)
        missing = tuple(
            document_id
            for document_id in case.expected_document_ids
            if document_id not in actual
        )
        results.append(
            RetrievalCaseResult(
                case_id=case.case_id,
                passed=not missing,
                expected_document_ids=case.expected_document_ids,
                actual_document_ids=actual,
                missing_document_ids=missing,
            )
        )
    passed = sum(result.passed for result in results)
    return RetrievalEvaluationSummary(
        total_cases=len(results),
        passed_cases=passed,
        case_results=tuple(results),
    )


def default_retrieval_cases(facts: Facts) -> tuple[RetrievalCase, ...]:
    """从当前权威事实生成固定的 V1 语义检索评测问题。"""

    sales_table = _find_table(facts, "fct_sales_order_line")
    date_table = _find_table(facts, "dim_date")
    status_column = _find_column(facts, "fct_sales_order_line", "order_status")
    product_line = _find_column(facts, "dim_product", "product_line")
    gross_margin = _find_metric(facts, "毛利率")

    return (
        RetrievalCase(
            case_id="table-sales-order-line",
            collection=TABLE_COLLECTION,
            query="销售订单明细中的订单、客户、产品、区域和金额交易事实",
            expected_document_ids=(f"table:{sales_table}",),
        ),
        RetrievalCase(
            case_id="table-date-dimension",
            collection=TABLE_COLLECTION,
            query="按自然日、年、季度和月份筛选完成日期",
            expected_document_ids=(f"table:{date_table}",),
        ),
        RetrievalCase(
            case_id="column-order-status-values",
            collection=COLUMN_COLLECTION,
            query="订单状态，例如 completed、cancelled、pending",
            expected_document_ids=(f"column:{status_column}",),
            filter_payload={
                "schema_name": "mart_sales",
                "table_name": "fct_sales_order_line",
            },
        ),
        RetrievalCase(
            case_id="column-product-line-values",
            collection=COLUMN_COLLECTION,
            query="产品线，例如储能系统和动力电池",
            expected_document_ids=(f"column:{product_line}",),
            filter_payload={
                "schema_name": "mart_sales",
                "table_name": "dim_product",
            },
        ),
        RetrievalCase(
            case_id="metric-gross-margin",
            collection=METRIC_COLLECTION,
            query="人民币毛利率、毛利润和销售额为零时的处理",
            expected_document_ids=(
                f"metric:{gross_margin}",
                "metric:人民币毛利",
                "metric:人民币净销售额",
            ),
        ),
    )


def _find_table(facts: Facts, table_name: str) -> str:
    for table in facts.tables:
        if table["table_name"] == table_name:
            return f"{table['schema_name']}.{table['table_name']}"
    raise RetrievalEvaluationError(f"事实源缺少表：{table_name}")


def _find_column(facts: Facts, table_name: str, column_name: str) -> str:
    for column in facts.columns:
        if column["table_name"] == table_name and column["column_name"] == column_name:
            return (
                f"{column['schema_name']}.{column['table_name']}."
                f"{column['column_name']}"
            )
    raise RetrievalEvaluationError(f"事实源缺少字段：{table_name}.{column_name}")


def _find_metric(facts: Facts, metric_name: str) -> str:
    for metric in facts.metrics:
        if metric["name"] == metric_name:
            return metric["name"]
    raise RetrievalEvaluationError(f"事实源缺少指标：{metric_name}")
