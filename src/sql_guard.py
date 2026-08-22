"""确定性 SQL Guard（SQL 守卫）。"""

from __future__ import annotations

import re
from dataclasses import dataclass

from src.structure import StructureCatalog


class SqlValidationError(ValueError):
    """SQL 候选不满足只读和结构边界。"""

    def __init__(self, message: str, code: str = "sql_rejected") -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ValidatedSql:
    """通过 Guard 的 SQL。"""

    sql: str


@dataclass(frozen=True)
class _TableReference:
    schema_name: str
    table_name: str
    alias: str


_TABLE_REFERENCE = re.compile(
    r"\b(?:FROM|JOIN)\s+"
    r"(?P<schema>[A-Za-z_][A-Za-z0-9_]*)\."
    r"(?P<table>[A-Za-z_][A-Za-z0-9_]*)"
    r"(?:\s+(?:AS\s+)?(?P<alias>[A-Za-z_][A-Za-z0-9_]*))?",
    re.IGNORECASE,
)
_COLUMN_REFERENCE = re.compile(
    r"\b(?P<qualifier>[A-Za-z_][A-Za-z0-9_]*)\."
    r"(?P<column>[A-Za-z_][A-Za-z0-9_]*)\b",
    re.IGNORECASE,
)
_FORBIDDEN = re.compile(
    r"\b(?:INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|GRANT|REVOKE|"
    r"COPY|CALL|DO|SET|SHOW|VACUUM|ANALYZE|MERGE|EXECUTE)\b",
    re.IGNORECASE,
)
_FORBIDDEN_FUNCTION = re.compile(
    r"\b(?:pg_sleep|dblink|lo_import|lo_export|set_config|current_setting|"
    r"nextval|setval)\s*\(",
    re.IGNORECASE,
)
_RESERVED_AFTER_TABLE = {
    "AS",
    "ON",
    "WHERE",
    "GROUP",
    "ORDER",
    "HAVING",
    "LIMIT",
    "UNION",
    "LEFT",
    "RIGHT",
    "INNER",
    "FULL",
    "CROSS",
    "JOIN",
}


class SqlGuard:
    """校验 SQL 语法边界、Schema 白名单和字段引用。"""

    def __init__(self, structure: StructureCatalog) -> None:
        self.structure = structure

    def validate(self, raw_sql: str) -> ValidatedSql:
        sql = raw_sql.strip()
        if not sql:
            raise SqlValidationError("SQL 为空", "empty_sql")
        if "--" in sql or "/*" in sql or "*/" in sql:
            raise SqlValidationError("SQL 不允许包含注释", "sql_comment")
        if ";" in sql.rstrip(";"):
            raise SqlValidationError("SQL 只允许一条语句", "multiple_statements")
        sql = sql.rstrip(";").strip()
        if not re.match(r"^SELECT\b", sql, re.IGNORECASE):
            raise SqlValidationError("POC 只允许 SELECT 查询", "not_select")
        if _FORBIDDEN.search(sql):
            raise SqlValidationError("SQL 包含禁止的写入或管理关键字", "forbidden_keyword")
        if _FORBIDDEN_FUNCTION.search(sql):
            raise SqlValidationError("SQL 包含禁止的系统函数", "forbidden_function")
        if re.search(r"\b(?:pg_catalog|information_schema|public)\b", sql, re.IGNORECASE):
            raise SqlValidationError("SQL 只能访问 mart_sales Schema", "schema_forbidden")
        if re.search(r"\bSELECT\s+\*", sql, re.IGNORECASE):
            raise SqlValidationError("POC 不允许无界 SELECT *", "select_star")

        references = self._extract_table_references(sql)
        if not references:
            raise SqlValidationError("SQL 缺少可验证的 FROM 表", "missing_from")
        table_spans = [
            match.span()
            for match in _TABLE_REFERENCE.finditer(sql)
        ]
        aliases = {reference.alias: reference for reference in references}
        for reference in references:
            if reference.schema_name != self.structure.schema_name:
                raise SqlValidationError("SQL 只能访问 mart_sales Schema", "schema_forbidden")
            if not self.structure.has_table(reference.table_name):
                raise SqlValidationError(
                    f"SQL 引用了未知表：{reference.table_name}",
                    "unknown_table",
                )

        for match in _COLUMN_REFERENCE.finditer(sql):
            if any(
                start <= match.start() and match.end() <= end
                for start, end in table_spans
            ):
                # 跳过 FROM/JOIN 中的 schema.table 本身，不把表名误判成字段引用。
                continue
            qualifier = match.group("qualifier").lower()
            column = match.group("column")
            if qualifier == self.structure.schema_name.lower():
                # 仅允许 schema.table 出现在 FROM/JOIN；三段式字段引用不在 POC 范围内。
                raise SqlValidationError(
                    "字段应通过表别名引用，暂不支持三段式列名",
                    "unsupported_identifier",
                )
            reference = aliases.get(qualifier)
            if reference is None:
                continue
            if not self.structure.has_column(reference.table_name, column):
                raise SqlValidationError(
                    f"SQL 引用了未知字段：{reference.table_name}.{column}",
                    "unknown_column",
                )

        return ValidatedSql(sql=sql)

    def _extract_table_references(self, sql: str) -> tuple[_TableReference, ...]:
        references: list[_TableReference] = []
        for match in _TABLE_REFERENCE.finditer(sql):
            schema_name = match.group("schema")
            table_name = match.group("table")
            alias = match.group("alias") or table_name
            if alias.upper() in _RESERVED_AFTER_TABLE:
                alias = table_name
            references.append(
                _TableReference(
                    schema_name=schema_name,
                    table_name=table_name,
                    alias=alias.lower(),
                )
            )
        aliases = [reference.alias for reference in references]
        if len(aliases) != len(set(aliases)):
            raise SqlValidationError("SQL 表别名重复", "duplicate_alias")
        return tuple(references)


def validate_sql(raw_sql: str, structure: StructureCatalog) -> ValidatedSql:
    """函数式入口，方便测试和小型调用方使用。"""

    return SqlGuard(structure).validate(raw_sql)
