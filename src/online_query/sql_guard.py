"""使用 SQLGlot 对 LLM SQL 候选做确定性安全校验。"""

from collections.abc import Iterable

from sqlglot import exp, parse, parse_one
from sqlglot.errors import SqlglotError
from sqlglot.optimizer.qualify import qualify
from sqlglot.optimizer.scope import traverse_scope

from .contracts import JoinConstraint, QueryContext, ValidatedSQL


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
    if len(context.metric_constraints) >= 2:
        _validate_multi_metric_expression(expression, context)

    return ValidatedSQL(sql=sql)


def validate_multi_metric_sql(candidate: str, context: QueryContext) -> None:
    """单独执行多指标 SQL 结构、公式、过滤和输出完整性校验。"""

    if len(context.metric_constraints) < 2:
        return
    sql = candidate.strip()
    if not sql or sql == "CANNOT_ANSWER":
        raise SQLRejectedError("SQL 候选为空或不是 SQL")
    _validate_multi_metric_expression(_parse_single_select(sql), context)


def _validate_multi_metric_expression(
    expression: exp.Select,
    context: QueryContext,
) -> None:
    constraints = context.metric_constraints
    metric_table = _multi_metric_table(constraints)
    bindings = _table_bindings(expression)
    _reject_multi_metric_structure(expression)
    _validate_multi_metric_from(expression, context, metric_table)
    _validate_multi_metric_joins(expression, context, bindings, metric_table)
    _validate_multi_metric_filters(expression, context, bindings, metric_table)
    _validate_multi_metric_output(expression, context, bindings, metric_table)


def _reject_multi_metric_structure(expression: exp.Select) -> None:
    for node_type, label in (
        (exp.With, "CTE"),
        (exp.Subquery, "子查询"),
        (exp.Window, "窗口函数"),
        (exp.SetOperation, "集合运算"),
        (exp.Having, "HAVING"),
    ):
        if expression.find(node_type) is not None:
            raise SQLRejectedError(f"多指标 SQL 不支持{label}")
    if expression.args.get("distinct") is not None:
        raise SQLRejectedError("多指标 SQL 不支持顶层 DISTINCT")


def _multi_metric_table(constraints: tuple) -> str:
    sources = {
        constraint.data_source.strip().casefold()
        for constraint in constraints
        if isinstance(constraint.data_source, str)
        and constraint.data_source.strip()
    }
    if len(sources) != 1:
        raise SQLRejectedError("多指标必须共享一个事实表")
    return constraints[0].data_source.strip()


def _validate_multi_metric_from(
    expression: exp.Select,
    context: QueryContext,
    metric_table: str,
) -> None:
    from_clause = expression.args.get("from_")
    if from_clause is None or not isinstance(from_clause.this, exp.Table):
        raise SQLRejectedError("多指标 SQL 必须从共同事实表开始")
    if from_clause.expressions:
        raise SQLRejectedError("多指标 SQL 不支持逗号隐式 Join")

    base_table = _qualified_table_ref(from_clause.this)
    if base_table.casefold() != metric_table.casefold():
        raise SQLRejectedError("多指标 SQL 必须以共同事实表为主表")

    table_refs = tuple(
        _qualified_table_ref(table)
        for table in expression.find_all(exp.Table)
    )
    if len(table_refs) != len(set(table_refs)):
        raise SQLRejectedError("多指标 SQL 不支持同一物理表的重复引用")
    if sum(
        table.casefold() == metric_table.casefold()
        for table in table_refs
    ) != 1:
        raise SQLRejectedError("多指标 SQL 必须只包含一个共同事实表")

    certified_tables = {
        metric_table.casefold(),
        *(
            table.casefold()
            for constraint in context.join_constraints
            for table in (constraint.source_table, constraint.target_table)
        ),
    }
    if any(table.casefold() not in certified_tables for table in table_refs):
        raise SQLRejectedError("多指标 SQL 引用了未认证的关联表")


def _validate_multi_metric_joins(
    expression: exp.Select,
    context: QueryContext,
    bindings: dict[str, set[str]],
    metric_table: str,
) -> None:
    joins = tuple(expression.args.get("joins") or ())
    table_refs = tuple(
        _qualified_table_ref(table)
        for table in expression.find_all(exp.Table)
    )
    if len(table_refs) != 1 + len(joins):
        raise SQLRejectedError("多指标 SQL 的表必须通过显式认证 Join 连接")

    constraints = tuple(
        constraint
        for constraint in context.join_constraints
        if constraint.direction.casefold() == "forward"
    )
    used: set[int] = set()
    for join in joins:
        side = str(join.args.get("side") or "").upper()
        kind = str(join.args.get("kind") or "").upper()
        if side in {"RIGHT", "FULL"} or kind == "CROSS":
            raise SQLRejectedError("多指标 SQL 只允许从事实表正向安全 Join")
        joined_table = join.args.get("this")
        if not isinstance(joined_table, exp.Table):
            raise SQLRejectedError("多指标 SQL 只能 Join 物理表")
        target_table = _qualified_table_ref(joined_table)
        condition = join.args.get("on")
        if condition is None:
            raise SQLRejectedError("多指标 SQL 的 Join 必须包含认证 ON 条件")
        actual_pairs = _join_pairs(condition, bindings, context)
        matches = [
            (index, constraint)
            for index, constraint in enumerate(constraints)
            if index not in used
            and constraint.target_table.casefold() == target_table.casefold()
            and actual_pairs == _constraint_pairs(constraint)
        ]
        if len(matches) != 1:
            raise SQLRejectedError("多指标 SQL 使用了未认证或错误的 Join")
        used.add(matches[0][0])

    if any(
        table.casefold() != metric_table.casefold()
        and table.casefold()
        not in {
            constraint.target_table.casefold()
            for constraint in constraints
        }
        for table in table_refs
    ):
        raise SQLRejectedError("多指标 SQL 的 Join 目标不在认证关系中")


def _validate_multi_metric_filters(
    expression: exp.Select,
    context: QueryContext,
    bindings: dict[str, set[str]],
    metric_table: str,
) -> None:
    where = expression.args.get("where")
    condition = where.this if where is not None else None
    if condition is not None and any(
        isinstance(node, exp.Or) for node in condition.walk()
    ):
        raise SQLRejectedError("多指标 SQL 的 WHERE 不允许 OR")

    actual_filters = {
        _canonical_expression_sql(
            item,
            bindings=bindings,
            context=context,
        )
        for item in _multi_conjuncts(condition)
    }
    expected_filters: set[str] = set()
    for constraint in context.metric_constraints:
        for raw_filter in constraint.filters:
            try:
                parsed = parse_one(
                    f"SELECT 1 WHERE {raw_filter}",
                    dialect="postgres",
                )
            except SqlglotError:
                raise SQLRejectedError("指标固定过滤条件无法解析") from None
            parsed_where = parsed.args.get("where")
            if not isinstance(parsed_where, exp.Where):
                raise SQLRejectedError("指标固定过滤条件无法解析")
            expected_filters.update(
                _canonical_expression_sql(
                    item,
                    bindings={},
                    context=context,
                    default_table=metric_table,
                    aliases_are_default=True,
                )
                for item in _multi_conjuncts(parsed_where.this)
            )

    if not expected_filters.issubset(actual_filters):
        raise SQLRejectedError("多指标 SQL 缺少认证固定过滤条件")


def _validate_multi_metric_output(
    expression: exp.Select,
    context: QueryContext,
    bindings: dict[str, set[str]],
    metric_table: str,
) -> None:
    projections = tuple(expression.expressions)
    if not projections:
        raise SQLRejectedError("多指标 SQL 没有输出字段")

    metric_projections: list[exp.Expression] = []
    dimension_projections: list[exp.Expression] = []
    metric_aggregate_ids: set[int] = set()
    for projection in projections:
        value = projection.this if isinstance(projection, exp.Alias) else projection
        if any(isinstance(node, exp.Star) for node in value.walk()):
            raise SQLRejectedError("多指标 SQL 不允许 SELECT *")
        aggregates = tuple(
            node for node in value.walk() if isinstance(node, exp.AggFunc)
        )
        if aggregates:
            metric_projections.append(value)
            metric_aggregate_ids.update(id(node) for node in aggregates)
        else:
            if not isinstance(value, exp.Column):
                raise SQLRejectedError("多指标 SQL 的非聚合输出必须是分组字段")
            dimension_projections.append(value)

    if len(metric_projections) != len(context.metric_constraints):
        raise SQLRejectedError("多指标 SQL 输出的指标数量不完整")

    for node in expression.walk():
        if (
            isinstance(node, exp.AggFunc)
            and id(node) not in metric_aggregate_ids
        ):
            raise SQLRejectedError("多指标 SQL 包含额外聚合表达式")

    group = expression.args.get("group")
    group_expressions = tuple(group.expressions) if group is not None else ()
    if dimension_projections and not group_expressions:
        raise SQLRejectedError("多指标 SQL 的分组字段必须出现在 GROUP BY")
    if not dimension_projections and group_expressions:
        raise SQLRejectedError("多指标 SQL 不能包含未输出的分组字段")
    dimension_signatures = {
        _canonical_expression_sql(
            item,
            bindings=bindings,
            context=context,
        )
        for item in dimension_projections
    }
    group_signatures = {
        _canonical_expression_sql(
            item,
            bindings=bindings,
            context=context,
        )
        for item in group_expressions
    }
    if dimension_signatures != group_signatures:
        raise SQLRejectedError("多指标 SQL 的输出分组与 GROUP BY 不一致")

    for projection, constraint in zip(
        metric_projections,
        context.metric_constraints,
    ):
        try:
            expected = parse_one(constraint.formula, dialect="postgres")
        except SqlglotError:
            raise SQLRejectedError("指标认证公式无法解析") from None
        actual_signature = _canonical_expression_sql(
            projection,
            bindings=bindings,
            context=context,
        )
        expected_signature = _canonical_expression_sql(
            expected,
            bindings={},
            context=context,
            default_table=metric_table,
            aliases_are_default=True,
        )
        if actual_signature != expected_signature:
            raise SQLRejectedError(
                f"多指标 SQL 未按认证公式实现：{constraint.metric_name}"
            )


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
