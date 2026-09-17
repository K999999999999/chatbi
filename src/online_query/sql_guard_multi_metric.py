"""SQL Guard 的 Multi-Metric（多指标）结构、公式和过滤校验。"""

from sqlglot import exp, parse_one
from sqlglot.errors import SqlglotError

from .contracts import QueryContext
from .sql_guard_errors import SQLRejectedError


def validate_multi_metric_expression(
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
        if isinstance(constraint.data_source, str) and constraint.data_source.strip()
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
        _qualified_table_ref(table) for table in expression.find_all(exp.Table)
    )
    if len(table_refs) != len(set(table_refs)):
        raise SQLRejectedError("多指标 SQL 不支持同一物理表的重复引用")
    if sum(table.casefold() == metric_table.casefold() for table in table_refs) != 1:
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
        _qualified_table_ref(table) for table in expression.find_all(exp.Table)
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
        if side != "LEFT" or kind == "CROSS":
            raise SQLRejectedError("多指标 SQL 只允许使用 LEFT JOIN")
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
        not in {constraint.target_table.casefold() for constraint in constraints}
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
        if isinstance(node, exp.AggFunc) and id(node) not in metric_aggregate_ids:
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
    from .sql_guard import _table_bindings as implementation

    return implementation(expression)


def _qualified_table_ref(table: exp.Table) -> str:
    from .sql_guard import _qualified_table_ref as implementation

    return implementation(table)


def _join_pairs(
    condition: exp.Expression,
    bindings: dict[str, set[str]],
    context: QueryContext,
) -> frozenset[tuple[tuple[str, str], tuple[str, str]]]:
    from .sql_guard import _join_pairs as implementation

    return implementation(condition, bindings, context)


def _constraint_pairs(
    constraint: object,
) -> frozenset[tuple[tuple[str, str], tuple[str, str]]]:
    from .sql_guard import _constraint_pairs as implementation

    return implementation(constraint)


def _canonical_expression_sql(
    expression: exp.Expression,
    *,
    bindings: dict[str, set[str]],
    context: QueryContext,
    default_table: str | None = None,
    aliases_are_default: bool = False,
) -> str:
    from .sql_guard import _canonical_expression_sql as implementation

    return implementation(
        expression,
        bindings=bindings,
        context=context,
        default_table=default_table,
        aliases_are_default=aliases_are_default,
    )


def _multi_conjuncts(
    condition: exp.Expression | None,
) -> tuple[exp.Expression, ...]:
    from .sql_guard import _multi_conjuncts as implementation

    return implementation(condition)
