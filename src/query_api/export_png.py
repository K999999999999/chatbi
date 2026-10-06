"""在凭证剥离的 Chromium worker 中离线生成单张完整图表 PNG。"""

from __future__ import annotations

import hashlib
import json
import os
import re
import struct
import time
import zlib
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit

from .export_assets import verify_bundle, verify_runtime_manifest

PNG_WIDTH = 1600
MAX_PNG_PIXELS = 40_000_000
MAX_PNG_BYTES = 20 * 1024 * 1024
RENDER_ORIGIN = "http://localhost"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


class InvalidChartSelection(ValueError):
    """请求选择的图表不属于此成功快照。"""


class ExportPixelLimit(ValueError):
    """完整 PNG 无法在资源上限内呈现。"""


class ExportRendererUnavailable(RuntimeError):
    """固定离线 renderer 或 sandbox 不可用。"""


class ExportRenderFailure(RuntimeError):
    """固定图形模板未能完整生成 PNG。"""


def _json_hash(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return hashlib.sha256(encoded).hexdigest()


def _read_assets(asset_root: Path) -> dict[str, bytes]:
    manifest = verify_bundle(asset_root)
    files: dict[str, bytes] = {}
    for relative in manifest["files"]:
        path = asset_root.joinpath(*PurePosixPath(relative).parts)
        files[relative] = path.read_bytes()
    return files


def _content_type(path: str) -> str:
    if path.endswith(".html"):
        return "text/html; charset=utf-8"
    if path.endswith(".js"):
        return "text/javascript; charset=utf-8"
    if path.endswith(".css"):
        return "text/css; charset=utf-8"
    if path.endswith(".woff2"):
        return "font/woff2"
    if path.endswith(".svg"):
        return "image/svg+xml"
    return "application/octet-stream"


def _png_dimensions(path: Path) -> tuple[int, int]:
    with path.open("rb") as stream:
        signature = stream.read(8)
        length = struct.unpack(">I", stream.read(4))[0]
        chunk_type = stream.read(4)
        header = stream.read(length)
        crc = struct.unpack(">I", stream.read(4))[0]
    if (
        signature != PNG_SIGNATURE
        or length != 13
        or chunk_type != b"IHDR"
        or zlib.crc32(chunk_type + header) & 0xFFFFFFFF != crc
    ):
        raise ExportRenderFailure("PNG 文件头无效")
    width, height = struct.unpack(">II", header[:8])
    if width != PNG_WIDTH or width < 1 or height < 1 or width * height > MAX_PNG_PIXELS:
        raise ExportPixelLimit("PNG 尺寸超出完整导出范围")
    return width, height


def _validate_manifest(manifest: object, render_hash: str, selection: dict) -> dict:
    if not isinstance(manifest, dict) or manifest.get("version") != 1:
        raise ExportRenderFailure("图表完整性清单无效")
    if (
        manifest.get("render_hash") != render_hash
        or manifest.get("chart_id") != selection.get("chart_id")
        or manifest.get("chart_type") != selection.get("chart_type")
        or manifest.get("task_id") != selection.get("task_id")
        or manifest.get("product_index") != selection.get("product_index")
    ):
        raise InvalidChartSelection("图表选择与渲染结果不一致")
    if (
        type(manifest.get("category_count")) is not int
        or not 1 <= manifest["category_count"] <= 2200
        or type(manifest.get("series_count")) is not int
        or not 1 <= manifest["series_count"] <= 20
        or manifest.get("width") != PNG_WIDTH
        or type(manifest.get("height")) is not int
        or not 1 <= manifest["height"] <= MAX_PNG_PIXELS // PNG_WIDTH
        or not isinstance(manifest.get("labels_hash"), str)
        or re.fullmatch(r"[0-9a-f]{64}", manifest["labels_hash"]) is None
    ):
        raise ExportRenderFailure("图表覆盖范围无效")
    return manifest


def generate_png(document: dict, selection: dict, destination: str) -> None:
    root = Path(os.environ.get("CHATBI_EXPORT_ROOT", "/opt/chatbi-export"))
    asset_root = root / "assets"
    try:
        runtime = verify_runtime_manifest(root)
        files = _read_assets(asset_root)
    except Exception as error:
        raise ExportRendererUnavailable("固定 PNG renderer 资源不可用") from error

    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import sync_playwright

    source = {key: value for key, value in document.items() if key != "export_time"}
    render_hash = _json_hash({"source": source, "selection": selection})
    payload = {
        "source": {**document, "kind": document.get("kind")},
        "selection": selection,
        "render_hash": render_hash,
    }
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
                    viewport={"width": PNG_WIDTH, "height": 1000},
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
                            content_type=_content_type(relative),
                            headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "no-store"},
                        )

                    context.route("**/*", fulfill_local_resources)
                    page = context.new_page()
                    page.set_default_timeout(45_000)
                    page.on("websocket", lambda socket: blocked.append(socket.url[:512]))
                    page.goto(RENDER_ORIGIN + "/", wait_until="load")
                    page.evaluate("request => window.__chatbiRenderChart(request)", payload)
                    render_deadline = time.monotonic() + 45
                    state = None
                    while time.monotonic() < render_deadline:
                        state = page.evaluate("() => window.__chatbiRenderState")
                        if isinstance(state, dict) and state.get("status") in {"ready", "failed"}:
                            break
                        time.sleep(0.05)
                    else:
                        raise ExportRendererUnavailable("固定 PNG renderer 未在时限内完成")
                    if not isinstance(state, dict) or state.get("status") != "ready":
                        code = state.get("code") if isinstance(state, dict) else None
                        if code == "EXPORT_SELECTION_INVALID":
                            raise InvalidChartSelection("所选图表不可用")
                        if code == "EXPORT_PIXEL_LIMIT":
                            raise ExportPixelLimit("完整图表超过 PNG 像素限制")
                        raise ExportRenderFailure("图表未能完整渲染")
                    manifest = _validate_manifest(state.get("manifest"), render_hash, selection)
                    actual = page.evaluate("() => ({width: document.documentElement.scrollWidth, height: document.documentElement.scrollHeight})")
                    if (
                        actual.get("width") != PNG_WIDTH
                        or not isinstance(actual.get("height"), int)
                        or actual["height"] != manifest["height"]
                        or actual["width"] * actual["height"] > MAX_PNG_PIXELS
                    ):
                        raise ExportPixelLimit("完整图表超过 PNG 像素限制")
                    if blocked:
                        raise ExportRenderFailure("渲染期间尝试访问未批准资源")
                    page.screenshot(path=output, full_page=True, animations="disabled", scale="css", type="png")
                finally:
                    context.close()
            finally:
                browser.close()
    except (InvalidChartSelection, ExportPixelLimit, ExportRendererUnavailable, ExportRenderFailure):
        raise
    except PlaywrightError as error:
        raise ExportRendererUnavailable("Chromium sandbox 或页面渲染不可用") from error
    except Exception as error:
        raise ExportRenderFailure("PNG 未能完整生成") from error

    size = output.stat().st_size
    if size <= 0 or size > MAX_PNG_BYTES:
        raise ExportPixelLimit("PNG 文件超过 20 MiB 限制")
    _png_dimensions(output)
