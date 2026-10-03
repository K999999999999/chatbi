"""从已认证的完成日期角色提取实际范围和时间键，不推测缺失年份。"""

from datetime import date, timedelta

from sqlglot import exp, parse_one

from .sql_guard.sql_guard_scope import _column_identity


def literal(node):
    if isinstance(node, exp.Cast):
        node = node.this
    if isinstance(node, exp.Literal):
        return node.this
    return None


def _physical(node, bindings, context):
    if not isinstance(node, exp.Column):
        return None
    try:
        table, name = _column_identity(node, bindings, context)
        return f"{table}.{name}"
    except Exception:
        return None


def completion_date_role(statement, metrics, bindings, context):
    if not metrics or {m.get("time_field") for m in metrics} != {
        "fct_sales_order_line.completion_date_key -> dim_date.full_date"
    }:
        return False
    required = {
        "mart_sales.fct_sales_order_line.completion_date_key",
        "mart_sales.dim_date.date_key",
    }
    for join in statement.args.get("joins", []):
        condition = join.args.get("on")
        if (
            isinstance(condition, exp.EQ)
            and {
                _physical(condition.left, bindings, context),
                _physical(condition.right, bindings, context),
            }
            == required
        ):
            return True
    return False


def calendar_part(node, canonical):
    signature = canonical(node)

    def expected_signature(text):
        return parse_one(text, read="postgres").sql(dialect="postgres", normalize=True)

    for part in ("year", "month", "quarter"):
        if signature == f"mart_sales.dim_date.{part}":
            return part
        expected = expected_signature(
            f"EXTRACT({part} FROM mart_sales.dim_date.full_date)"
        )
        if signature == expected:
            return part
    if signature == "mart_sales.dim_date.full_date":
        return "period:day"
    for grain, pattern in (("month", "YYYY-MM"), ("year", "YYYY")):
        for text in (
            f"DATE_TRUNC('{grain}', mart_sales.dim_date.full_date)",
            f"TO_CHAR(mart_sales.dim_date.full_date, '{pattern}')",
        ):
            if signature == expected_signature(text):
                return "period:" + grain
    if signature == expected_signature(
        "DATE_TRUNC('quarter', mart_sales.dim_date.full_date)"
    ):
        return "period:quarter"
    return None


def actual_date_range(predicates, bindings, context, role):
    if not role:
        return None, set()
    consumed = set()
    values = {}
    lower, upper = None, None
    for index, predicate in enumerate(predicates):
        if (
            isinstance(predicate, exp.Between)
            and _physical(predicate.this, bindings, context)
            == "mart_sales.dim_date.full_date"
        ):
            try:
                start = date.fromisoformat(literal(predicate.args["low"]))
                end = date.fromisoformat(literal(predicate.args["high"])) + timedelta(
                    days=1
                )
                lower = max(lower, start) if lower else start
                upper = min(upper, end) if upper else end
                consumed.add(index)
            except (ValueError, TypeError, OverflowError):
                continue
        if not isinstance(predicate, (exp.EQ, exp.GTE, exp.GT, exp.LT, exp.LTE)):
            continue
        physical = _physical(predicate.left, bindings, context)
        value = literal(predicate.right)
        if value is None:
            continue
        if physical in {
            "mart_sales.dim_date.year",
            "mart_sales.dim_date.month",
            "mart_sales.dim_date.quarter",
        } and isinstance(predicate, exp.EQ):
            name = physical.rsplit(".", 1)[1]
            if name in values:
                return None, set()
            try:
                values[name] = int(value)
                consumed.add(index)
            except ValueError:
                continue
        if physical == "mart_sales.dim_date.full_date":
            try:
                boundary = date.fromisoformat(value)
                if isinstance(predicate, exp.EQ):
                    start, end = boundary, boundary + timedelta(days=1)
                elif isinstance(predicate, (exp.GTE, exp.GT)):
                    start, end = (
                        boundary + timedelta(days=int(isinstance(predicate, exp.GT))),
                        None,
                    )
                else:
                    start, end = (
                        None,
                        boundary + timedelta(days=int(isinstance(predicate, exp.LTE))),
                    )
                if start:
                    lower = max(lower, start) if lower else start
                if end:
                    upper = min(upper, end) if upper else end
                consumed.add(index)
            except (ValueError, TypeError, OverflowError):
                continue
    if values:
        try:
            year = values["year"]
            if "month" in values:
                month = values["month"]
                if "quarter" in values and (month - 1) // 3 + 1 != values["quarter"]:
                    return None, set()
                start = date(year, month, 1)
                end = date(year + int(month == 12), month % 12 + 1, 1)
            elif "quarter" in values:
                quarter = values["quarter"]
                if not 1 <= quarter <= 4:
                    return None, set()
                start = date(year, (quarter - 1) * 3 + 1, 1)
                end = date(
                    year + int(quarter == 4), quarter * 3 + 1 if quarter < 4 else 1, 1
                )
            else:
                start, end = date(year, 1, 1), date(year + 1, 1, 1)
            lower = max(lower, start) if lower else start
            upper = min(upper, end) if upper else end
        except (KeyError, ValueError, OverflowError):
            return None, set()
    if lower is None or upper is None or lower >= upper:
        return None, set()
    return dict(
        start=lower.isoformat(),
        end_exclusive=upper.isoformat(),
        time_basis="订单完成日期",
    ), consumed


def time_keys(parts, rows, period):
    names = {kind for _, kind in parts}
    grain = "month" if "month" in names else "quarter" if "quarter" in names else "year"
    encoded = [part for part in parts if part[1].startswith("period:")]
    if encoded:
        if len(encoded) != 1:
            return None
        grain = encoded[0][1].split(":")[1]
    fixed_year = None
    if period:
        first, last = (
            date.fromisoformat(period["start"]),
            date.fromisoformat(period["end_exclusive"]) - timedelta(days=1),
        )
        if first.year == last.year:
            fixed_year = first.year
    keys = []
    for row in rows:
        try:
            if encoded:
                value = str(row[encoded[0][0]])
                if grain == "year" and len(value) == 4:
                    value += "-01-01"
                elif grain == "month" and len(value) == 7:
                    value += "-01"
                key = date.fromisoformat(value[:10])
            else:
                numbers = {name: int(row[index]) for index, name in parts}
                if any(str(row[index]) != str(numbers[name]) for index, name in parts):
                    return None
                year = numbers.get("year", fixed_year)
                month = numbers.get("month", (numbers.get("quarter", 1) - 1) * 3 + 1)
                if "quarter" in numbers and not 1 <= numbers["quarter"] <= 4:
                    return None
                key = date(year, month, 1)
            if period and not (
                period["start"] <= key.isoformat() < period["end_exclusive"]
            ):
                return None
            keys.append(key.isoformat())
        except (ValueError, TypeError, OverflowError):
            return None
    return dict(granularity=grain, keys=keys)
