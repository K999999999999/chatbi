"""确定性查询快照 XLSX 序列化；所有输入只作为数据单元格写入。"""

from __future__ import annotations

import json
import math
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile

import xlsxwriter

EXCEL_MAX_ROWS = 1_048_576
EXCEL_MAX_COLUMNS = 16_384
EXCEL_MAX_CELL_CHARS = 32_767
QUERY_MAX_ROWS = 100
_NUMBER = re.compile(r"^-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?$")
_XML_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\ufffe\uffff]")


def _text(value: str) -> str:
    if not isinstance(value, str):
        raise TypeError("导出文字格式无效")
    try:
        utf16_length = len(value.encode("utf-16-le")) // 2
    except UnicodeEncodeError:
        raise ValueError("导出文字包含 XLSX 无法表达的字符") from None
    if utf16_length > EXCEL_MAX_CELL_CHARS:
        raise ValueError("导出文字超过 XLSX 单元格长度限制")
    if _XML_CONTROL.search(value) or any(
        0xD800 <= ord(char) <= 0xDFFF for char in value
    ):
        raise ValueError("导出文字包含 XLSX 无法表达的字符")
    return value


def _format_cell(workbook, value: Any):
    if value is None:
        return "〈NULL〉", "null", "null"
    if isinstance(value, bool):
        return value, "boolean", json.dumps(value)
    if isinstance(value, int):
        if len(str(abs(value))) <= 15:
            return value, "number", str(value)
        return str(value), "integer-text", str(value)
    if isinstance(value, float):
        try:
            decimal_value = Decimal(str(value))
        except InvalidOperation:
            decimal_value = Decimal("NaN")
        significant_digits = len(decimal_value.normalize().as_tuple().digits)
        magnitude = decimal_value.copy_abs()
        in_excel_range = decimal_value.is_finite() and (
            decimal_value.is_zero()
            or Decimal("2.2251e-308") <= magnitude <= Decimal("9.99999999999999e307")
        )
        if (
            math.isfinite(value)
            and significant_digits <= 15
            and in_excel_range
        ):
            return value, "number", repr(value)
        return _text(repr(value)), "number-text", repr(value)
    if isinstance(value, str):
        if value == "":
            return "〈空字符串〉", "string", json.dumps(value, ensure_ascii=False)
        return _text(value), "string", json.dumps(value, ensure_ascii=False)
    raise ValueError("结果包含 XLSX 无法安全表达的数据类型")


def create_query_workbook(source: dict, destination: str | Path) -> None:
    """把一个已授权的公开查询快照编码成两工作表 XLSX。"""
    result = source.get("result")
    if not isinstance(result, dict):
        raise TypeError("查询快照不可用")
    columns = result.get("columns")
    rows = result.get("rows")
    row_count = result.get("row_count")
    if (
        not isinstance(columns, list)
        or not columns
        or len(columns) > EXCEL_MAX_COLUMNS
        or any(not isinstance(name, str) for name in columns)
        or not isinstance(rows, list)
        or len(rows) > QUERY_MAX_ROWS
        or type(row_count) is not int
        or row_count < len(rows)
        or type(result.get("truncated")) is not bool
        or (row_count != len(rows) and not result["truncated"])
        or any(not isinstance(row, list) or len(row) != len(columns) for row in rows)
    ):
        raise ValueError("查询结果快照格式无效")

    clean_columns = [_text(name) for name in columns]
    destination = Path(destination)
    workbook = xlsxwriter.Workbook(
        str(destination),
        {
            "constant_memory": True,
            "tmpdir": str(destination.parent),
            "strings_to_formulas": False,
            "strings_to_urls": False,
            "strings_to_numbers": False,
        },
    )
    try:
        data = workbook.add_worksheet("原始数据")
        notes = workbook.add_worksheet("结果说明")
        header_format = workbook.add_format({"bold": True, "text_wrap": True})
        data.freeze_panes(1, 0)
        data.autofilter(0, 0, len(rows), len(columns) - 1)
        for col, name in enumerate(clean_columns):
            if data.write_string(0, col, name, header_format) != 0:
                raise ValueError("导出列名无法写入")

        notes.write_string(0, 0, "项目", header_format)
        notes.write_string(0, 1, "内容", header_format)
        metadata = result.get("result_metadata")
        note_rows = [
            ("来源问题", source.get("question") or "来源问题未保存"),
            ("结果时间", source.get("result_time") or "原结果完成时间未保存"),
            ("导出时间", source.get("export_time") or "导出时间未保存"),
            ("展示行数", str(len(rows))),
            ("结果行数", str(row_count)),
            (
                "数据截断",
                "是；文件仅包含当前快照返回行" if result["truncated"] else "否",
            ),
        ]
        if source.get("saved_time"):
            note_rows.insert(2, ("成果保存时间", source["saved_time"]))
        _append_metadata(note_rows, metadata)

        null_markers: list[tuple[str, str, str, str]] = []
        for row_index, row in enumerate(rows, start=1):
            for col_index, value in enumerate(row):
                encoded, json_type, original = _format_cell(workbook, value)
                cell = f"{_column_name(col_index + 1)}{row_index + 1}"
                status = (
                    data.write_number(row_index, col_index, encoded)
                    if isinstance(encoded, (int, float))
                    and not isinstance(encoded, bool)
                    else data.write_boolean(row_index, col_index, encoded)
                    if isinstance(encoded, bool)
                    else data.write_string(row_index, col_index, encoded)
                )
                if status != 0:
                    raise ValueError("导出单元格无法完整写入")
                if (
                    json_type not in {"string", "boolean", "number"}
                    or value == ""
                    or value in {"〈NULL〉", "〈空字符串〉"}
                ):
                    null_markers.append(
                        (cell, clean_columns[col_index], json_type, original)
                    )

        if result["truncated"]:
            note_rows.append(
                ("截断提示", "仅包含快照当前返回行，未重新查询或获取全量数据。")
            )
        if null_markers:
            note_rows.append(("特殊单元格", "单元格坐标、原始 JSON 类型、原始 JSON 值"))
        for cell, column, json_type, original in null_markers:
            note_rows.append((f"{cell} · {column}", f"{json_type} · {original}"))
        if len(note_rows) + 1 > EXCEL_MAX_ROWS:
            raise ValueError("结果说明超过 XLSX 行数限制")
        for row_index, (key, value) in enumerate(note_rows, start=1):
            key = _text(str(key))
            value = _text(str(value))
            if (
                notes.write_string(row_index, 0, key) != 0
                or notes.write_string(row_index, 1, value) != 0
            ):
                raise ValueError("结果说明超过 XLSX 可表达限制")
        notes.freeze_panes(1, 0)
        notes.set_column(0, 0, 24)
        notes.set_column(1, 1, 80)
    except BaseException:
        workbook.close()
        destination.unlink(missing_ok=True)
        raise
    else:
        workbook.close()
        try:
            _verify_workbook(
                destination, len(rows) + 1, len(columns), len(note_rows) + 1
            )
        except (BadZipFile, ElementTree.ParseError, KeyError, OSError, ValueError):
            destination.unlink(missing_ok=True)
            raise ValueError("XLSX 文件完整性检查失败") from None


def _verify_workbook(path: Path, data_rows: int, data_columns: int, note_rows: int):
    namespace = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with ZipFile(path) as archive:
        if archive.testzip() is not None:
            raise BadZipFile("XLSX member checksum failed")
        workbook = ElementTree.fromstring(archive.read("xl/workbook.xml"))
        sheets = workbook.findall("./main:sheets/main:sheet", namespace)
        if [sheet.get("name") for sheet in sheets] != ["原始数据", "结果说明"]:
            raise ValueError("unexpected XLSX worksheet names")
        expected = (
            f"A1:{_column_name(data_columns)}{data_rows}",
            f"A1:B{note_rows}",
        )
        for index, reference in enumerate(expected, start=1):
            worksheet = ElementTree.fromstring(
                archive.read(f"xl/worksheets/sheet{index}.xml")
            )
            dimension = worksheet.find("main:dimension", namespace)
            if dimension is None or dimension.get("ref") != reference:
                raise ValueError("unexpected XLSX worksheet dimensions")


def _append_metadata(rows: list[tuple[str, str]], metadata: Any) -> None:
    if not isinstance(metadata, dict):
        rows.append(("结果说明", "业务口径未确认；保留原始快照值。"))
        return
    columns = metadata.get("columns")
    if isinstance(columns, list):
        for index, column in enumerate(columns):
            if not isinstance(column, dict):
                continue
            label = (
                column.get("semantic_name") or column.get("name") or f"第{index + 1}列"
            )
            definition = column.get("definition")
            unit = column.get("unit")
            if definition:
                rows.append((f"指标定义 · {label}", str(definition)))
            if isinstance(unit, dict) and unit.get("label"):
                rows.append((f"单位 · {label}", str(unit["label"])))
    scope = metadata.get("scope")
    if isinstance(scope, dict):
        for key in ("time", "filters", "grouping", "warnings"):
            value = scope.get(key)
            if value:
                rows.append(
                    (
                        f"查询范围 · {key}",
                        json.dumps(value, ensure_ascii=False, sort_keys=True),
                    )
                )


def _column_name(number: int) -> str:
    label = ""
    while number:
        number, remainder = divmod(number - 1, 26)
        label = chr(65 + remainder) + label
    return label
