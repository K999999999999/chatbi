"""Query Understanding（查询理解）的结构 Contract 和确定性校验。"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime, timedelta, time as datetime_time
from enum import StrEnum
import re
from typing import Final
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


DEFAULT_QUERY_TIMEZONE: Final = "Asia/Shanghai"
MAX_REQUEST_METRICS: Final = 5

_CANDIDATE_FIELDS = frozenset(
    {"query_type", "subjects", "metrics", "dimensions", "time", "filters"}
)
_TIME_FIELDS = frozenset({"text", "granularity"})
_FILTER_FIELDS = frozenset({"field_text", "operator", "values"})
_RECENT_DAYS_PATTERN = re.compile(r"最近([1-9][0-9]*)天")
_RECENT_MONTHS_PATTERN = re.compile(r"最近([1-9][0-9]*|[一二三四五六七八九十百]+)个月")
_YEAR_PATTERN = re.compile(r"([0-9]{4})年?$")
_YEAR_MONTH_PATTERN = re.compile(r"([0-9]{4})(?:年([0-9]{1,2})月?|[-/]([0-9]{1,2}))$")
_YEAR_QUARTER_PATTERN = re.compile(
    r"(?P<year>[0-9]{4})(?:年?(?:第)?(?P<cn>[一二三四1-4])季度|年?[Qq](?P<q>[1-4]))$"
)
_DATE_PATTERN = re.compile(
    r"([0-9]{4})(?:年([0-9]{1,2})月([0-9]{1,2})日?|[-/]([0-9]{1,2})[-/]([0-9]{1,2}))$"
)
_DATE_RANGE_PATTERN = re.compile(r"(.+?)(?:至|到|~)(.+)$")
_CURRENT_CONTEXT_TIME_TEXTS = frozenset({"当前", "目前", "现在"})


class QueryType(StrEnum):
    """结构化查询的粗粒度类型。"""

    ENTITY_LOOKUP = "entity_lookup"
    METRIC_ANALYSIS = "metric_analysis"
    UNKNOWN = "unknown"


class TimeGranularity(StrEnum):
    """用户时间条件的粒度。"""

    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    QUARTER = "quarter"
    YEAR = "year"


class FilterOperator(StrEnum):
    """V1 用户过滤条件允许的操作符。"""

    EQUALS = "equals"
    IN = "in"
    GT = "gt"
    GTE = "gte"
    LT = "lt"
    LTE = "lte"


class SemanticQueryValidationError(ValueError):
    """结构或业务校验失败，并携带可观测的内部原因。"""

    def __init__(self, message: str, *, reason: str) -> None:
        super().__init__(message)
        self.reason = reason


class SemanticQueryStructureError(SemanticQueryValidationError):
    """结构化候选不符合 LLM 输出 Contract。"""


class SemanticQueryCannotAnswer(SemanticQueryValidationError):
    """结构合法，但业务语义不能可靠回答。"""


@dataclass(frozen=True, slots=True)
class TimeCandidate:
    text: str
    granularity: TimeGranularity


@dataclass(frozen=True, slots=True)
class FilterCandidate:
    field_text: str
    operator: FilterOperator
    values: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SemanticQueryCandidate:
    query_type: QueryType
    subjects: tuple[str, ...]
    metrics: tuple[str, ...]
    dimensions: tuple[str, ...]
    time: TimeCandidate | None
    filters: tuple[FilterCandidate, ...]


@dataclass(frozen=True, slots=True)
class ValidatedTime:
    text: str
    granularity: TimeGranularity
    start: datetime
    end: datetime


@dataclass(frozen=True, slots=True)
class ValidatedFilter:
    field_text: str
    operator: FilterOperator
    values: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ValidatedSemanticQuery:
    query_type: QueryType
    subjects: tuple[str, ...]
    metrics: tuple[str, ...]
    dimensions: tuple[str, ...]
    time: ValidatedTime | None
    filters: tuple[ValidatedFilter, ...]
    original_question: str


def candidate_from_payload(payload: Mapping[str, object]) -> SemanticQueryCandidate:
    """将一个结构化对象转换为严格的 Candidate Contract。"""

    if not isinstance(payload, Mapping):
        raise _structure("结构化查询必须是 JSON 对象", "CANDIDATE_NOT_OBJECT")

    fields = set(payload)
    missing = _CANDIDATE_FIELDS - fields
    extra = fields - _CANDIDATE_FIELDS
    if missing:
        missing_text = "、".join(sorted(str(field) for field in missing))
        raise _structure(
            f"结构化查询缺少字段：{missing_text}",
            "CANDIDATE_FIELD_MISSING",
        )
    if extra:
        extra_text = "、".join(sorted(str(field) for field in extra))
        raise _structure(
            f"结构化查询包含未允许字段：{extra_text}",
            "CANDIDATE_FIELD_EXTRA",
        )

    query_type = _enum_value(payload["query_type"], QueryType, "query_type")
    subjects = _string_list(payload["subjects"], "subjects")
    metrics = _string_list(payload["metrics"], "metrics")
    dimensions = _string_list(payload["dimensions"], "dimensions")
    time_candidate = _time_candidate(payload["time"])
    filters = _filter_candidates(payload["filters"])
    return SemanticQueryCandidate(
        query_type=query_type,
        subjects=subjects,
        metrics=metrics,
        dimensions=dimensions,
        time=time_candidate,
        filters=filters,
    )


def validate_candidate(
    candidate: SemanticQueryCandidate,
    *,
    original_question: str,
    now: datetime | None = None,
    timezone_name: str = DEFAULT_QUERY_TIMEZONE,
) -> ValidatedSemanticQuery:
    """校验候选并生成不含未授权物理资源的 ValidatedSemanticQuery。"""

    if not isinstance(candidate, SemanticQueryCandidate):
        raise _structure("查询候选类型无效", "CANDIDATE_TYPE_INVALID")
    if not isinstance(original_question, str) or not original_question.strip():
        raise _structure("原始查询问题不能为空", "ORIGINAL_QUESTION_INVALID")

    if candidate.query_type is QueryType.UNKNOWN:
        raise _cannot_answer(
            "无法确定查询类型",
            "QUERY_TYPE_UNKNOWN",
        )
    if candidate.query_type is QueryType.ENTITY_LOOKUP:
        if not candidate.subjects:
            raise _cannot_answer(
                "实体查询缺少业务主题",
                "SUBJECT_REQUIRED",
            )
        if candidate.metrics:
            raise _cannot_answer(
                "实体查询不能同时携带指标",
                "ENTITY_METRICS_CONFLICT",
            )
    elif not candidate.metrics:
        raise _cannot_answer(
            "指标分析查询缺少指标",
            "METRIC_REQUIRED",
        )

    if len(candidate.metrics) > MAX_REQUEST_METRICS:
        raise _cannot_answer(
            f"单次查询最多支持 {MAX_REQUEST_METRICS} 个指标",
            "METRIC_LIMIT_EXCEEDED",
        )

    validated_time: ValidatedTime | None = None
    if candidate.time is not None and not _is_current_context_time(candidate.time):
        validated_time = _validate_time(
            candidate.time,
            now=now,
            timezone_name=timezone_name,
        )
    validated_filters = tuple(
        ValidatedFilter(
            field_text=item.field_text,
            operator=item.operator,
            values=item.values,
        )
        for item in candidate.filters
    )
    return ValidatedSemanticQuery(
        query_type=candidate.query_type,
        subjects=candidate.subjects,
        metrics=candidate.metrics,
        dimensions=candidate.dimensions,
        time=validated_time,
        filters=validated_filters,
        original_question=original_question.strip(),
    )


def _is_current_context_time(candidate: TimeCandidate) -> bool:
    """把 LLM 误放进 time 的当前状态词还原为无时间过滤。"""

    compact_text = re.sub(r"\s+", "", candidate.text.strip())
    return compact_text in _CURRENT_CONTEXT_TIME_TEXTS


def _time_candidate(value: object) -> TimeCandidate | None:
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise _structure("time 必须是对象或 null", "TIME_TYPE_INVALID")
    fields = set(value)
    missing = _TIME_FIELDS - fields
    extra = fields - _TIME_FIELDS
    if missing:
        raise _structure("time 缺少必要字段", "TIME_FIELD_MISSING")
    if extra:
        raise _structure("time 包含未允许字段", "TIME_FIELD_EXTRA")
    text = _required_text(value["text"], "time.text")
    granularity = _enum_value(
        value["granularity"],
        TimeGranularity,
        "time.granularity",
    )
    return TimeCandidate(text=text, granularity=granularity)


def _filter_candidates(value: object) -> tuple[FilterCandidate, ...]:
    if not isinstance(value, list):
        raise _structure("filters 必须是数组", "FILTERS_TYPE_INVALID")
    result: list[FilterCandidate] = []
    for index, raw_item in enumerate(value, 1):
        if not isinstance(raw_item, Mapping):
            raise _structure(
                f"第 {index} 个 filter 必须是对象",
                "FILTER_TYPE_INVALID",
            )
        fields = set(raw_item)
        missing = _FILTER_FIELDS - fields
        extra = fields - _FILTER_FIELDS
        if missing:
            raise _structure(
                f"第 {index} 个 filter 缺少必要字段",
                "FILTER_FIELD_MISSING",
            )
        if extra:
            raise _structure(
                f"第 {index} 个 filter 包含未允许字段",
                "FILTER_FIELD_EXTRA",
            )
        field_text = _required_text(raw_item["field_text"], "filter.field_text")
        operator = _enum_value(
            raw_item["operator"],
            FilterOperator,
            "filter.operator",
        )
        values = _string_list(raw_item["values"], "filter.values")
        if not values:
            raise _structure(
                f"第 {index} 个 filter 的 values 不能为空",
                "FILTER_VALUES_EMPTY",
            )
        if operator is not FilterOperator.IN and len(values) != 1:
            raise _structure(
                f"操作符 {operator.value} 必须恰好包含一个值",
                "FILTER_VALUE_CARDINALITY_INVALID",
            )
        result.append(
            FilterCandidate(
                field_text=field_text,
                operator=operator,
                values=values,
            )
        )
    return tuple(result)


def _validate_time(
    candidate: TimeCandidate,
    *,
    now: datetime | None,
    timezone_name: str,
) -> ValidatedTime:
    zone = _query_timezone(timezone_name)
    local_now = _local_now(now, zone)
    text = candidate.text.strip()
    compact_text = re.sub(r"\s+", "", text)
    expected_granularity, start_date, end_date = _resolve_dates(
        compact_text,
        local_now.date(),
    )
    if expected_granularity is not candidate.granularity:
        raise _cannot_answer(
            f"时间表达 {text} 与粒度 {candidate.granularity.value} 不一致",
            "TIME_GRANULARITY_CONFLICT",
        )
    return ValidatedTime(
        text=text,
        granularity=candidate.granularity,
        start=datetime.combine(start_date, datetime_time.min, tzinfo=zone),
        end=datetime.combine(end_date, datetime_time.min, tzinfo=zone),
    )


def _resolve_dates(
    text: str,
    today: date,
) -> tuple[TimeGranularity, date, date]:
    if text in {"今天", "昨日", "昨天", "前天"}:
        offset = {"今天": 0, "昨日": -1, "昨天": -1, "前天": -2}[text]
        start = today + timedelta(days=offset)
        return TimeGranularity.DAY, start, start + timedelta(days=1)

    if text in {"本周", "上周"}:
        current_start = today - timedelta(days=today.weekday())
        start = current_start if text == "本周" else current_start - timedelta(days=7)
        return TimeGranularity.WEEK, start, start + timedelta(days=7)

    if text in {"本月", "上月"}:
        current_start = date(today.year, today.month, 1)
        start = current_start if text == "本月" else _shift_month(current_start, -1)
        return TimeGranularity.MONTH, start, _shift_month(start, 1)

    if text in {"本季度", "上季度"}:
        current_start = _quarter_start(today)
        start = current_start if text == "本季度" else _shift_month(current_start, -3)
        return TimeGranularity.QUARTER, start, _shift_month(start, 3)

    if text in {"今年", "去年"}:
        year = today.year if text == "今年" else today.year - 1
        start = date(year, 1, 1)
        return TimeGranularity.YEAR, start, date(year + 1, 1, 1)

    quarter_match = _YEAR_QUARTER_PATTERN.fullmatch(text)
    if quarter_match is not None:
        quarter_text = quarter_match.group("cn") or quarter_match.group("q")
        quarter_names = {"一": 1, "二": 2, "三": 3, "四": 4}
        quarter = (
            quarter_names[quarter_text]
            if quarter_text in quarter_names
            else int(quarter_text)
        )
        try:
            start = date(
                int(quarter_match.group("year")),
                (quarter - 1) * 3 + 1,
                1,
            )
            end = _shift_month(start, 3)
        except (TypeError, ValueError, OverflowError):
            raise _cannot_answer("日期表达无法标准化", "DATE_NOT_NORMALIZABLE")
        return TimeGranularity.QUARTER, start, end

    recent_match = _RECENT_DAYS_PATTERN.fullmatch(text)
    if recent_match is not None:
        days = int(recent_match.group(1))
        try:
            start = today - timedelta(days=days - 1)
        except (OverflowError, ValueError):
            raise _cannot_answer(
                "最近 N 天的范围超出日期支持范围", "DATE_NOT_NORMALIZABLE"
            )
        return TimeGranularity.DAY, start, today + timedelta(days=1)

    recent_months_match = _RECENT_MONTHS_PATTERN.fullmatch(text)
    if recent_months_match is not None:
        months = _parse_positive_number(recent_months_match.group(1))
        if months is None:
            raise _cannot_answer("最近 N 个月的范围无法标准化", "DATE_NOT_NORMALIZABLE")
        try:
            current_month = date(today.year, today.month, 1)
            start = _shift_month(current_month, -(months - 1))
            end = _shift_month(current_month, 1)
        except (OverflowError, ValueError):
            raise _cannot_answer(
                "最近 N 个月的范围超出日期支持范围", "DATE_NOT_NORMALIZABLE"
            ) from None
        return TimeGranularity.MONTH, start, end

    range_match = _DATE_RANGE_PATTERN.fullmatch(text)
    if range_match is not None:
        start = _parse_absolute_day(range_match.group(1))
        end_inclusive = _parse_absolute_day(range_match.group(2))
        end = end_inclusive + timedelta(days=1)
        if start > end_inclusive:
            raise _cannot_answer(
                "日期区间的开始日期晚于结束日期", "DATE_RANGE_REVERSED"
            )
        return TimeGranularity.DAY, start, end

    date_match = _DATE_PATTERN.fullmatch(text)
    if date_match is not None:
        start = _date_from_match(date_match)
        return TimeGranularity.DAY, start, start + timedelta(days=1)

    month_match = _YEAR_MONTH_PATTERN.fullmatch(text)
    if month_match is not None and (
        month_match.group(2) is not None or month_match.group(3) is not None
    ):
        month = int(month_match.group(2) or month_match.group(3))
        try:
            start = date(int(month_match.group(1)), month, 1)
            end = _shift_month(start, 1)
        except (ValueError, OverflowError):
            raise _cannot_answer("日期无法标准化", "DATE_NOT_NORMALIZABLE")
        return TimeGranularity.MONTH, start, end

    year_match = _YEAR_PATTERN.fullmatch(text)
    if year_match is not None:
        try:
            year = int(year_match.group(1))
            start = date(year, 1, 1)
        except (ValueError, OverflowError):
            raise _cannot_answer("日期无法标准化", "DATE_NOT_NORMALIZABLE")
        return TimeGranularity.YEAR, start, date(year + 1, 1, 1)

    raise _cannot_answer("日期表达无法标准化", "DATE_NOT_NORMALIZABLE")


def _parse_absolute_day(value: str) -> date:
    candidate = value.strip()
    match = _DATE_PATTERN.fullmatch(candidate)
    if match is None:
        raise _cannot_answer("日期区间必须使用完整日期", "DATE_NOT_NORMALIZABLE")
    return _date_from_match(match)


def _date_from_match(match: re.Match[str]) -> date:
    year = int(match.group(1))
    if match.group(2) is not None:
        month = int(match.group(2))
        day = int(match.group(3))
    else:
        month = int(match.group(4))
        day = int(match.group(5))
    try:
        return date(year, month, day)
    except (ValueError, OverflowError):
        raise _cannot_answer("日期无法标准化", "DATE_NOT_NORMALIZABLE")


def _quarter_start(value: date) -> date:
    month = ((value.month - 1) // 3) * 3 + 1
    return date(value.year, month, 1)


def _shift_month(value: date, offset: int) -> date:
    absolute_month = value.year * 12 + value.month - 1 + offset
    year, month_index = divmod(absolute_month, 12)
    return date(year, month_index + 1, 1)


def _parse_positive_number(value: str) -> int | None:
    if value.isdigit():
        parsed = int(value)
        return parsed if parsed > 0 else None

    digits = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
    if value == "十":
        return 10
    if value.startswith("十"):
        tail = value[1:]
        return 10 + digits.get(tail, 0) if tail in digits else None
    if value.endswith("十"):
        head = value[:-1]
        return digits.get(head, 0) * 10 if head in digits else None
    if len(value) == 3 and value[1] == "十" and value[0] in digits and value[2] in digits:
        return digits[value[0]] * 10 + digits[value[2]]
    if len(value) == 1:
        return digits.get(value)
    return None


def _query_timezone(timezone_name: str) -> ZoneInfo:
    if not isinstance(timezone_name, str) or not timezone_name.strip():
        raise _structure("QUERY_TIMEZONE 配置无效", "TIMEZONE_INVALID")
    try:
        return ZoneInfo(timezone_name.strip())
    except ZoneInfoNotFoundError:
        raise _structure("QUERY_TIMEZONE 配置无效", "TIMEZONE_INVALID") from None


def _local_now(value: datetime | None, zone: ZoneInfo) -> datetime:
    if value is None:
        return datetime.now(zone)
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise _structure("当前时间必须包含时区", "NOW_TIMEZONE_REQUIRED")
    return value.astimezone(zone)


def _string_list(value: object, field: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise _structure(f"{field} 必须是字符串数组", "STRING_LIST_INVALID")
    result: list[str] = []
    for item in value:
        result.append(_required_text(item, field))
    return tuple(result)


def _required_text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _structure(f"{field} 必须是非空字符串", "TEXT_INVALID")
    return value.strip()


def _enum_value(value: object, enum_type: type[StrEnum], field: str) -> StrEnum:
    if not isinstance(value, str):
        raise _structure(f"{field} 必须是字符串", "ENUM_TYPE_INVALID")
    try:
        return enum_type(value)
    except ValueError:
        raise _structure(f"{field} 的值不在允许范围内", "ENUM_VALUE_INVALID") from None


def _structure(message: str, reason: str) -> SemanticQueryStructureError:
    return SemanticQueryStructureError(message, reason=reason)


def _cannot_answer(message: str, reason: str) -> SemanticQueryCannotAnswer:
    return SemanticQueryCannotAnswer(message, reason=reason)
