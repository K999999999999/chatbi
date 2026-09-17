"""SQL Guard 的 AST 作用域、表绑定和动态白名单辅助。"""

from collections.abc import Iterable

from sqlglot import exp
from sqlglot.errors import SqlglotError
from sqlglot.optimizer.qualify import qualify
from sqlglot.optimizer.scope import traverse_scope

from ..contracts import JoinConstraint, QueryContext
from .sql_guard_errors import SQLRejectedError


ALLOWED_SCHEMA = "mart_sales"


def _table_bindings(expression: exp.Select) -> dict[str, set[str]]:
    bindings: dict[str, set[str]] = {}
    for table in expression.find_all(exp.Table):
        qualified = _qualified_table_ref(table)
        names = {table.name, qualified}
        if table.alias:
            names.add(table.alias)
        for name in names:
            bindings.setdefault(name.casefold(), set()).add(qualified)
    return bindings


def _qualified_table_ref(table: exp.Table) -> str:
    schema = table.db
    name = table.name
    if table.catalog or not schema or not name:
        raise SQLRejectedError("多指标 SQL 只能引用完整的 mart_sales 表")
    return f"{schema}.{name}"


def _join_pairs(
    condition: exp.Expression,
    bindings: dict[str, set[str]],
    context: QueryContext,
) -> frozenset[tuple[tuple[str, str], tuple[str, str]]]:
    pairs: set[tuple[tuple[str, str], tuple[str, str]]] = set()
    for item in _multi_conjuncts(condition):
        if not isinstance(item, exp.EQ):
            raise SQLRejectedError("多指标 SQL 的 Join 只能使用等值键连接")
        left, right = item.this, item.expression
        if not isinstance(left, exp.Column) or not isinstance(right, exp.Column):
            raise SQLRejectedError("多指标 SQL 的 Join 键必须是字段")
        left_identity = _column_identity(left, bindings, context)
        right_identity = _column_identity(right, bindings, context)
        pairs.add(tuple(sorted((left_identity, right_identity))))
    return frozenset(pairs)


def _constraint_pairs(
    constraint: JoinConstraint,
) -> frozenset[tuple[tuple[str, str], tuple[str, str]]]:
    if (
        constraint.direction.casefold() != "forward"
        or len(constraint.source_columns) != len(constraint.target_columns)
        or not constraint.source_columns
    ):
        return frozenset()
    return frozenset(
        tuple(
            sorted(
                (
                    (
                        constraint.source_table.casefold(),
                        source_column.casefold(),
                    ),
                    (
                        constraint.target_table.casefold(),
                        target_column.casefold(),
                    ),
                )
            )
        )
        for source_column, target_column in zip(
            constraint.source_columns,
            constraint.target_columns,
        )
    )


def _column_identity(
    column: exp.Column,
    bindings: dict[str, set[str]],
    context: QueryContext,
    *,
    default_table: str | None = None,
    aliases_are_default: bool = False,
) -> tuple[str, str]:
    if aliases_are_default:
        if default_table is None:
            raise SQLRejectedError("指标公式缺少事实表")
        physical_table = default_table
    elif column.db and column.table:
        physical_table = _match_table_name(
            f"{column.db}.{column.table}",
            set().union(*bindings.values()),
        )
    elif column.table:
        candidates = bindings.get(column.table.casefold(), set())
        if len(candidates) != 1:
            raise SQLRejectedError("SQL 字段表别名无法唯一解析")
        physical_table = next(iter(candidates))
    else:
        candidates = {
            table
            for table in set().union(*bindings.values())
            if column.name in context.allowed_columns.get(table, frozenset())
        }
        if len(candidates) != 1:
            raise SQLRejectedError("SQL 未限定字段无法唯一解析")
        physical_table = next(iter(candidates))

    allowed = context.allowed_columns.get(physical_table, frozenset())
    if column.name not in allowed:
        raise SQLRejectedError("SQL 字段不在多指标候选范围内")
    return physical_table.casefold(), column.name.casefold()


def _match_table_name(value: str, candidates: Iterable[str]) -> str:
    for candidate in candidates:
        if candidate.casefold() == value.casefold():
            return candidate
    raise SQLRejectedError("SQL 字段引用了未绑定的表")


def _canonical_expression_sql(
    expression: exp.Expression,
    *,
    bindings: dict[str, set[str]],
    context: QueryContext,
    default_table: str | None = None,
    aliases_are_default: bool = False,
) -> str:
    normalized = expression.copy()
    for column in normalized.find_all(exp.Column):
        physical_table, column_name = _column_identity(
            column,
            bindings,
            context,
            default_table=default_table,
            aliases_are_default=aliases_are_default,
        )
        schema, table = physical_table.split(".", maxsplit=1)
        column.set("catalog", None)
        column.set("db", exp.to_identifier(schema))
        column.set("table", exp.to_identifier(table))
        column.set("this", exp.to_identifier(column_name))
    while normalized.find(exp.Paren) is not None:
        normalized = normalized.transform(
            lambda node: node.this if isinstance(node, exp.Paren) else node
        )
    return normalized.sql(dialect="postgres", normalize=True)


def _multi_conjuncts(
    condition: exp.Expression | None,
) -> tuple[exp.Expression, ...]:
    if condition is None:
        return ()
    if isinstance(condition, exp.And):
        return (*_multi_conjuncts(condition.left), *_multi_conjuncts(condition.right))
    if isinstance(condition, exp.Paren):
        return _multi_conjuncts(condition.this)
    return (condition,)


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
    except (TypeError, KeyError, SqlglotError, ValueError):
        raise SQLRejectedError("SQL 引用了未知或歧义字段") from None
