"""使用 SQLGlot 对 LLM SQL 候选做确定性安全校验。"""

from sqlglot import exp, parse
from sqlglot.errors import SqlglotError
from sqlglot.optimizer.qualify import qualify
from sqlglot.optimizer.scope import traverse_scope

from .contracts import QueryContext, ValidatedSQL


ALLOWED_SCHEMA = "mart_sales"
_FORBIDDEN_NODE_TYPES = (
    exp.DDL,
    exp.DML,
    exp.Copy,
    exp.Command,
    exp.Into,
    exp.Lock,
)

class SQLRejectedError(RuntimeError):
    """SQL 候选不满足只读白名单契约。"""


def validate_candidate_scope(candidate: str, context: QueryContext) -> None:
    """在 AST SQL Guard（SQL 安全校验）前拒绝动态范围外的表和字段。"""

    sql = candidate.strip()
    if not sql or sql == "CANNOT_ANSWER":
        raise SQLRejectedError("SQL 候选为空或不是 SQL")
    expression = _parse_single_select(sql)
    physical_tables = _physical_tables(expression)
    if not physical_tables:
        raise SQLRejectedError("SQL 必须读取 mart_sales 物理表")
    _validate_physical_tables(physical_tables, context)
    _validate_columns(expression, context)


def validate_sql(candidate: str, context: QueryContext) -> ValidatedSQL:
    """校验 SQL 候选，不改写原始 SQL。"""

    sql = candidate.strip()
    if not sql or sql == "CANNOT_ANSWER":
        raise SQLRejectedError("SQL 候选为空或不是 SQL")

    expression = _parse_single_select(sql)
    if any(expression.find(node_type) for node_type in _FORBIDDEN_NODE_TYPES):
        raise SQLRejectedError("SQL 包含禁止的写入、结构修改或锁定操作")

    _reject_dangerous_functions(expression)
    physical_tables = _physical_tables(expression)
    if not physical_tables:
        raise SQLRejectedError("SQL 必须读取 mart_sales 物理表")
    _validate_physical_tables(physical_tables, context)
    _validate_columns(expression, context)

    return ValidatedSQL(sql=sql)


def _parse_single_select(sql: str) -> exp.Select:
    try:
        statements = [
            statement
            for statement in parse(sql, read="postgres")
            if statement is not None
        ]
    except SqlglotError:
        raise SQLRejectedError("SQL 无法按 PostgreSQL 解析") from None

    if len(statements) != 1:
        raise SQLRejectedError("只允许一条 SQL")
    expression = statements[0]
    if not isinstance(expression, exp.Select):
        raise SQLRejectedError("只允许 SELECT 或 WITH SELECT")
    return expression


def _physical_tables(expression: exp.Expression) -> list[exp.Table]:
    tables: list[exp.Table] = []
    for scope in traverse_scope(expression):
        for table in scope.tables:
            if (
                isinstance(table, exp.Table)
                and table.name
                and table.name not in scope.cte_sources
            ):
                tables.append(table)
    return tables


def _validate_physical_tables(
    tables: list[exp.Table],
    context: QueryContext,
) -> None:
    for table in tables:
        schema_name = table.db
        table_name = table.name
        if table.catalog or schema_name != ALLOWED_SCHEMA:
            raise SQLRejectedError("只能访问 mart_sales Schema")
        qualified_name = f"{schema_name}.{table_name}"
        if qualified_name not in context.allowed_tables:
            raise SQLRejectedError("SQL 引用了未知表")


def _validate_columns(expression: exp.Expression, context: QueryContext) -> None:
    schema: dict[str, dict[str, dict[str, str]]] = {ALLOWED_SCHEMA: {}}
    for qualified_name in context.allowed_tables:
        schema_name, table_name = qualified_name.split(".", maxsplit=1)
        if schema_name != ALLOWED_SCHEMA:
            continue
        schema[ALLOWED_SCHEMA][table_name] = {
            column: "UNKNOWN"
            for column in context.allowed_columns.get(qualified_name, frozenset())
        }

    try:
        qualify(
            expression.copy(),
            dialect="postgres",
            schema=schema,
            quote_identifiers=False,
            identify=False,
            validate_qualify_columns=True,
        )
    except (SqlglotError, KeyError, TypeError, ValueError):
        raise SQLRejectedError("SQL 引用了未知或歧义字段") from None


def _reject_dangerous_functions(expression: exp.Expression) -> None:
    if expression.find(exp.Anonymous):
        raise SQLRejectedError("SQL 包含未认证的数据库函数")
