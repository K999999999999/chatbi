"""历史查询的完整业务条件；不包含SQL、持久化或Provider类型。"""

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation


class RestorationConditionError(ValueError):
    """候选条件结构非法，不能进入业务认证。"""


@dataclass(frozen=True, slots=True)
class BusinessOrder:
    target_kind: str
    target: str
    direction: str
    nulls: str


@dataclass(frozen=True, slots=True)
class AggregateFilter:
    metric: str
    operator: str
    values: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EntitySelection:
    fields: tuple[str, ...]
    distinct: bool


@dataclass(frozen=True, slots=True)
class RestorationConditions:
    order_by: tuple[BusinessOrder, ...]
    row_limit: int | None
    aggregate_filters: tuple[AggregateFilter, ...]
    selection: EntitySelection | None

    def to_payload(self) -> dict:
        """JSON编码器可直接编码的完整对象。"""
        return asdict(self)


def revision_operations_from_payload(payload: object) -> dict:
    names = {
        "order_operation": "order_by",
        "limit_operation": "row_limit",
        "aggregate_filter_operation": "aggregate_filters",
        "selection_operation": "selection",
    }
    operations = _object(payload, set(names))
    result = {}
    for name, field in names.items():
        value = operations[name]
        if not isinstance(value, Mapping):
            raise RestorationConditionError("修订操作非法")
        operation = _choice(value.get("operation"), {"keep", "set", "clear"})
        expected = {"operation", "value"} if operation == "set" else {"operation"}
        _object(value, expected)
        if operation == "set":
            full = {
                "order_by": [],
                "row_limit": None,
                "aggregate_filters": [],
                "selection": None,
            }
            full[field] = value["value"]
            parsed = conditions_from_payload(full)
            changed = getattr(parsed, field)
            if changed is None or changed == ():
                raise RestorationConditionError("set必须给出完整非空值，取消使用clear")
            result[field] = (operation, changed)
        else:
            result[field] = (operation, None)
    return result


def conditions_from_payload(payload: object) -> RestorationConditions:
    value = _object(
        payload, {"order_by", "row_limit", "aggregate_filters", "selection"}
    )
    limit = value["row_limit"]
    if limit is not None and (type(limit) is not int or not 1 <= limit <= 2**63 - 1):
        raise RestorationConditionError("业务数量必须为正整数")
    orders = []
    for item in _array(value["order_by"]):
        order = _object(item, {"target_kind", "target", "direction", "nulls"})
        kind = _choice(
            order["target_kind"], {"metric", "dimension", "entity_field", "time"}
        )
        orders.append(
            BusinessOrder(
                kind,
                _text(order["target"]),
                _choice(order["direction"], {"asc", "desc"}),
                _choice(order["nulls"], {"first", "last"}),
            )
        )
    identities = [(item.target_kind, item.target) for item in orders]
    if len(set(identities)) != len(identities):
        raise RestorationConditionError("排序对象不能重复")
    aggregate_filters = []
    for item in _array(value["aggregate_filters"]):
        predicate = _object(item, {"metric", "operator", "values"})
        operator = _choice(
            predicate["operator"], {"equals", "in", "gt", "gte", "lt", "lte"}
        )
        values = tuple(_decimal(v) for v in _array(predicate["values"]))
        if not values or (operator != "in" and len(values) != 1):
            raise RestorationConditionError("聚合筛选值数量非法")
        aggregate_filters.append(
            AggregateFilter(_text(predicate["metric"]), operator, values)
        )
    if len({item.metric for item in aggregate_filters}) != len(aggregate_filters):
        raise RestorationConditionError("聚合筛选指标不能重复")
    selection = None
    if value["selection"] is not None:
        selected = _object(value["selection"], {"fields", "distinct"})
        fields = tuple(_text(v) for v in _array(selected["fields"]))
        if (
            not fields
            or len(set(fields)) != len(fields)
            or type(selected["distinct"]) is not bool
        ):
            raise RestorationConditionError("实体选择非法")
        selection = EntitySelection(fields, selected["distinct"])
    return RestorationConditions(
        tuple(orders), limit, tuple(aggregate_filters), selection
    )


def _object(value: object, keys: set[str]) -> Mapping:
    if not isinstance(value, Mapping) or set(value) != keys:
        raise RestorationConditionError("恢复条件字段不完整或包含未知字段")
    return value


def _array(value: object) -> list:
    if not isinstance(value, list) or len(value) > 100:
        raise RestorationConditionError("恢复条件必须为有界数组")
    return value


def _text(value: object) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 200:
        raise RestorationConditionError("业务身份必须为有效文本")
    return value.strip()


def _choice(value: object, choices: set[str]) -> str:
    if not isinstance(value, str) or value not in choices:
        raise RestorationConditionError("恢复条件枚举非法")
    return value


def _decimal(value: object) -> str:
    text = _text(value)
    try:
        number = Decimal(text)
    except InvalidOperation as exc:
        raise RestorationConditionError("聚合筛选须为十进制文本") from exc
    if not number.is_finite():
        raise RestorationConditionError("聚合筛选须为有限数值")
    return text
