"""认证本次实际SQL的显示事实；认证失败仅降级，不裁决业务查询。"""

from sqlglot import exp, parse_one

from src.semantic.result_display import load_display_facts

from .contracts import QueryContext, QueryData, ValidatedSQL
from .query_understanding import ValidatedSemanticQuery
from .result_contracts import ResultMetadata
from .result_time import (
    actual_date_range,
    calendar_part,
    completion_date_role,
    literal,
    time_keys,
)
from .sql_guard.sql_guard_scope import (
    _canonical_expression_sql,
    _column_identity,
    _multi_conjuncts,
    _table_bindings,
)


def _unknown(index: int, name: str) -> dict:
    return dict(
        index=index,
        name=name,
        data_type="unknown",
        role="unknown",
        semantic_name=None,
        definition=None,
        unit=None,
        format="raw",
        certified=False,
        reason_code="SEMANTICS_UNCONFIRMED",
    )


def build_result_metadata(
    sql: ValidatedSQL,
    data: QueryData,
    context: QueryContext,
    semantic: ValidatedSemanticQuery | None,
) -> ResultMetadata:
    columns = [_unknown(i, name) for i, name in enumerate(data.columns)]
    scope = dict(
        status="unavailable",
        time=None,
        time_status="unknown",
        filters=[],
        grouping=[],
        warnings=["SCOPE_UNCONFIRMED"],
    )
    payload = dict(
        version=1, status="unavailable", columns=columns, scope=scope, time_axis=None
    )
    try:
        _certify(payload, sql.sql, data, context, semantic)
    except Exception:
        # 元数据不改变查询成功语义；异常与内部来源不公开。
        return ResultMetadata.from_payload(
            dict(
                version=1,
                status="unavailable",
                columns=[_unknown(i, name) for i, name in enumerate(data.columns)],
                scope=dict(
                    status="unavailable",
                    time=None,
                    time_status="unknown",
                    filters=[],
                    grouping=[],
                    warnings=["SCOPE_UNCONFIRMED"],
                ),
                time_axis=None,
            )
        )
    return ResultMetadata.from_payload(payload)


def _certify(payload, sql, data, context, semantic):
    if semantic is None:
        return
    statement = parse_one(sql, read="postgres")
    if not isinstance(statement, exp.Select) or any(
        statement.find(t)
        for t in (exp.Subquery, exp.Window, exp.With, exp.SetOperation)
    ):
        return
    projections = [
        p.this if isinstance(p, exp.Alias) else p for p in statement.expressions
    ]
    if len(projections) != len(data.columns) or any(
        p.find(exp.Star) and not p.find(exp.Count) for p in projections
    ):
        return
    metrics, traits, _ = load_display_facts()
    bindings = _table_bindings(statement)

    def canonical(node):
        return _canonical_expression_sql(node, bindings=bindings, context=context)

    predicates = _multi_conjuncts(
        statement.args.get("where").this if statement.args.get("where") else None
    )
    actual_filters = {canonical(p) for p in predicates}
    requested = [
        m
        for m in metrics
        if any(n in {m["name"], *m.get("aliases", [])} for n in semantic.metrics)
    ]
    candidates = []
    for metric in requested:
        try:

            def normal(text):
                return _canonical_expression_sql(
                    parse_one(text, read="postgres"),
                    bindings={},
                    context=context,
                    default_table=metric["data_source"],
                    aliases_are_default=True,
                )

            formula = normal(metric["formula"])
            fixed = {normal(f) for f in metric["filters"]}
            if fixed.issubset(actual_filters):
                candidates.append((metric, formula))
        except Exception:
            continue
    matched_filters = set()
    matched_metrics = []
    for index, projection in enumerate(projections):
        try:
            signature = canonical(projection)
            matches = [m for m, formula in candidates if signature == formula]
            column = payload["columns"][index]
            if len(matches) == 1:
                m = matches[0]
                trait = traits["metrics"].get(m["name"])
                if trait is not None:
                    column.update(
                        data_type="number",
                        role="metric",
                        semantic_name=m["name"],
                        definition=m["definition"],
                        unit=trait["unit"],
                        format=trait["format"],
                        certified=True,
                        reason_code=None,
                    )
                    matched_metrics.append(m)
                    matched_filters.update(
                        canonical(
                            parse_one(
                                f.replace("f.", m["data_source"] + "."), read="postgres"
                            )
                        )
                        for f in m["filters"]
                    )
            elif isinstance(projection, exp.Column):
                table, name = _column_identity(projection, bindings, context)
                physical = f"{table}.{name}"
                matches = [
                    n
                    for n, value in traits["dimensions"].items()
                    if value["column"] == physical and n in semantic.dimensions
                ]
                if len(matches) == 1:
                    column.update(
                        data_type="string",
                        role="dimension",
                        semantic_name=matches[0],
                        format="raw",
                        certified=True,
                        reason_code=None,
                    )
        except Exception:
            continue
    group = statement.args.get("group")
    group_signatures = set()
    for expression in group.expressions if group else ():
        if isinstance(expression, exp.Literal) and expression.is_int:
            ordinal = int(expression.this)
            if not 1 <= ordinal <= len(projections):
                return
            expression = projections[ordinal - 1]
        elif isinstance(expression, exp.Column) and not expression.table:
            aliases = [
                p.this
                for p in statement.expressions
                if isinstance(p, exp.Alias)
                and p.alias.casefold() == expression.name.casefold()
            ]
            if len(aliases) == 1:
                expression = aliases[0]
        group_signatures.add(canonical(expression))
    grouping = []
    covered = set()
    for column, projection in zip(payload["columns"], projections, strict=True):
        if column["role"] == "dimension" and canonical(projection) in group_signatures:
            grouping.append(
                dict(
                    semantic_name=column["semantic_name"],
                    kind="category",
                    column_indices=[column["index"]],
                )
            )
            covered.add(canonical(projection))
    scope = payload["scope"]
    role = completion_date_role(statement, matched_metrics, bindings, context)
    period, consumed = actual_date_range(predicates, bindings, context, role)
    scope.update(time=period, time_status="confirmed" if period else "unknown")
    if (
        semantic.time is not None
        and period
        and (
            period["start"] != semantic.time.start.date().isoformat()
            or period["end_exclusive"] != semantic.time.end.date().isoformat()
        )
    ):
        scope.update(time=None, time_status="unknown")
        consumed = set()
    parts = []
    if role:
        for index, projection in enumerate(projections):
            if canonical(projection) in group_signatures:
                part = calendar_part(projection, canonical)
                if part:
                    parts.append((index, part))
        if parts:
            axis = time_keys(parts, data.rows, period)
            names = {"month": "月份", "quarter": "季度", "year": "年份", "day": "日期"}
            if axis and names[axis["granularity"]] in semantic.dimensions:
                payload["time_axis"] = axis
                grouping.append(
                    dict(
                        semantic_name=names[axis["granularity"]],
                        kind="time",
                        column_indices=[i for i, _ in parts],
                    )
                )
                for index, part in parts:
                    payload["columns"][index].update(
                        data_type="date" if part.startswith("period:") else "number",
                        role="dimension",
                        semantic_name=names.get(part, names[axis["granularity"]]),
                        certified=True,
                        reason_code=None,
                    )
                    covered.add(canonical(projections[index]))
    scope["grouping"] = grouping
    scope["status"] = "partial"
    remaining = []
    for index, predicate in enumerate(predicates):
        if canonical(predicate) in matched_filters or index in consumed:
            continue
        item = _filter(predicate, traits, bindings, context)
        if item:
            scope["filters"].append(item)
        else:
            remaining.append(predicate)
    if not period and not remaining and semantic.time is None:
        scope["time_status"] = "unbounded"
    if not remaining and scope["time_status"] != "unknown":
        scope.update(status="complete", warnings=[])
    if covered != group_signatures:
        scope["warnings"].append("GROUPING_UNCONFIRMED")
        scope["status"] = "partial"
    if statement.args.get("having") is not None:
        scope["warnings"].append("HAVING_UNCONFIRMED")
        scope["status"] = "partial"
    known = sum(c["certified"] for c in payload["columns"])
    payload["status"] = (
        "complete"
        if known == len(projections) and scope["status"] == "complete"
        else "partial"
        if known
        else "unavailable"
    )


def _filter(predicate, traits, bindings, context):
    operators = {exp.EQ: "=", exp.GT: ">", exp.GTE: ">=", exp.LT: "<", exp.LTE: "<="}
    if type(predicate) not in operators and not isinstance(predicate, exp.In):
        return None
    node = predicate.this if isinstance(predicate, exp.In) else predicate.left
    if not isinstance(node, exp.Column):
        return None
    try:
        table, name = _column_identity(node, bindings, context)
        matches = [
            label
            for label, value in traits["dimensions"].items()
            if value["column"] == f"{table}.{name}"
        ]
        if len(matches) != 1:
            return None
        values = (
            [literal(n) for n in predicate.expressions]
            if isinstance(predicate, exp.In)
            else [literal(predicate.right)]
        )
        if not values or any(v is None for v in values):
            return None
        return dict(
            label=matches[0],
            operator="IN"
            if isinstance(predicate, exp.In)
            else operators[type(predicate)],
            values=values,
        )
    except Exception:
        return None
