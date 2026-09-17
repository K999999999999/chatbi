"""使用 SQLGlot 对 LLM SQL 候选做确定性安全校验。"""

from sqlglot import exp, parse
from sqlglot.errors import SqlglotError

from ..contracts import QueryContext, ValidatedSQL
from .sql_guard_errors import SQLRejectedError
from .sql_guard_join import validate_join_constraints
from .sql_guard_multi_metric import validate_multi_metric_expression
from .sql_guard_scope import (
    ALLOWED_SCHEMA,
    _canonical_expression_sql,
    _column_identity,
    _constraint_pairs,
    _join_pairs,
    _multi_conjuncts,
    _physical_tables,
    _qualified_table_ref,
    _table_bindings,
    _validate_columns,
    _validate_physical_tables,
)

__all__ = [
    "ALLOWED_SCHEMA",
    "SQLRejectedError",
    "_canonical_expression_sql",
    "_column_identity",
    "_constraint_pairs",
    "_join_pairs",
    "_multi_conjuncts",
    "_physical_tables",
    "_qualified_table_ref",
    "_table_bindings",
    "_validate_columns",
    "_validate_physical_tables",
    "validate_candidate_scope",
    "validate_multi_metric_sql",
    "validate_sql",
]

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


def _reject_dangerous_functions(expression: exp.Expression) -> None:
    if expression.find(exp.Anonymous):
        raise SQLRejectedError("SQL 包含未认证的数据库函数")
