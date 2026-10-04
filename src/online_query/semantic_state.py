"""业务条件到当前认证映射；SQL只能被核对，不能反向定义语义。"""

import json
from dataclasses import asdict, replace
from decimal import Decimal
from hashlib import sha256
from pathlib import Path

from sqlglot import exp, parse_one

from .contracts import QueryContext
from .prompt import _semantic_query_json
from .query_understanding import QueryType, ValidatedSemanticQuery
from .restoration_conditions import BusinessOrder
from .result_time import actual_date_range, calendar_part, completion_date_role
from .sql_guard.sql_guard_scope import (
    _canonical_expression_sql,
    _multi_conjuncts,
    _table_bindings,
)


class SemanticCertificationError(ValueError):
    """当前发布事实不足以认证业务语义。"""


class SemanticSQLMismatch(ValueError):
    """SQL与事先认证业务条件不一致。"""


def load_query_bindings() -> dict:
    value = json.loads(
        (Path(__file__).parents[1] / "semantic/query_bindings.json").read_text()
    )
    if set(value) != {"dimensions", "entity_fields", "filters"}:
        raise SemanticCertificationError("业务绑定配置非法")
    return value


def prepare_restoration_state(semantic: ValidatedSemanticQuery, context: QueryContext):
    """生成SQL前认证完整条件；返回规范语义和最小相关来源。"""
    if semantic.restoration_conditions is None or context.semantic_facts is None:
        raise SemanticCertificationError("缺少完整业务条件或当前发布事实")
    facts = context.semantic_facts
    available = facts["metrics"]
    metrics = []
    canonical_metrics = []
    for requested in semantic.metrics:
        matches = [
            m
            for m in available
            if requested in {m.get("name", m.get("metric_name")), *m.get("aliases", [])}
        ]
        if len(matches) != 1:
            raise SemanticCertificationError("指标无法唯一认证")
        record = matches[0]
        name = record.get("name", record.get("metric_name"))
        canonical_metrics.append(name)
        metrics.append(
            {
                key: record[key]
                for key in (
                    "formula",
                    "data_source",
                    "time_field",
                    "filters",
                    "depends_on",
                )
            }
        )
        metrics[-1]["name"] = name
        metrics[-1]["formula"] = parse_one(metrics[-1]["formula"], read="postgres").sql(
            dialect="postgres", normalize=True
        )
        metrics[-1]["filters"] = sorted(
            parse_one(text, read="postgres").sql(dialect="postgres", normalize=True)
            for text in metrics[-1]["filters"]
        )
        metrics[-1]["depends_on"] = sorted(metrics[-1]["depends_on"])
        metrics[-1]["dependency_definitions"] = _dependency_definitions(
            record, available, {name}
        )
    semantic = replace(semantic, metrics=tuple(canonical_metrics))
    config = load_query_bindings()
    bindings = dict(config["dimensions"])
    bindings.update(config["entity_fields"])
    bindings.update(config["filters"])
    conditions = semantic.restoration_conditions
    if semantic.query_type is QueryType.ENTITY_LOOKUP:
        if conditions.selection is None or conditions.aggregate_filters:
            raise SemanticCertificationError("实体选择不完整")
        targets = conditions.selection.fields
        subject_aliases = {
            "客户": "客户",
            "产品": "产品",
            "订单": "销售订单",
            "销售订单": "销售订单",
        }
        subjects = {subject_aliases.get(subject) for subject in semantic.subjects}
        if None in subjects or not subjects:
            raise SemanticCertificationError("实体主题无法认证")
        if any(
            config["entity_fields"].get(name, {}).get("subject") not in subjects
            for name in targets
        ):
            raise SemanticCertificationError("实体字段不属于所选主题")
    else:
        if conditions.selection is not None:
            raise SemanticCertificationError("指标查询不能携带实体选择")
        targets = semantic.dimensions
        if len(metrics) >= 2 and conditions.aggregate_filters:
            raise SemanticCertificationError("多指标不支持聚合后筛选")
    used_bindings = {}
    time_names = {"年份": "year", "季度": "quarter", "月份": "month"}
    for name in {*targets, *(item.field_text for item in semantic.filters)}:
        if name in time_names:
            used_bindings[name] = {
                "granularity": time_names[name],
                "column": "mart_sales.dim_date.full_date",
            }
        elif name in bindings:
            used_bindings[name] = dict(bindings[name])
        else:
            raise SemanticCertificationError(
                "业务字段没有认证映射:" + sha256(name.encode()).hexdigest()[:12]
            )
    for predicate in conditions.aggregate_filters:
        if predicate.metric not in canonical_metrics:
            raise SemanticCertificationError("聚合筛选指标未选择")
    orders = conditions.order_by
    if conditions.row_limit is not None and not orders:
        raise SemanticCertificationError("排名条件缺少明确排序依据")
    if orders:
        if any(item.target not in {*targets, *canonical_metrics} for item in orders):
            raise SemanticCertificationError("排序对象不在业务输出中")
        for item in orders:
            expected_kind = (
                "metric"
                if item.target in canonical_metrics
                else "time"
                if item.target in time_names
                else "entity_field"
                if conditions.selection
                else "dimension"
            )
            if item.target_kind != expected_kind:
                raise SemanticCertificationError("排序对象类型不符")
    column_facts = {
        f"{c['schema_name']}.{c['table_name']}.{c['column_name']}": c["data_type"]
        for c in facts["columns"]
    }
    used_columns = {value["column"] for value in used_bindings.values()}
    for metric in metrics:
        formula = parse_one(metric["formula"], read="postgres")
        for column in formula.find_all(exp.Column):
            used_columns.add(metric["data_source"] + "." + column.name)
        for text in metric["filters"]:
            for column in parse_one(text, read="postgres").find_all(exp.Column):
                used_columns.add(metric["data_source"] + "." + column.name)
    if semantic.time is not None or any(name in time_names for name in targets):
        used_columns.update(
            {
                "mart_sales.fct_sales_order_line.completion_date_key",
                "mart_sales.dim_date.date_key",
                "mart_sales.dim_date.full_date",
            }
        )
    for qualified in used_columns:
        table, column = qualified.rsplit(".", 1)
        if (
            table not in context.allowed_tables
            or column not in context.allowed_columns.get(table, ())
            or qualified not in column_facts
            or column_facts[qualified] == "UNKNOWN"
        ):
            raise SemanticCertificationError("物理引用不在当前认证闭包")
    used_tables = {column.rsplit(".", 1)[0] for column in used_columns}
    used_tables.update(metric["data_source"] for metric in metrics)
    if not used_tables.issubset(context.allowed_tables):
        raise SemanticCertificationError("指标来源不在当前认证闭包")
    joins = [
        {
            **asdict(c),
            "source_columns": list(c.source_columns),
            "target_columns": list(c.target_columns),
        }
        for c in context.join_constraints
        if c.source_table in used_tables and c.target_table in used_tables
    ]
    for join in joins:
        for side in ("source", "target"):
            for column in join[f"{side}_columns"]:
                qualified = join[f"{side}_table"] + "." + column
                if (
                    qualified not in column_facts
                    or column_facts[qualified] == "UNKNOWN"
                ):
                    raise SemanticCertificationError("连接字段无法认证")
                used_columns.add(qualified)
    joins.sort(key=lambda item: json.dumps(item, sort_keys=True))
    certificate = {
        "state_version": 1,
        "semantic_query": json.loads(_semantic_query_json(semantic)),
        "provenance": {
            "metrics": metrics,
            "bindings": used_bindings,
            "columns": {c: column_facts[c] for c in sorted(used_columns)},
            "joins": joins,
        },
    }
    return semantic, certificate


def validate_restoration_sql(
    sql: str, semantic: ValidatedSemanticQuery, certificate: dict, context: QueryContext
) -> None:
    """只核对候选；不从候选SQL生成业务条件或认证身份。"""
    statement = parse_one(sql, read="postgres")
    if not isinstance(statement, exp.Select) or any(
        statement.find(node)
        for node in (exp.Subquery, exp.Window, exp.With, exp.SetOperation)
    ):
        raise SemanticSQLMismatch("SQL形态未表达已认证业务条件")
    allowed_args = {
        "expressions",
        "from_",
        "joins",
        "where",
        "group",
        "having",
        "order",
        "limit",
        "distinct",
    }
    if any(value and key not in allowed_args for key, value in statement.args.items()):
        raise SemanticSQLMismatch("SQL包含未认证的结果修饰条件")
    if any(table.args.get("sample") for table in statement.find_all(exp.Table)):
        raise SemanticSQLMismatch("SQL不能抽样已认证数据")
    aliases = _table_bindings(statement)

    def canonical(node):
        return _canonical_expression_sql(
            _normalize_numbers(node), bindings=aliases, context=context
        )

    provenance = certificate["provenance"]
    metric_expressions = {}
    fixed = set()
    for metric in provenance["metrics"]:

        def expected(text, metric=metric):
            return _canonical_expression_sql(
                _normalize_numbers(parse_one(text, read="postgres")),
                bindings={},
                context=context,
                default_table=metric["data_source"],
                aliases_are_default=True,
            )

        metric_expressions[metric["name"]] = expected(metric["formula"])
        fixed.update(expected(text) for text in metric["filters"])
    dimension_expressions = {
        name: value["column"]
        for name, value in provenance["bindings"].items()
        if "granularity" not in value
    }
    conditions = semantic.restoration_conditions
    assert conditions is not None
    projections = [
        node.this if isinstance(node, exp.Alias) else node
        for node in statement.expressions
    ]
    signatures = [canonical(node) for node in projections]
    output_aliases = {
        node.alias: signature
        for node, signature in zip(statement.expressions, signatures)
        if node.alias
    }
    requested = list(
        conditions.selection.fields if conditions.selection else semantic.dimensions
    )
    expected_signatures = set(metric_expressions.values()) | {
        dimension_expressions[n] for n in requested if n in dimension_expressions
    }
    time_targets = {
        name: value["granularity"]
        for name, value in provenance["bindings"].items()
        if "granularity" in value and name in requested
    }
    time_signatures = set()
    for name, grain in time_targets.items():
        parts = {
            calendar_part(node, canonical): canonical(node)
            for node in projections
            if calendar_part(node, canonical)
        }
        if f"period:{grain}" in parts:
            time_signatures.add(parts[f"period:{grain}"])
            dimension_expressions[name] = parts[f"period:{grain}"]
        elif "year" in parts and (grain == "year" or grain in parts):
            time_signatures.add(parts["year"])
            if grain != "year":
                time_signatures.add(parts[grain])
            dimension_expressions[name] = (
                (parts["year"], parts[grain]) if grain != "year" else parts["year"]
            )
        else:
            raise SemanticSQLMismatch("时间分组缺少完整时期身份")
    if set(signatures) != expected_signatures | time_signatures or len(
        set(signatures)
    ) != len(signatures):
        raise SemanticSQLMismatch("SQL输出与业务选择不同")
    grouped = statement.args.get("group")
    group_signatures = (
        {canonical(node) for node in grouped.expressions} if grouped else set()
    )
    expected_group = (
        {dimension_expressions[n] for n in requested if n not in time_targets}
        | time_signatures
        if not conditions.selection
        else set()
    )
    if group_signatures != expected_group:
        raise SemanticSQLMismatch("SQL分组不同")
    if bool(statement.args.get("distinct")) != bool(
        conditions.selection and conditions.selection.distinct
    ):
        raise SemanticSQLMismatch("实体去重条件不同")
    distinct = statement.args.get("distinct")
    if distinct is not None and distinct.args.get("on") is not None:
        raise SemanticSQLMismatch("实体去重不能指定额外子集")
    where = statement.args.get("where")
    predicates = _multi_conjuncts(where.this if where else None)
    consumed = set()
    if semantic.time is not None:
        role = completion_date_role(statement, provenance["metrics"], aliases, context)
        bounds, consumed = actual_date_range(predicates, aliases, context, role)
        if bounds is None or (bounds["start"], bounds["end_exclusive"]) != (
            semantic.time.start.date().isoformat(),
            semantic.time.end.date().isoformat(),
        ):
            raise SemanticSQLMismatch("SQL时间范围不同")
    expected_where = set(fixed)
    for predicate in semantic.filters:
        binding = provenance["bindings"][predicate.field_text]
        column = binding["column"]
        values = tuple(
            binding.get("value_aliases", {}).get(value, value)
            for value in predicate.values
        )
        expected_where.add(
            _predicate(
                column,
                predicate.operator.value,
                values,
                numeric=provenance["columns"][column]
                in {
                    "integer",
                    "bigint",
                    "smallint",
                    "numeric",
                    "double precision",
                    "real",
                },
            )
        )
    if {
        canonical(node) for i, node in enumerate(predicates) if i not in consumed
    } != expected_where:
        raise SemanticSQLMismatch("SQL行筛选或固定口径不同")
    having = statement.args.get("having")
    actual_having = {
        canonical(node) for node in _multi_conjuncts(having.this if having else None)
    }
    expected_having = {
        _predicate(
            metric_expressions[item.metric], item.operator, item.values, numeric=True
        )
        for item in conditions.aggregate_filters
    }
    if actual_having != expected_having:
        raise SemanticSQLMismatch("聚合后条件不同")
    order = statement.args.get("order")
    actual_orders = []
    for item in order.expressions if order else ():
        node = item.this
        signature = (
            output_aliases.get(node.name)
            if isinstance(node, exp.Column) and not node.table
            else None
        )
        signature = signature or canonical(node)
        actual_orders.append(
            (signature, bool(item.args.get("desc")), bool(item.args.get("nulls_first")))
        )
    effective_orders = list(conditions.order_by)
    if not effective_orders and conditions.row_limit is None:
        kind = "entity_field" if conditions.selection else "dimension"
        effective_orders.extend(
            BusinessOrder("time" if name in time_targets else kind, name, "asc", "last")
            for name in requested
        )
    if conditions.row_limit is not None:
        ordered_targets = {item.target for item in effective_orders}
        kind = "entity_field" if conditions.selection else "dimension"
        effective_orders.extend(
            BusinessOrder("time" if name in time_targets else kind, name, "asc", "last")
            for name in requested
            if name not in ordered_targets
        )
    expected_orders = []
    for item in effective_orders:
        signature = metric_expressions.get(
            item.target, dimension_expressions.get(item.target)
        )
        signatures_for_target = (
            signature if isinstance(signature, tuple) else (signature,)
        )
        expected_orders.extend(
            (signature, item.direction == "desc", item.nulls == "first")
            for signature in signatures_for_target
        )
    if actual_orders != expected_orders:
        raise SemanticSQLMismatch("SQL排序不同")
    limit = statement.args.get("limit")
    actual_limit = (
        int(limit.expression.this)
        if limit
        and isinstance(limit.expression, exp.Literal)
        and not limit.expression.is_string
        else None
    )
    if actual_limit != conditions.row_limit or (
        limit is not None and actual_limit is None
    ):
        raise SemanticSQLMismatch("SQL业务数量不同")
    if statement.args.get("offset") is not None:
        raise SemanticSQLMismatch("SQL包含未确认偏移")


def _predicate(expression, operator, values, *, numeric):
    def literal(value):
        return exp.Literal.number(value) if numeric else exp.Literal.string(value)

    left = parse_one(expression, read="postgres")
    types = {
        "equals": exp.EQ,
        "gt": exp.GT,
        "gte": exp.GTE,
        "lt": exp.LT,
        "lte": exp.LTE,
    }
    node = (
        exp.In(this=left, expressions=[literal(v) for v in values])
        if operator == "in"
        else types[operator](this=left, expression=literal(values[0]))
    )
    return _normalize_numbers(node).sql(dialect="postgres", normalize=True)


def _normalize_numbers(node):
    def normalize(value):
        if isinstance(value, exp.Literal) and not value.is_string:
            number = Decimal(value.this)
            return exp.Literal.number(format(number.normalize(), "f"))
        return value

    return node.transform(normalize)


def _dependency_definitions(record, available, path):
    result = {}
    for name in sorted(record.get("depends_on", ())):
        matches = [m for m in available if m.get("name", m.get("metric_name")) == name]
        if len(matches) != 1 or name in path:
            raise SemanticCertificationError("指标依赖定义缺失或循环")
        dependency = matches[0]
        result[name] = {
            "formula": parse_one(dependency["formula"], read="postgres").sql(
                dialect="postgres", normalize=True
            ),
            "data_source": dependency["data_source"],
            "time_field": dependency["time_field"],
            "filters": sorted(
                parse_one(text, read="postgres").sql(dialect="postgres", normalize=True)
                for text in dependency["filters"]
            ),
            "dependencies": _dependency_definitions(
                dependency, available, path | {name}
            ),
        }
    return result
