"""单指标与多指标共用的认证公式、固定过滤条件校验。"""

from collections.abc import Sequence

from sqlglot import exp, parse_one
from sqlglot.errors import SqlglotError

from ..contracts import QueryContext
from .sql_guard_errors import SQLRejectedError
from .sql_guard_scope import _canonical_expression_sql, _multi_conjuncts


def validate_metric_filters(
    expression: exp.Select,
    context: QueryContext,
    bindings: dict[str, set[str]],
) -> None:
    """固定口径必须是顶层 WHERE 的必需 AND 条件，不能藏在 OR 分支中。"""

    where = expression.args.get("where")
    actual_filters = {
        _canonical_expression_sql(item, bindings=bindings, context=context)
        for item in _multi_conjuncts(where.this if where is not None else None)
    }
    expected_filters: set[str] = set()
    for constraint in context.metric_constraints:
        for raw_filter in constraint.filters:
            try:
                parsed = parse_one(f"SELECT 1 WHERE {raw_filter}", dialect="postgres")
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
                    default_table=constraint.data_source,
                    aliases_are_default=True,
                )
                for item in _multi_conjuncts(parsed_where.this)
            )
    if not expected_filters.issubset(actual_filters):
        raise SQLRejectedError("SQL 缺少认证固定过滤条件")


def validate_metric_formulas(
    projections: Sequence[exp.Expression],
    context: QueryContext,
    bindings: dict[str, set[str]],
) -> None:
    """输出聚合必须完整且按认证指标顺序匹配，不通过列别名认定指标。"""

    if len(projections) != len(context.metric_constraints):
        raise SQLRejectedError("SQL 输出的指标数量与认证指标不一致")
    for projection, constraint in zip(projections, context.metric_constraints):
        try:
            expected = parse_one(constraint.formula, dialect="postgres")
        except SqlglotError:
            raise SQLRejectedError("指标认证公式无法解析") from None
        actual_signature = _canonical_expression_sql(
            projection, bindings=bindings, context=context
        )
        expected_signature = _canonical_expression_sql(
            expected,
            bindings={},
            context=context,
            default_table=constraint.data_source,
            aliases_are_default=True,
        )
        if actual_signature != expected_signature:
            raise SQLRejectedError(f"SQL 未按认证公式实现：{constraint.metric_name}")
