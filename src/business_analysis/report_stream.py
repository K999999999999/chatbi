"""受限的 Business Analysis 报告增量 JSON 字符串解码器。"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field as dataclass_field
from io import StringIO

_TEXT_FIELDS = frozenset({"title", "executive_summary", "trend_judgment"})
_LIST_FIELDS = frozenset({"key_findings", "root_causes", "action_suggestions"})
_DRAFT_FIELDS = _TEXT_FIELDS | _LIST_FIELDS
MAX_DRAFT_BYTES = 5 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class ReportTextDelta:
    field: str
    index: int | None
    offset: int
    text: str


@dataclass(slots=True)
class _Frame:
    kind: str
    state: str
    root: bool = False
    keys: set[str] = dataclass_field(default_factory=set)
    current_key: str | None = None
    draft_field: str | None = None
    item_count: int = 0


@dataclass(slots=True)
class _String:
    role: str
    field: str | None = None
    index: int | None = None
    key_parts: list[str] = dataclass_field(default_factory=list)
    escaped: bool = False
    unicode_digits: str | None = None
    pending_high_surrogate: int | None = None
    expect_low: str | None = None


@dataclass(slots=True)
class _DeltaBuilder:
    field: str
    index: int | None
    offset: int
    text: StringIO = dataclass_field(default_factory=StringIO)
    length: int = 0


class IncrementalReportJSONDecoder:
    """按 JSON 结构定位六个展示字段；绝不按模型 key 构造对象路径。"""

    def __init__(self, *, max_draft_bytes: int = MAX_DRAFT_BYTES) -> None:
        if isinstance(max_draft_bytes, bool) or max_draft_bytes < 1:
            raise ValueError("报告草稿上限必须为正整数")
        self._max_draft_bytes = max_draft_bytes
        self._stack: list[_Frame] = []
        self._root_started = False
        self._root_complete = False
        self._string: _String | None = None
        self._primitive: list[str] | None = None
        self._draft_lengths: dict[tuple[str, int | None], int] = {}
        self._draft_bytes = 0
        self._feed_deltas: list[_DeltaBuilder] = []
        self._finished = False

    def feed(self, text: str) -> tuple[ReportTextDelta, ...]:
        if self._finished:
            raise ValueError("报告 JSON 解码器已结束")
        if not isinstance(text, str):
            raise TypeError("Summary LLM 输出必须是文本")
        self._feed_deltas = []
        index = 0
        while index < len(text):
            char = text[index]
            if self._string is not None:
                self._consume_string_char(char)
                index += 1
                continue
            if self._primitive is not None:
                if char in ",]} \t\r\n":
                    self._finish_primitive()
                    continue
                self._primitive.append(char)
                index += 1
                continue
            self._consume_json_char(char)
            index += 1
        deltas = tuple(
            ReportTextDelta(
                builder.field,
                builder.index,
                builder.offset,
                builder.text.getvalue(),
            )
            for builder in self._feed_deltas
        )
        self._feed_deltas = []
        return deltas

    def finish(self) -> None:
        if self._finished:
            raise ValueError("报告 JSON 解码器重复结束")
        self._finished = True
        if self._primitive is not None:
            self._finish_primitive()
        if self._string is not None or self._stack or not self._root_complete:
            raise ValueError("Summary LLM 返回的 JSON 不完整")

    def _consume_json_char(self, char: str) -> None:
        if char in " \t\r\n":
            return
        if not self._stack:
            if self._root_complete:
                raise ValueError("JSON 根对象后包含额外内容")
            if self._root_started or char != "{":
                raise ValueError("Summary 报告必须是 JSON 对象")
            self._root_started = True
            self._stack.append(_Frame("object", "key_or_end", root=True))
            return

        frame = self._stack[-1]
        if frame.kind == "object":
            self._consume_object_char(frame, char)
        else:
            self._consume_array_char(frame, char)

    def _consume_object_char(self, frame: _Frame, char: str) -> None:
        if frame.state in {"key_or_end", "key_required"}:
            if char == "}" and frame.state == "key_or_end":
                self._close_container()
            elif char == '"':
                self._string = _String("key")
            else:
                raise ValueError("JSON 对象 key 格式无效")
            return
        if frame.state == "colon":
            if char != ":":
                raise ValueError("JSON 对象缺少冒号")
            frame.state = "value"
            return
        if frame.state == "value":
            self._start_value(char)
            return
        if frame.state == "comma_or_end":
            if char == ",":
                frame.state = "key_required"
            elif char == "}":
                self._close_container()
            else:
                raise ValueError("JSON 对象分隔符无效")
            return
        raise ValueError("JSON 对象状态无效")

    def _consume_array_char(self, frame: _Frame, char: str) -> None:
        if frame.state in {"value_or_end", "value_required"}:
            if char == "]" and frame.state == "value_or_end":
                self._close_container()
            else:
                self._start_value(char)
            return
        if frame.state == "comma_or_end":
            if char == ",":
                frame.state = "value_required"
            elif char == "]":
                self._close_container()
            else:
                raise ValueError("JSON 数组分隔符无效")
            return
        raise ValueError("JSON 数组状态无效")

    def _start_value(self, char: str) -> None:
        parent = self._stack[-1]
        if parent.kind == "object":
            if parent.state != "value":
                raise ValueError("JSON 对象 value 位置无效")
            root_field = parent.current_key if parent.root else None
            if char == '"':
                field_name = root_field if root_field in _TEXT_FIELDS else None
                self._string = _String("value", field=field_name)
                return
            if char == "{":
                self._stack.append(_Frame("object", "key_or_end"))
                return
            if char == "[":
                draft_field = root_field if root_field in _LIST_FIELDS else None
                self._stack.append(
                    _Frame("array", "value_or_end", draft_field=draft_field)
                )
                return
        else:
            if parent.state not in {"value_or_end", "value_required"}:
                raise ValueError("JSON 数组 value 位置无效")
            if char == '"':
                field_name = parent.draft_field
                item_index = parent.item_count if field_name is not None else None
                self._string = _String("value", field=field_name, index=item_index)
                return
            if char == "{":
                self._stack.append(_Frame("object", "key_or_end"))
                return
            if char == "[":
                self._stack.append(_Frame("array", "value_or_end"))
                return

        if char in "-0123456789tfn":
            self._primitive = [char]
            return
        raise ValueError("JSON value 格式无效")

    def _consume_string_char(self, char: str) -> None:
        token = self._string
        assert token is not None

        if token.expect_low is not None:
            if token.expect_low == "slash":
                if char != "\\":
                    raise ValueError("JSON Unicode 代理对不完整")
                token.expect_low = "u"
            else:
                if char != "u":
                    raise ValueError("JSON Unicode 代理对不完整")
                token.expect_low = None
                token.unicode_digits = ""
            return

        if token.unicode_digits is not None:
            if char not in "0123456789abcdefABCDEF":
                raise ValueError("JSON Unicode 转义无效")
            token.unicode_digits += char
            if len(token.unicode_digits) == 4:
                value = int(token.unicode_digits, 16)
                token.unicode_digits = None
                if token.pending_high_surrogate is not None:
                    if not 0xDC00 <= value <= 0xDFFF:
                        raise ValueError("JSON Unicode 代理对无效")
                    codepoint = (
                        0x10000
                        + ((token.pending_high_surrogate - 0xD800) << 10)
                        + (value - 0xDC00)
                    )
                    token.pending_high_surrogate = None
                    self._emit_string_char(token, chr(codepoint))
                elif 0xD800 <= value <= 0xDBFF:
                    token.pending_high_surrogate = value
                    token.expect_low = "slash"
                elif 0xDC00 <= value <= 0xDFFF:
                    raise ValueError("JSON 孤立低代理项无效")
                else:
                    self._emit_string_char(token, chr(value))
            return

        if token.escaped:
            token.escaped = False
            escapes = {
                '"': '"',
                "\\": "\\",
                "/": "/",
                "b": "\b",
                "f": "\f",
                "n": "\n",
                "r": "\r",
                "t": "\t",
            }
            if char == "u":
                token.unicode_digits = ""
            elif char in escapes:
                self._emit_string_char(token, escapes[char])
            else:
                raise ValueError("JSON 字符串转义无效")
            return

        if char == '"':
            self._close_string(token)
        elif char == "\\":
            token.escaped = True
        elif ord(char) < 0x20 or 0xD800 <= ord(char) <= 0xDFFF:
            raise ValueError("JSON 字符串包含无效字符")
        else:
            self._emit_string_char(token, char)

    def _emit_string_char(self, token: _String, char: str) -> None:
        if token.role == "key":
            token.key_parts.append(char)
            return
        if token.field is None:
            return
        encoded_size = len(char.encode("utf-8"))
        if self._draft_bytes + encoded_size > self._max_draft_bytes:
            raise ValueError("报告草稿超过公开上限")
        key = (token.field, token.index)
        offset = self._draft_lengths.get(key, 0)
        self._draft_lengths[key] = offset + 1
        self._draft_bytes += encoded_size
        if self._feed_deltas and (
            self._feed_deltas[-1].field == token.field
            and self._feed_deltas[-1].index == token.index
            and self._feed_deltas[-1].offset + self._feed_deltas[-1].length == offset
        ):
            builder = self._feed_deltas[-1]
            builder.text.write(char)
            builder.length += 1
        else:
            builder = _DeltaBuilder(token.field, token.index, offset)
            builder.text.write(char)
            builder.length = 1
            self._feed_deltas.append(builder)

    def _close_string(self, token: _String) -> None:
        if token.pending_high_surrogate is not None or token.unicode_digits is not None:
            raise ValueError("JSON Unicode 转义不完整")
        self._string = None
        parent = self._stack[-1]
        if token.role == "key":
            key = "".join(token.key_parts)
            if key in parent.keys:
                raise ValueError("JSON 对象包含重复 key")
            parent.keys.add(key)
            parent.current_key = key
            parent.state = "colon"
            return
        self._complete_value()

    def _finish_primitive(self) -> None:
        token = "".join(self._primitive or ())
        self._primitive = None
        if token not in {"true", "false", "null"} and not _valid_json_number(token):
            raise ValueError("JSON primitive 格式无效")
        self._complete_value()

    def _complete_value(self) -> None:
        parent = self._stack[-1]
        if parent.kind == "object":
            if parent.state != "value":
                raise ValueError("JSON 对象 value 状态无效")
            parent.state = "comma_or_end"
            parent.current_key = None
        else:
            if parent.state not in {"value_or_end", "value_required"}:
                raise ValueError("JSON 数组 value 状态无效")
            parent.state = "comma_or_end"
            parent.item_count += 1

    def _close_container(self) -> None:
        frame = self._stack[-1]
        if frame.kind == "object" and frame.state not in {"key_or_end", "comma_or_end"}:
            raise ValueError("JSON 对象未完整")
        if frame.kind == "array" and frame.state not in {
            "value_or_end",
            "comma_or_end",
        }:
            raise ValueError("JSON 数组未完整")
        self._stack.pop()
        if not self._stack:
            self._root_complete = True
        else:
            self._complete_value()


def _valid_json_number(value: str) -> bool:
    if not value:
        return False
    index = 0
    if value[index] == "-":
        index += 1
        if index == len(value):
            return False
    if value[index] == "0":
        index += 1
        if index < len(value) and value[index].isdigit():
            return False
    elif "1" <= value[index] <= "9":
        index += 1
        while index < len(value) and "0" <= value[index] <= "9":
            index += 1
    else:
        return False
    if index < len(value) and value[index] == ".":
        index += 1
        start = index
        while index < len(value) and "0" <= value[index] <= "9":
            index += 1
        if index == start:
            return False
    if index < len(value) and value[index] in "eE":
        index += 1
        if index < len(value) and value[index] in "+-":
            index += 1
        start = index
        while index < len(value) and "0" <= value[index] <= "9":
            index += 1
        if index == start:
            return False
    return index == len(value)
