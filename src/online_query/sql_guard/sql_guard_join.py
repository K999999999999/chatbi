"""SQL Guard 的 Relationship Graph Join 校验。"""

from sqlglot import exp

from ..contracts import QueryContext
from .sql_guard_errors import SQLRejectedError


def validate_join_constraints(
    expression: exp.Select,
    context: QueryContext,
) -> None:
    """校验实体/单指标查询使用的直接认证 Join。"""

    joins = tuple(expression.args.get("joins") or ())
    constraints = tuple(
        constraint
        for constraint in context.join_constraints
        if constraint.direction.casefold() == "forward"
    )
    if not joins or not constraints:
        raise SQLRejectedError("SQL Join 缺少认证的 Relationship Graph 事实")

    from_clause = expression.args.get("from_")
    if from_clause is None or not isinstance(from_clause.this, exp.Table):
        raise SQLRejectedError("SQL Join 必须从事实表 Anchor 开始")
    base_table = _qualified_table_ref(from_clause.this)
    source_tables = {constraint.source_table.casefold() for constraint in constraints}
    if base_table.casefold() not in source_tables:
        raise SQLRejectedError("SQL Join 的主表不是认证事实表 Anchor")

    bindings = _table_bindings(expression)
    table_refs = tuple(
        _qualified_table_ref(table)
        for table in expression.find_all(exp.Table)
    )
    if len(table_refs) != 1 + len(joins):
        raise SQLRejectedError("SQL 表必须通过显式认证 Join 连接")

    used: set[int] = set()
    for join in joins:
        side = str(join.args.get("side") or "").upper()
        kind = str(join.args.get("kind") or "").upper()
        if side != "LEFT" or kind == "CROSS":
            raise SQLRejectedError("事实表到维表只允许使用 LEFT JOIN")
        joined_table = join.args.get("this")
        condition = join.args.get("on")
        if not isinstance(joined_table, exp.Table) or condition is None:
            raise SQLRejectedError("SQL Join 必须是带 ON 的物理表连接")
        target_table = _qualified_table_ref(joined_table)
        actual_pairs = _join_pairs(condition, bindings, context)
        matches = [
            (index, constraint)
            for index, constraint in enumerate(constraints)
            if index not in used
            and constraint.target_table.casefold() == target_table.casefold()
            and actual_pairs == _constraint_pairs(constraint)
        ]
        if len(matches) != 1:
            raise SQLRejectedError("SQL Join 使用了未认证或错误的直接关系")
        used.add(matches[0][0])


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


def _constraint_pairs(constraint: object) -> frozenset[tuple[tuple[str, str], tuple[str, str]]]:
    from .sql_guard import _constraint_pairs as implementation

    return implementation(constraint)
