"""校验导出渲染 bundle、Chromium 与字体的固定构建身份。"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import stat
from pathlib import Path, PurePosixPath


def _digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def _regular_file(path: Path, *, maximum: int = 20 * 1024 * 1024) -> os.stat_result:
    info = path.lstat()
    if (
        not stat.S_ISREG(info.st_mode)
        or info.st_size > maximum
        or info.st_mode & 0o022
    ):
        raise ValueError("导出资源不是受保护的普通文件")
    return info


def _read_json(path: Path, *, maximum: int = 2 * 1024 * 1024) -> dict:
    _regular_file(path, maximum=maximum)
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError("导出资源清单格式无效")
    return value


def frontend_source_hash(source_root: Path) -> str:
    files: list[Path] = []
    source_dir = source_root / "src"
    for current, directories, names in os.walk(source_dir, followlinks=False):
        current_path = Path(current)
        if current_path.is_symlink() or any((current_path / name).is_symlink() for name in directories):
            raise ValueError("开发图形源码不能包含符号链接")
        files.extend(current_path / name for name in names)
    files.extend(
        source_root / name
        for name in (
            "export.html",
            "vite.export.config.ts",
            "tsconfig.json",
            "package.json",
            "package-lock.json",
        )
    )
    digest = hashlib.sha256()
    for path in sorted(files):
        relative = path.relative_to(source_root).as_posix()
        _regular_file(path, maximum=30 * 1024 * 1024)
        digest.update(relative.encode())
        digest.update(b"\0")
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        digest.update(b"\0")
    return digest.hexdigest()


def verify_bundle(asset_root: Path, source_root: Path | None = None) -> dict:
    if asset_root.is_symlink() or not asset_root.is_dir():
        raise ValueError("PNG 离线资源目录不可用")
    manifest_path = asset_root / "bundle-manifest.json"
    manifest = _read_json(manifest_path)
    files = manifest.get("files")
    if manifest.get("version") != 1 or not isinstance(files, dict) or "export.html" not in files:
        raise ValueError("PNG bundle 清单版本无效")
    for name, expected in files.items():
        relative = PurePosixPath(name) if isinstance(name, str) else None
        if (
            relative is None
            or relative.is_absolute()
            or not relative.parts
            or any(part in {"", ".", ".."} for part in relative.parts)
            or not isinstance(expected, dict)
            or not isinstance(expected.get("sha256"), str)
            or len(expected["sha256"]) != 64
            or type(expected.get("size")) is not int
            or expected["size"] < 0
        ):
            raise ValueError("PNG bundle 文件清单无效")
        path = asset_root.joinpath(*relative.parts)
        _regular_file(path, maximum=10 * 1024 * 1024)
        if path.stat().st_size != expected["size"] or _digest(path) != expected["sha256"]:
            raise ValueError("PNG bundle 文件指纹不匹配")
    if source_root is not None and frontend_source_hash(source_root) != manifest.get("source_sha256"):
        raise ValueError("PNG bundle 与当前开发图形源码不一致，请重建开发镜像")
    return manifest


def write_runtime_manifest(root: Path, browser_root: Path, font_path: Path) -> None:
    asset_root = root / "assets"
    bundle = verify_bundle(asset_root)
    if browser_root.is_symlink() or not browser_root.is_dir():
        raise ValueError("Playwright 浏览器目录不可用")
    executable = Path(_playwright_executable())
    resolved_browser_root = browser_root.resolve(strict=True)
    resolved_executable = executable.resolve(strict=True)
    if resolved_browser_root not in resolved_executable.parents or not os.access(executable, os.X_OK):
        raise ValueError("Playwright Chromium 安装位置无效")
    _regular_file(font_path, maximum=100 * 1024 * 1024)
    payload = {
        "version": 1,
        "bundle_manifest_sha256": _digest(asset_root / "bundle-manifest.json"),
        "playwright_version": importlib.metadata.version("playwright"),
        "browser_root": str(resolved_browser_root),
        "chromium_executable": str(resolved_executable),
        "font_path": str(font_path.resolve(strict=True)),
        "font_sha256": _digest(font_path),
        "frontend_source_sha256": bundle["source_sha256"],
    }
    output = root / "runtime-manifest.json"
    output.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
    output.chmod(0o644)


def verify_runtime_manifest(
    root: Path, source_root: Path | None = None
) -> dict:
    asset_root = root / "assets"
    bundle = verify_bundle(asset_root, source_root)
    runtime = _read_json(root / "runtime-manifest.json")
    browser_root = Path(runtime.get("browser_root", ""))
    executable = Path(runtime.get("chromium_executable", ""))
    font_path = Path(runtime.get("font_path", ""))
    if runtime.get("version") != 1 or runtime.get("bundle_manifest_sha256") != _digest(
        asset_root / "bundle-manifest.json"
    ):
        raise ValueError("PNG 运行资源与 bundle 不匹配")
    if runtime.get("frontend_source_sha256") != bundle.get("source_sha256"):
        raise ValueError("PNG 图形源码指纹不匹配")
    if runtime.get("playwright_version") != importlib.metadata.version("playwright"):
        raise ValueError("Playwright 与浏览器版本不匹配")
    if (
        browser_root.is_symlink()
        or not browser_root.is_dir()
        or executable.is_symlink()
        or not executable.is_file()
        or browser_root.resolve(strict=True) not in executable.resolve(strict=True).parents
        or not os.access(executable, os.X_OK)
    ):
        raise ValueError("Playwright Chromium 不可用")
    _regular_file(font_path, maximum=100 * 1024 * 1024)
    if runtime.get("font_sha256") != _digest(font_path):
        raise ValueError("PNG 中文字体指纹不匹配")
    return {
        "asset_root": asset_root,
        "browser_root": browser_root,
        "chromium_executable": executable,
        "font_path": font_path,
    }


def _playwright_executable() -> str:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        return playwright.chromium.executable_path


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("/opt/chatbi-export"))
    parser.add_argument("--browser-root", type=Path, default=Path("/opt/chatbi-export/browsers"))
    parser.add_argument("--font-path", type=Path, required=True)
    options = parser.parse_args()
    write_runtime_manifest(options.root, options.browser_root, options.font_path)
