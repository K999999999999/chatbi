"""多指标请求形态判别与列举项解析。"""

from dataclasses import dataclass
import re

from ..contracts import RequestShape


_ACTION_PATTERN = re.compile(r"统计|查询|查看|比较|分析")
_SEPARATOR_PATTERN = re.compile(r"、|，|,|以及|和|及|与")
_METRIC_ENDING_PATTERN = re.compile(
    r"(?:数量|金额|利润|毛利率|占比|均价|单价|总额|成本|毛利|数|额|率)$"
)
_UNSUPPORTED_MULTI_MARKERS = ("不要", "不查", "不统计", "排除", "分别")
_TEXT_MATCH_MARKERS = (
    "名称中包含",
    "描述中包含",
    "文本中包含",
    "字段中包含",
    "字符串中包含",
)
_TRIM_CHARS = " 。！？；;：:"


@dataclass(frozen=True, slots=True)
class _ListItem:
    text: str
    start: int
    end: int


def classify_request_shape(question: str) -> RequestShape:
    """仅用有限句法预判是否存在明确多指标列举。"""

    if any(marker in question for marker in _TEXT_MATCH_MARKERS):
        return RequestShape.BASELINE
    segment, _ = _metric_segment(question)
    items = _list_items(segment)
    metric_like = tuple(item for item in items if _looks_like_metric(item.text))
    if len(metric_like) < 2:
        return RequestShape.BASELINE
    if any(marker in question for marker in _UNSUPPORTED_MULTI_MARKERS):
        return RequestShape.POSSIBLE_MULTI
    if _has_separate_item_dates(metric_like):
        return RequestShape.POSSIBLE_MULTI
    return RequestShape.EXPLICIT_MULTI


def _metric_segment(question: str) -> tuple[str, int]:
    actions = tuple(_ACTION_PATTERN.finditer(question))
    if not actions:
        return question, 0
    last = actions[-1]
    return question[last.end():], last.end()


def _list_items(segment: str) -> tuple[_ListItem, ...]:
    items: list[_ListItem] = []
    start = 0
    for separator in _SEPARATOR_PATTERN.finditer(segment):
        _append_item(items, segment, start, separator.start())
        start = separator.end()
    _append_item(items, segment, start, len(segment))
    return tuple(items)


def _append_item(
    items: list[_ListItem],
    segment: str,
    start: int,
    end: int,
) -> None:
    raw = segment[start:end]
    left_trimmed = raw.lstrip(_TRIM_CHARS)
    text = left_trimmed.rstrip(_TRIM_CHARS)
    if not text:
        return
    item_start = start + len(raw) - len(left_trimmed)
    items.append(_ListItem(text=text, start=item_start, end=item_start + len(text)))


def _looks_like_metric(value: str) -> bool:
    compact = re.sub(r"[\s的]+", "", value)
    return bool(_METRIC_ENDING_PATTERN.search(compact))


def _has_separate_item_dates(items: tuple[_ListItem, ...]) -> bool:
    date_pattern = re.compile(
        r"(?:20\d{2}年|\d{1,2}月|第[一二三四1-4]季度|上月|本月|去年|今年)"
    )
    return sum(bool(date_pattern.search(item.text)) for item in items) > 1
