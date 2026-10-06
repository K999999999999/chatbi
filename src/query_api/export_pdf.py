"""从受限的已完成分析快照离线生成可选取文本的 A4 PDF。"""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit

from .export_assets import verify_runtime_manifest
from .export_png import (
    RENDER_ORIGIN,
    ExportRendererUnavailable,
    ExportRenderFailure,
    _read_assets,
)

MAX_PDF_BYTES = 20 * 1024 * 1024
MAX_PDF_TABLE_CELLS = 100_000
PDF_VIEWPORT = {"width": 794, "height": 1123}


class ExportFileTooLarge(ValueError):
    """PDF 超出单文件资源限制。"""


def _json_hash(value: object) -> str:
    try:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError):
        raise ExportRenderFailure("PDF 快照无法安全编码") from None
    import hashlib

    return hashlib.sha256(encoded).hexdigest()


def _object(value: object, label: str) -> dict:
    if not isinstance(value, dict):
        raise ExportRenderFailure(f"{label}结构无效")
    return value


def _string(value: object, label: str) -> str:
    if not isinstance(value, str):
        raise ExportRenderFailure(f"{label}文字无效")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        raise ExportRenderFailure(f"{label}文字编码无效") from None
    if any(ord(char) < 32 and char not in "\n\r\t" for char in value):
        raise ExportRenderFailure(f"{label}文字包含不可显示字符")
    return value


def _strings(value: object, label: str) -> list[str]:
    if not isinstance(value, list):
        raise ExportRenderFailure(f"{label}列表无效")
    return [_string(item, label) for item in value]


def _decimal(value: object, label: str) -> str:
    result = _string(value, label)
    if re.fullmatch(r"-?\d+(?:\.\d+)?", result) is None:
        raise ExportRenderFailure(f"{label}数值无效")
    return result


def _safe_metadata(value: object) -> dict | None:
    if value is None:
        return None
    metadata = _object(value, "任务口径")
    columns = metadata.get("columns", [])
    if not isinstance(columns, list):
        raise ExportRenderFailure("任务列口径无效")
    safe_columns = []
    for item in columns:
        column = _object(item, "任务列口径")
        safe = {
            key: _string(column[key], f"任务列 {key}")
            for key in ("name", "semantic_name", "definition", "role")
            if isinstance(column.get(key), str)
        }
        if type(column.get("index")) is int and 0 <= column["index"] < 100_000:
            safe["index"] = column["index"]
        unit = column.get("unit")
        if isinstance(unit, dict) and isinstance(unit.get("label"), str):
            safe["unit"] = {"label": _string(unit["label"], "任务列单位")}
        safe_columns.append(safe)
    scope = _object(metadata.get("scope", {}), "任务范围")
    safe_scope: dict = {}
    for key in ("status", "time_status"):
        if isinstance(scope.get(key), str):
            safe_scope[key] = _string(scope[key], "任务范围")
    period = scope.get("time")
    if isinstance(period, dict):
        safe_period = {
            key: _string(period[key], "任务时间范围")
            for key in ("start", "end_exclusive", "time_basis")
            if isinstance(period.get(key), str)
        }
        safe_scope["time"] = safe_period
    for key in ("filters", "grouping"):
        values = scope.get(key, [])
        if not isinstance(values, list):
            raise ExportRenderFailure("任务范围列表无效")
        clean_values = []
        for item in values:
            entry = _object(item, "任务范围项目")
            clean: dict = {}
            for field in ("label", "operator", "kind", "semantic_name"):
                if isinstance(entry.get(field), str):
                    clean[field] = _string(entry[field], "任务范围项目")
            field_values = entry.get("values")
            if isinstance(field_values, list):
                clean["values"] = [
                    _string(text, "任务范围值")
                    if isinstance(text, str)
                    else json.dumps(text, ensure_ascii=False, allow_nan=False)
                    for text in field_values
                ]
            clean_values.append(clean)
        safe_scope[key] = clean_values
    warnings = scope.get("warnings", [])
    if not isinstance(warnings, list):
        raise ExportRenderFailure("任务范围提示无效")
    safe_scope["warnings"] = [_string(item, "任务范围提示") for item in warnings if isinstance(item, str)]
    return {"columns": safe_columns, "scope": safe_scope}


def _safe_attribution(value: object) -> dict:
    attribution = _object(value, "分析归因")
    if attribution.get("reconciliation_passed") is not True:
        raise ExportRenderFailure("分析归因未通过对账")
    products = attribution.get("products")
    if not isinstance(products, list):
        raise ExportRenderFailure("产品归因列表无效")
    clean_products = []
    for item in products:
        product = _object(item, "产品归因")
        factors = product.get("factors")
        if not isinstance(factors, list):
            raise ExportRenderFailure("因素归因列表无效")
        clean_products.append(
            {
                "product_name": _string(product.get("product_name"), "产品名称"),
                "change": _decimal(product.get("change"), "产品贡献"),
                "classification": _string(product.get("classification"), "产品分类"),
                "effect_on_metric": _string(product.get("effect_on_metric"), "产品贡献方向"),
                "factors": [
                    {
                        "name": _string(_object(factor, "因素归因").get("name"), "因素名称"),
                        "amount": _decimal(_object(factor, "因素归因").get("amount"), "因素贡献"),
                        "effect_on_metric": _string(
                            _object(factor, "因素归因").get("effect_on_metric"), "因素贡献方向"
                        ),
                    }
                    for factor in factors
                ],
            }
        )
    omitted = attribution.get("omitted_product_count")
    if type(omitted) is not int or omitted < 0:
        raise ExportRenderFailure("未返回产品数量无效")
    return {
        key: _string(attribution.get(key), "归因说明")
        for key in (
            "metric_name",
            "comparison_period",
            "current_period",
            "direction",
        )
    } | {
        key: _decimal(attribution.get(key), "归因指标值")
        for key in ("comparison_value", "current_value", "total_change")
    } | {"omitted_product_count": omitted, "products": clean_products}


def _safe_document(document: object) -> dict:
    source = _object(document, "导出来源")
    if source.get("kind") != "analysis":
        raise ExportRenderFailure("PDF 仅支持经营分析成功快照")
    result = _object(source.get("result"), "分析结果")
    raw_report = _object(result.get("report"), "分析报告")
    report = {
        key: _string(raw_report.get(key), "分析报告")
        for key in ("title", "executive_summary", "trend_judgment")
    }
    for key in ("key_findings", "root_causes", "action_suggestions", "evidence_task_ids"):
        report[key] = _strings(raw_report.get(key), "分析报告")
    raw_incomplete = raw_report.get("incomplete_tasks")
    if not isinstance(raw_incomplete, list):
        raise ExportRenderFailure("证据限制列表无效")
    report["incomplete_tasks"] = [
        {
            "task_id": _string(_object(item, "证据限制").get("task_id"), "证据限制任务"),
            "reasons": _strings(_object(item, "证据限制").get("reasons"), "证据限制原因"),
        }
        for item in raw_incomplete
    ]
    if raw_report.get("attribution") is not None:
        report["attribution"] = _safe_attribution(raw_report["attribution"])
    raw_tasks = result.get("task_results")
    if not isinstance(raw_tasks, list):
        raise ExportRenderFailure("查询证据列表无效")
    clean_tasks: list[dict] = []
    task_ids: set[str] = set()
    cells = 0
    for value in raw_tasks:
        task = _object(value, "查询任务")
        task_id = _string(task.get("task_id"), "查询任务编号")
        status = task.get("status")
        if status not in {"completed", "failed", "skipped"} or task_id in task_ids:
            raise ExportRenderFailure("查询任务身份或状态无效")
        task_ids.add(task_id)
        columns = _strings(task.get("columns"), "查询任务列")
        raw_rows = task.get("rows")
        if not isinstance(raw_rows, list) or len(raw_rows) > 100:
            raise ExportRenderFailure("查询任务数据超过已保存范围")
        rows: list[list[str | int | float | bool | None]] = []
        for row in raw_rows:
            if not isinstance(row, list) or len(row) != len(columns):
                raise ExportRenderFailure("查询任务行列数不一致")
            if any(
                cell is not None
                and type(cell) not in {str, int, float, bool}
                for cell in row
            ):
                raise ExportRenderFailure("查询任务单元格类型无效")
            if any(isinstance(cell, float) and not __import__("math").isfinite(cell) for cell in row):
                raise ExportRenderFailure("查询任务包含非有限数值")
            rows.append(row)
        row_count = task.get("row_count")
        truncated = task.get("truncated")
        if (
            type(row_count) is not int
            or row_count < len(rows)
            or type(truncated) is not bool
            or (row_count > len(rows) and not truncated)
        ):
            raise ExportRenderFailure("查询任务返回范围无效")
        cells += len(rows) * len(columns)
        if cells > MAX_PDF_TABLE_CELLS:
            raise ExportRenderFailure("完整证据表格超过 PDF 渲染范围")
        error = task.get("error")
        error_message = None
        if error is not None:
            error_message = _string(_object(error, "查询任务错误").get("message"), "查询任务错误")
        clean_tasks.append(
            {
                "task_id": task_id,
                "status": status,
                "columns": columns,
                "rows": rows,
                "row_count": row_count,
                "truncated": truncated,
                "error": error_message,
                "result_metadata": _safe_metadata(task.get("result_metadata")),
            }
        )
    if len({task["task_id"] for task in clean_tasks}) != len(clean_tasks):
        raise ExportRenderFailure("查询任务编号重复")
    if any(task_id not in task_ids for task_id in report["evidence_task_ids"]):
        raise ExportRenderFailure("报告引用了未保存的查询任务")
    return {
        "kind": "analysis",
        "question": _string(source.get("question"), "原分析问题")
        if isinstance(source.get("question"), str)
        else "原分析问题未保存",
        "result_time": _string(source.get("result_time"), "报告完成时间")
        if isinstance(source.get("result_time"), str)
        else "原报告完成时间未保存",
        "saved_time": _string(source.get("saved_time"), "成果保存时间")
        if isinstance(source.get("saved_time"), str)
        else None,
        "export_time": _string(source.get("export_time"), "导出时间"),
        "result": {"report": report, "task_results": clean_tasks},
    }


def _expected_coverage(document: dict, render_hash: str) -> dict:
    result = document["result"]
    report = result["report"]
    attribution = report.get("attribution")
    tasks = []
    for task in result["task_results"]:
        column_count = len(task["columns"])
        row_count = len(task["rows"])
        table_blocks = (column_count + 1) // 2
        tasks.append(
            {
                "task_id": task["task_id"],
                "column_count": column_count,
                "row_count": row_count,
                "table_blocks": table_blocks,
                "rendered_rows": table_blocks * row_count,
            }
        )
    products = attribution["products"] if attribution else []
    block_ids = [
        "title",
        "executive-summary",
        "key-findings",
        "trend-judgment",
        "root-causes",
        "action-suggestions",
    ]
    if attribution is not None:
        block_ids.append("attribution")
    block_ids.extend(("evidence", "limitations"))
    return {
        "version": 1,
        "render_hash": render_hash,
        "block_ids": block_ids,
        "tasks": tasks,
        "product_count": len(products),
        "factor_count": sum(len(product["factors"]) for product in products),
        "attribution_chart": bool(products),
    }


def _validate_manifest(value: object, expected: dict) -> None:
    if not isinstance(value, dict) or value != expected:
        raise ExportRenderFailure("PDF 内容 coverage 清单与快照不一致")


def _validate_pdf(path: Path) -> int:
    try:
        size = path.stat().st_size
        if not 0 < size <= MAX_PDF_BYTES:
            raise ExportFileTooLarge("PDF 文件超过 20 MiB")
        with path.open("rb") as stream:
            header = stream.read(8)
            stream.seek(max(0, size - 2048))
            trailer = stream.read()
    except OSError:
        raise ExportRenderFailure("PDF 文件无法读取") from None
    if not header.startswith(b"%PDF-") or b"%%EOF" not in trailer:
        raise ExportRenderFailure("PDF 文件不完整")
    return size


def generate_pdf(document: dict, destination: str | Path) -> None:
    """校验公开分析快照，使用固定离线 Chromium 生成可选取文本的 PDF。"""
    clean_document = _safe_document(document)
    root = Path(os.environ.get("CHATBI_EXPORT_ROOT", "/opt/chatbi-export"))
    asset_root = root / "assets"
    try:
        runtime = verify_runtime_manifest(root)
        files = _read_assets(asset_root)
    except Exception as error:
        raise ExportRendererUnavailable("固定 PDF renderer 资源不可用") from error

    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import sync_playwright
    except ImportError as error:
        raise ExportRendererUnavailable("Playwright PDF renderer 不可用") from error

    render_hash = _json_hash(clean_document)
    payload = {"source": clean_document, "render_hash": render_hash}
    expected = _expected_coverage(clean_document, render_hash)
    blocked: list[str] = []
    output = Path(destination)
    output.unlink(missing_ok=True)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True, chromium_sandbox=True)
            try:
                executable = Path(playwright.chromium.executable_path).resolve(strict=True)
                if executable != Path(runtime["chromium_executable"]).resolve(strict=True):
                    raise ExportRendererUnavailable("Chromium 版本与固定运行清单不匹配")
                context = browser.new_context(
                    viewport=PDF_VIEWPORT,
                    device_scale_factor=1,
                    service_workers="block",
                    accept_downloads=False,
                )
                try:
                    def fulfill_local_resources(route):
                        request = route.request
                        parsed = urlsplit(request.url)
                        if request.method != "GET" or parsed.scheme != "http" or parsed.netloc != "localhost":
                            blocked.append(request.url[:512])
                            route.abort()
                            return
                        relative = unquote(parsed.path).lstrip("/") or "export.html"
                        if relative not in files or ".." in PurePosixPath(relative).parts:
                            blocked.append(request.url[:512])
                            route.abort()
                            return
                        route.fulfill(
                            status=200,
                            body=files[relative],
                            content_type=(
                                "text/html; charset=utf-8"
                                if relative.endswith(".html")
                                else "text/javascript; charset=utf-8"
                                if relative.endswith(".js")
                                else "text/css; charset=utf-8"
                                if relative.endswith(".css")
                                else "font/woff2"
                                if relative.endswith(".woff2")
                                else "application/octet-stream"
                            ),
                            headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "no-store"},
                        )

                    context.route("**/*", fulfill_local_resources)
                    page = context.new_page()
                    page.set_default_timeout(45_000)
                    page.on("websocket", lambda socket: blocked.append(socket.url[:512]))
                    page.goto(RENDER_ORIGIN + "/", wait_until="load")
                    page.evaluate("request => window.__chatbiRenderReport(request)", payload)
                    render_deadline = time.monotonic() + 45
                    state = None
                    while time.monotonic() < render_deadline:
                        state = page.evaluate("() => window.__chatbiRenderState")
                        if isinstance(state, dict) and state.get("status") in {"ready", "failed"}:
                            break
                        time.sleep(0.05)
                    else:
                        raise ExportRendererUnavailable("PDF 页面未在时限内完成")
                    if not isinstance(state, dict) or state.get("status") != "ready":
                        diagnostic = state.get("error") if isinstance(state, dict) else None
                        cause = RuntimeError(diagnostic) if isinstance(diagnostic, str) else None
                        raise ExportRenderFailure("PDF 内容未能完整渲染") from cause
                    _validate_manifest(state.get("manifest"), expected)
                    if blocked:
                        raise ExportRenderFailure("PDF 渲染期间尝试访问未批准资源")
                    page.emulate_media(media="print")
                    dimensions = page.evaluate(
                        """() => ({width: document.documentElement.scrollWidth,
                        viewport: window.innerWidth,
                        rootWidth: document.querySelector('.pdf-report').scrollWidth,
                        clientWidth: document.querySelector('.pdf-report').clientWidth})"""
                    )
                    if (
                        dimensions["width"] > dimensions["viewport"]
                        or dimensions["rootWidth"] > dimensions["clientWidth"] + 2
                    ):
                        raise ExportRenderFailure("PDF 页面存在横向裁切")
                    page.pdf(
                        path=str(output),
                        format="A4",
                        print_background=True,
                        display_header_footer=True,
                        header_template="<div></div>",
                        footer_template=(
                            '<div style="width:100%;padding:0 13mm;color:#56636d;'
                            'font:8px sans-serif;text-align:right">'
                            '<span class="pageNumber"></span> / '
                            '<span class="totalPages"></span></div>'
                        ),
                        prefer_css_page_size=True,
                    )
                finally:
                    context.close()
            finally:
                browser.close()
    except (ExportRendererUnavailable, ExportRenderFailure, ExportFileTooLarge):
        raise
    except PlaywrightError as error:
        raise ExportRendererUnavailable("Chromium sandbox 或 PDF 打印不可用") from error
    except Exception as error:
        raise ExportRenderFailure("PDF 未能完整生成") from error

    _validate_pdf(output)
