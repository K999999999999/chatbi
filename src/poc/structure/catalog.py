"""加载并渲染当前 POC 使用的 PostgreSQL 结构元数据。

结构元数据由 :mod:`scripts.metadata.export_schema` 从 ``mart_sales`` 自动导出。
本模块只负责读取导出结果，不在结构层补充指标定义或业务公式。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class StructureCatalogError(ValueError):
    """结构目录不满足 POC 结构契约。"""


@dataclass(frozen=True)
class StructureCatalog:
    """当前允许 SQL 生成器使用的物理结构目录。"""

    schema_name: str
    tables: tuple[dict[str, Any], ...]
    columns: tuple[dict[str, Any], ...]
    relationships: dict[str, Any]

    @classmethod
    def from_directory(cls, directory: Path) -> "StructureCatalog":
        """从导出目录读取三份稳定 JSON。"""

        tables = _read_json(directory / "tables.json")
        columns = _read_json(directory / "columns.json")
        relationships = _read_json(directory / "relationships.json")

        if not isinstance(tables, list):
            raise StructureCatalogError("tables.json 必须是数组")
        if not isinstance(columns, list):
            raise StructureCatalogError("columns.json 必须是数组")
        if not isinstance(relationships, dict):
            raise StructureCatalogError("relationships.json 必须是对象")

        schema_names = {
            str(item.get("schema_name"))
            for item in [*tables, *columns]
            if isinstance(item, dict)
        }
        if schema_names != {"mart_sales"}:
            raise StructureCatalogError(
                f"POC 只允许 mart_sales Schema，实际为：{sorted(schema_names)}"
            )

        table_names = {
            str(item.get("table_name"))
            for item in tables
            if isinstance(item, dict)
        }
        if not table_names:
            raise StructureCatalogError("结构目录没有任何表")

        column_keys: set[tuple[str, str]] = set()
        for column in columns:
            if not isinstance(column, dict):
                raise StructureCatalogError("columns.json 包含非对象元素")
            table_name = str(column.get("table_name"))
            column_name = str(column.get("column_name"))
            if table_name not in table_names:
                raise StructureCatalogError(
                    f"字段 {table_name}.{column_name} 属于未导出的表"
                )
            key = (table_name, column_name)
            if key in column_keys:
                raise StructureCatalogError(f"字段重复：{table_name}.{column_name}")
            column_keys.add(key)

        catalog = cls(
            schema_name="mart_sales",
            tables=tuple(sorted(tables, key=lambda item: str(item["table_name"]))),
            columns=tuple(
                sorted(
                    columns,
                    key=lambda item: (
                        str(item["table_name"]),
                        int(item["ordinal_position"]),
                    ),
                )
            ),
            relationships=relationships,
        )
        catalog._validate_relationships()
        return catalog

    @property
    def table_names(self) -> frozenset[str]:
        """返回允许访问的物理表名。"""

        return frozenset(str(item["table_name"]) for item in self.tables)

    @property
    def column_names(self) -> frozenset[tuple[str, str]]:
        """返回 ``(table_name, column_name)`` 集合。"""

        return frozenset(
            (str(item["table_name"]), str(item["column_name"]))
            for item in self.columns
        )

    def has_table(self, table_name: str) -> bool:
        """判断表是否属于当前 ``mart_sales`` 目录。"""

        return table_name in self.table_names

    def has_column(self, table_name: str, column_name: str) -> bool:
        """判断字段是否属于指定表。"""

        return (table_name, column_name) in self.column_names

    def render_prompt(self) -> str:
        """把结构元数据渲染成简洁、稳定的 Prompt（提示词）文本。"""

        columns_by_table: dict[str, list[dict[str, Any]]] = {
            table_name: [] for table_name in self.table_names
        }
        for column in self.columns:
            columns_by_table[str(column["table_name"])].append(column)

        lines = [f"Schema: {self.schema_name}", "Tables and columns:"]
        for table in self.tables:
            table_name = str(table["table_name"])
            description = table.get("description") or ""
            suffix = f" - {description}" if description else ""
            lines.append(f"- {self.schema_name}.{table_name}{suffix}")
            for column in columns_by_table[table_name]:
                flags: list[str] = []
                if column.get("is_primary_key"):
                    flags.append("PK")
                if column.get("is_foreign_key"):
                    flags.append("FK")
                flag_text = f" [{', '.join(flags)}]" if flags else ""
                description = column.get("description") or ""
                description_text = f" - {description}" if description else ""
                lines.append(
                    f"  - {column['column_name']} {column['data_type']}"
                    f"{flag_text}{description_text}"
                )

        lines.append("Physical foreign-key relationships:")
        for relation in self.relationships.get("foreign_keys", []):
            local = ".".join(str(value) for value in relation["column_names"])
            remote = ".".join(
                str(value) for value in relation["referenced_column_names"]
            )
            lines.append(
                f"- {self.schema_name}.{relation['table_name']}.{local} = "
                f"{self.schema_name}.{relation['referenced_table']}.{remote}"
            )
        return "\n".join(lines)

    def _validate_relationships(self) -> None:
        for relation in self.relationships.get("foreign_keys", []):
            if relation.get("schema_name") != self.schema_name:
                raise StructureCatalogError("外键关系包含非 mart_sales Schema")
            if relation.get("referenced_schema") != self.schema_name:
                raise StructureCatalogError("外键目标包含非 mart_sales Schema")
            local_table = str(relation.get("table_name"))
            remote_table = str(relation.get("referenced_table"))
            local_columns = relation.get("column_names", [])
            remote_columns = relation.get("referenced_column_names", [])
            if not self.has_table(local_table) or not self.has_table(remote_table):
                raise StructureCatalogError("外键关系引用了未知表")
            if len(local_columns) != len(remote_columns):
                raise StructureCatalogError("复合外键两侧字段数量不一致")
            for local, remote in zip(local_columns, remote_columns):
                if not self.has_column(local_table, str(local)):
                    raise StructureCatalogError(f"外键本地字段不存在：{local_table}.{local}")
                if not self.has_column(remote_table, str(remote)):
                    raise StructureCatalogError(
                        f"外键目标字段不存在：{remote_table}.{remote}"
                    )


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise StructureCatalogError(f"缺少结构文件：{path}") from exc
    except json.JSONDecodeError as exc:
        raise StructureCatalogError(f"结构文件不是有效 JSON：{path}") from exc
