"""POC Semantic Layer（语义层）的指标目录。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from src.structure import StructureCatalog


class MetricCatalogError(ValueError):
    """指标目录不满足当前语义契约。"""


@dataclass(frozen=True)
class MetricDefinition:
    """一个可供 POC 查询的业务指标定义。"""

    metric_code: str
    metric_name: str
    metric_type: str
    aliases: tuple[str, ...]
    business_definition: str
    expression: str
    filters: tuple[str, ...]
    depends_on: tuple[str, ...]
    default_time_column_identity: str
    unit: str
    source_table: str | None = None
    source_columns: tuple[str, ...] = ()
    null_if: str | None = None
    grain: str = "sales_order_line"

    @classmethod
    def from_mapping(cls, raw: dict[str, Any]) -> "MetricDefinition":
        required = (
            "metric_code",
            "metric_name",
            "metric_type",
            "business_definition",
            "expression",
            "default_time_column_identity",
            "unit",
        )
        missing = [key for key in required if not raw.get(key)]
        if missing:
            raise MetricCatalogError(
                f"指标缺少必要字段：{', '.join(missing)}"
            )
        metric_type = str(raw["metric_type"])
        if metric_type not in {"atomic", "derived"}:
            raise MetricCatalogError(
                f"指标类型不支持：{raw['metric_code']}={metric_type}"
            )
        aliases = tuple(str(value) for value in raw.get("aliases", []))
        filters = tuple(str(value) for value in raw.get("filters", []))
        depends_on = tuple(str(value) for value in raw.get("depends_on", []))
        source_columns = tuple(str(value) for value in raw.get("source_columns", []))
        source_table = raw.get("source_table")
        if source_table is not None:
            source_table = str(source_table)
        return cls(
            metric_code=str(raw["metric_code"]),
            metric_name=str(raw["metric_name"]),
            metric_type=metric_type,
            aliases=aliases,
            business_definition=str(raw["business_definition"]),
            expression=str(raw["expression"]),
            filters=filters,
            depends_on=depends_on,
            default_time_column_identity=str(raw["default_time_column_identity"]),
            unit=str(raw["unit"]),
            source_table=source_table,
            source_columns=source_columns,
            null_if=(str(raw["null_if"]) if raw.get("null_if") else None),
            grain=str(raw.get("grain", "sales_order_line")),
        )

    @property
    def search_terms(self) -> tuple[str, ...]:
        return (self.metric_name, *self.aliases)

    def render_prompt(self) -> str:
        """渲染为给 SQL 生成器看的业务定义，不作为可执行 SQL。"""

        lines = [
            f"- metric_code: {self.metric_code}",
            f"  name: {self.metric_name}",
            f"  type: {self.metric_type}",
            f"  definition: {self.business_definition}",
            f"  semantic_expression: {self.expression}",
            f"  unit: {self.unit}",
            f"  grain: {self.grain}",
            f"  default_time: {self.default_time_column_identity}",
        ]
        if self.source_table:
            lines.append(f"  source_table: {self.source_table}")
        if self.source_columns:
            lines.append(f"  source_columns: {', '.join(self.source_columns)}")
        if self.filters:
            lines.append(f"  mandatory_filters: {'; '.join(self.filters)}")
        if self.depends_on:
            lines.append(f"  depends_on: {', '.join(self.depends_on)}")
        if self.null_if:
            lines.append(f"  null_if: {self.null_if}")
        return "\n".join(lines)


class MetricCatalog:
    """加载、校验和匹配 POC 指标。"""

    def __init__(self, metrics: Iterable[MetricDefinition]) -> None:
        values = tuple(metrics)
        if not values:
            raise MetricCatalogError("指标目录不能为空")
        codes = [metric.metric_code for metric in values]
        if len(codes) != len(set(codes)):
            raise MetricCatalogError("指标编码必须唯一")
        terms_by_code: dict[str, str] = {}
        for metric in values:
            for term in metric.search_terms:
                previous = terms_by_code.get(term)
                if previous is not None and previous != metric.metric_code:
                    raise MetricCatalogError(
                        f"指标名称或别名冲突：{term}（{previous} 与 {metric.metric_code}）"
                    )
                terms_by_code[term] = metric.metric_code
        self._metrics = values
        self._by_code = {metric.metric_code: metric for metric in values}

    @classmethod
    def from_file(cls, path: Path) -> "MetricCatalog":
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise MetricCatalogError(f"缺少指标文件：{path}") from exc
        except json.JSONDecodeError as exc:
            raise MetricCatalogError(f"指标文件不是有效 JSON：{path}") from exc
        if not isinstance(raw, list):
            raise MetricCatalogError("指标文件必须是数组")
        return cls(MetricDefinition.from_mapping(item) for item in raw)

    @property
    def metrics(self) -> tuple[MetricDefinition, ...]:
        return self._metrics

    def get(self, metric_code: str) -> MetricDefinition:
        try:
            return self._by_code[metric_code]
        except KeyError as exc:
            raise MetricCatalogError(f"未知指标：{metric_code}") from exc

    def validate_against_structure(self, structure: StructureCatalog) -> None:
        """确认原子指标引用的物理字段真实存在，依赖指标无环。"""

        for metric in self._metrics:
            if metric.metric_type == "atomic":
                if not metric.source_table:
                    raise MetricCatalogError(
                        f"原子指标缺少 source_table：{metric.metric_code}"
                    )
                if not structure.has_table(metric.source_table):
                    raise MetricCatalogError(
                        f"指标引用了未知表：{metric.metric_code}={metric.source_table}"
                    )
                for column in metric.source_columns:
                    if not structure.has_column(metric.source_table, column):
                        raise MetricCatalogError(
                            f"指标引用了未知字段：{metric.metric_code}="
                            f"{metric.source_table}.{column}"
                        )
            elif metric.source_table or metric.source_columns:
                raise MetricCatalogError(
                    f"派生指标不应直接声明 source_table/source_columns：{metric.metric_code}"
                )

            schema, table, column = metric.default_time_column_identity.split(".", 2)
            if schema != structure.schema_name or not structure.has_column(table, column):
                raise MetricCatalogError(
                    f"指标默认时间字段不存在：{metric.metric_code}="
                    f"{metric.default_time_column_identity}"
                )

            for dependency in metric.depends_on:
                if dependency not in self._by_code:
                    raise MetricCatalogError(
                        f"指标依赖不存在：{metric.metric_code}->{dependency}"
                    )

        self._assert_acyclic()

    def match_question(self, question: str) -> tuple[MetricDefinition, ...]:
        """按最长、不重叠的中文词组匹配指标，保持轻量且可解释。"""

        hits: list[tuple[int, int, MetricDefinition]] = []
        for metric in self._metrics:
            for term in metric.search_terms:
                if not term:
                    continue
                start = question.find(term)
                while start >= 0:
                    hits.append((start, start + len(term), metric))
                    start = question.find(term, start + 1)

        selected: list[tuple[int, int, MetricDefinition]] = []
        for hit in sorted(hits, key=lambda item: (-(item[1] - item[0]), item[0])):
            if any(_overlaps(hit, existing) for existing in selected):
                continue
            selected.append(hit)
        selected.sort(key=lambda item: item[0])

        unique: list[MetricDefinition] = []
        for _, _, metric in selected:
            if metric.metric_code not in {item.metric_code for item in unique}:
                unique.append(metric)
        return tuple(unique)

    def require_single(self, question: str) -> MetricDefinition:
        matched = self.match_question(question)
        if not matched:
            raise MetricCatalogError(
                "未识别到当前 POC 支持的指标；暂支持销售额、销量、销售成本、毛利和毛利率"
            )
        if len(matched) > 1:
            raise MetricCatalogError(
                "当前 POC 一次只支持一个指标，请拆分问题："
                + ", ".join(metric.metric_name for metric in matched)
            )
        return matched[0]

    def render_prompt(self, metrics: Iterable[MetricDefinition]) -> str:
        return "\n".join(metric.render_prompt() for metric in metrics)

    def _assert_acyclic(self) -> None:
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(code: str) -> None:
            if code in visiting:
                raise MetricCatalogError(f"指标依赖形成循环：{code}")
            if code in visited:
                return
            visiting.add(code)
            for dependency in self.get(code).depends_on:
                visit(dependency)
            visiting.remove(code)
            visited.add(code)

        for metric in self._metrics:
            visit(metric.metric_code)


def _overlaps(
    left: tuple[int, int, MetricDefinition],
    right: tuple[int, int, MetricDefinition],
) -> bool:
    return left[0] < right[1] and right[0] < left[1]
