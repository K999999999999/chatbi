"""使用 SQLGlot 对 LLM SQL 候选做确定性安全校验。"""

from collections.abc import Iterable

from sqlglot import exp, parse
from sqlglot.errors import SqlglotError
from sqlglot.optimizer.qualify import qualify
from sqlglot.optimizer.scope import traverse_scope

from .contracts import JoinConstraint, QueryContext, ValidatedSQL
from .sql_guard_errors import SQLRejectedError
from .sql_guard_join import validate_join_constraints
from .sql_guard_multi_metric import validate_multi_metric_expression


ALLOWED_SCHEMA = "mart_sales"
_FORBIDDEN_NODE_TYPES = (
    exp.DDL,
    exp.DML,
    exp.Copy,
    exp.Command,
    exp.Into,
    exp.Lock,
)


class _ValidationSession:
    """保存一次 SQL 校验调用内可复用的 AST 和范围校验事实。"""

    def __init__(self, candidate: str, context: QueryContext) -> None:
        self._candidate = candidate.strip()
        self._context = context
        self._expression: exp.Select | None = None
        self._scope_validated = False

    def validate_candidate_scope(self) -> None:
        """执行 Candidate Scope Check，并缓存本次调用的范围校验结果。"""

        self._ensure_candidate()
        self._validate_scope(self._parse())

    def validate_sql(self) -> ValidatedSQL:
        """执行完整 SQL Guard；已完成范围校验时复用其 AST 和事实。"""

        self._ensure_candidate()
        expression = self._parse()
        if any(expression.find(node_type) for node_type in _FORBIDDEN_NODE_TYPES):
            raise SQLRejectedError("SQL 包含禁止的写入、结构修改或锁定操作")
        if expression.find(exp.With) is not None:
            raise SQLRejectedError("V1 SQL 不支持 CTE")

        _reject_dangerous_functions(expression)
        if not self._scope_validated:
            self._validate_scope(expression)
        if len(self._context.metric_constraints) >= 2:
            validate_multi_metric_expression(expression, self._context)
        elif expression.args.get("joins"):
            validate_join_constraints(expression, self._context)

        return ValidatedSQL(sql=self._candidate)

    def _ensure_candidate(self) -> None:
        if not self._candidate or self._candidate == "CANNOT_ANSWER":
            raise SQLRejectedError("SQL 候选为空或不是 SQL")

    def _parse(self) -> exp.Select:
        if self._expression is None:
            self._expression = _parse_single_select(self._candidate)
        return self._expression

    def _validate_scope(self, expression: exp.Select) -> None:
        physical_tables = _physical_tables(expression)
        if not physical_tables:
            raise SQLRejectedError("SQL 必须读取 mart_sales 物理表")
        _validate_physical_tables(physical_tables, self._context)
        _validate_columns(expression, self._context)
        self._scope_validated = True


def _new_validation_session(
    candidate: str,
    context: QueryContext,
) -> _ValidationSession:
    """创建只供当前 Online Query 调用使用的内部校验会话。"""

    return _ValidationSession(candidate, context)


def validate_candidate_scope(candidate: str, context: QueryContext) -> None:
    """在 AST SQL Guard（SQL 安全校验）前拒绝动态范围外的表和字段。"""

    _new_validation_session(candidate, context).validate_candidate_scope()


def validate_sql(candidate: str, context: QueryContext) -> ValidatedSQL:
    """校验 SQL 候选，不改写原始 SQL。"""

    return _new_validation_session(candidate, context).validate_sql()


def validate_multi_metric_sql(candidate: str, context: QueryContext) -> None:
    """单独执行多指标 SQL 结构、公式、过滤和输出完整性校验。"""

    if len(context.metric_constraints) < 2:
        return
    sql = candidate.strip()
    if not sql or sql == "CANNOT_ANSWER":
        raise SQLRejectedError("SQL 候选为空或不是 SQL")
    validate_multi_metric_expression(_parse_single_select(sql), context)


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
            if column.name
            in context.allowed_columns.get(table, frozenset())
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
        raise SQLRejectedError("只允许单层 SELECT")
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
