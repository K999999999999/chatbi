"""DDD-T1 Domain / Application Contract（契约）测试。"""

import ast
import unittest
from pathlib import Path

from src.online_query.application.contracts import (
    CollectionKind,
    ContextSource,
    PublishedRetrievalSnapshot,
    RawRetrievalHit,
    SanitizedTablePayload,
)
from src.online_query.application.ports import (
    OpaqueQueryVector,
    RetrievalAssetPort,
)
from src.online_query.contracts import (
    MetricHit,
    QueryContext,
    RetrievalEvidence,
    TableHit,
)
from src.online_query.domain.models import (
    EmbeddingFingerprint,
    FormulaShape,
    FormulaStructure,
    MetricDefinition,
    MetricMention,
    MetricPlan,
    MetricPlanStatus,
    OpaqueSnapshotIdentity,
    RelationshipGraphFacts,
    RequestShape,
    SnapshotBinding,
    SnapshotBoundMetricDefinition,
    SnapshotResourceCatalog,
    TableRef,
    TimeFieldRef,
    ZeroDivisionGuard,
)


class _FakeVector:
    """测试用向量，不暴露给 Application Contract。"""


class _FakeAssetPort:
    def __init__(self, snapshot: PublishedRetrievalSnapshot) -> None:
        self.snapshot = snapshot
        self.search_calls: list[CollectionKind] = []

    def load_snapshot(self) -> PublishedRetrievalSnapshot:
        return self.snapshot

    def embed(
        self,
        snapshot: PublishedRetrievalSnapshot,
        text: str,
    ) -> OpaqueQueryVector:
        assert snapshot is self.snapshot
        assert text
        return _FakeVector()

    def search(
        self,
        snapshot: PublishedRetrievalSnapshot,
        collection_kind: CollectionKind,
        vector: OpaqueQueryVector,
        limit: int,
        table_filter: frozenset[TableRef] | None = None,
    ) -> tuple[RawRetrievalHit, ...]:
        assert snapshot is self.snapshot
        assert isinstance(vector, _FakeVector)
        assert limit > 0
        assert table_filter is None or isinstance(table_filter, frozenset)
        self.search_calls.append(collection_kind)
        return ()


class DddT1ContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self.identity = OpaqueSnapshotIdentity()
        self.version = "build-2026-09-14"
        table = TableRef("public", "orders")
        formula = FormulaStructure(
            shape=FormulaShape.AGGREGATE,
            aggregates=(),
            referenced_columns=(),
            zero_division_guard=ZeroDivisionGuard.NONE,
            canonical_expression="COUNT(*)",
        )
        definition = MetricDefinition(
            asset_version=self.version,
            document_id="metric:order_count",
            metric_name="order_count",
            aliases=("订单数",),
            semantic_text="订单数量",
            data_source=table,
            formula=formula,
            time_field=TimeFieldRef(table, "created_at", table, "created_at"),
            filters=(),
            depends_on=(),
        )
        binding = SnapshotBinding(self.identity, self.version)
        self.bound_definition = SnapshotBoundMetricDefinition(binding, definition)
        self.snapshot = PublishedRetrievalSnapshot(
            identity=self.identity,
            asset_version=self.version,
            available_collection_kinds=frozenset(CollectionKind),
            resource_catalog=SnapshotResourceCatalog(tables=(), columns=()),
            metric_definitions=(self.bound_definition,),
            relationship_graph=RelationshipGraphFacts(),
            embedding_fingerprint=EmbeddingFingerprint("test-model", 1),
            adapter_private_bindings=object(),
        )

    def test_domain_value_invariants_and_same_snapshot_binding(self) -> None:
        with self.assertRaises(ValueError):
            TableRef("", "orders")
        with self.assertRaises(ValueError):
            SnapshotBinding(self.identity, "")

        mismatched_definition = MetricDefinition(
            asset_version="other-version",
            document_id="metric:order_count",
            metric_name="order_count",
            aliases=(),
            semantic_text="订单数量",
            data_source=TableRef("public", "orders"),
            formula=self.bound_definition.value.formula,
            time_field=self.bound_definition.value.time_field,
            filters=(),
            depends_on=(),
        )
        with self.assertRaises(ValueError):
            SnapshotBoundMetricDefinition(
                SnapshotBinding(self.identity, self.version),
                mismatched_definition,
            )

        plan = MetricPlan(
            snapshot_identity=self.identity,
            asset_version=self.version,
            request_shape=RequestShape.BASELINE,
            ordered_metric_definitions=(self.bound_definition,),
            raw_mentions=(),
            ordered_mentions=(
                MetricMention("订单数", 0, 3, "metric:order_count", "order_count"),
            ),
            status=MetricPlanStatus.SUCCESS,
        )
        self.assertEqual(plan.asset_version, self.version)
        self.assertIs(plan.snapshot_identity, self.identity)

        with self.assertRaises(ValueError):
            MetricPlan(
                snapshot_identity=OpaqueSnapshotIdentity(),
                asset_version=self.version,
                request_shape=RequestShape.BASELINE,
                ordered_metric_definitions=(self.bound_definition,),
                raw_mentions=(),
                ordered_mentions=(),
                status=MetricPlanStatus.SUCCESS,
            )

    def test_published_snapshot_uses_logical_collection_port(self) -> None:
        payload = SanitizedTablePayload(
            table_ref=TableRef("public", "orders"),
            display_name="订单",
            business_description="订单事实表",
        )
        hit = RawRetrievalHit(
            snapshot_identity=self.identity,
            asset_version=self.version,
            collection_kind=CollectionKind.TABLE,
            document_id="table:public.orders",
            rank=1,
            score=0.9,
            payload=payload,
            page_content="订单表",
        )
        self.assertEqual(hit.collection_kind, CollectionKind.TABLE)
        port = _FakeAssetPort(self.snapshot)
        self.assertIsInstance(port, RetrievalAssetPort)
        vector = port.embed(self.snapshot, "订单数量")
        self.assertIsInstance(vector, _FakeVector)
        self.assertEqual(port.search(self.snapshot, CollectionKind.TABLE, vector, 3), ())
        self.assertEqual(port.search_calls, [CollectionKind.TABLE])

    def test_old_contract_constructors_and_new_optional_fields(self) -> None:
        old_table = TableHit(
            "doc-1", "public", "orders", "fact", 0.8, 1, {}, "订单表"
        )
        new_table = TableHit(
            "doc-1",
            "public",
            "orders",
            "fact",
            0.8,
            1,
            {},
            "订单表",
            self.identity,
            self.version,
        )
        metric = MetricHit(
            "metric:order_count",
            "order_count",
            0.9,
            1,
            {},
            "订单数",
            self.identity,
            self.version,
        )
        evidence = RetrievalEvidence(
            table_hits=(new_table,),
            metric_hits=(metric,),
            snapshot_identity=self.identity,
            asset_version=self.version,
        )
        context = QueryContext(
            "订单上下文",
            frozenset({"public.orders"}),
            {"public.orders": frozenset({"id"})},
            context_source=ContextSource.PUBLISHED,
            snapshot_identity=self.identity,
            asset_version=self.version,
            metric_definitions=(self.bound_definition.value,),
        )
        self.assertIsNone(old_table.snapshot_identity)
        self.assertEqual(evidence.table_hits[0].asset_version, self.version)
        self.assertEqual(context.context_source, ContextSource.PUBLISHED)

    def test_domain_and_application_sources_are_technology_neutral(self) -> None:
        source_root = Path(__file__).parents[2] / "src" / "online_query"
        forbidden_roots = {
            "qdrant",
            "langchain",
            "psycopg",
            "sqlglot",
            "opentelemetry",
            "pathlib",
            "os",
        }
        for relative in (Path("domain/models.py"), Path("application/ports.py")):
            tree = ast.parse((source_root / relative).read_text(encoding="utf-8"))
            imports: list[str] = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imports.extend(alias.name.lower() for alias in node.names)
                elif isinstance(node, ast.ImportFrom):
                    imports.append((node.module or "").lower())
            self.assertFalse(
                any(
                    any(
                        imported == term or imported.startswith(f"{term}.")
                        for term in forbidden_roots
                    )
                    for imported in imports
                ),
                msg=f"发现具体技术依赖: {relative} -> {imports}",
            )


if __name__ == "__main__":
    unittest.main()
