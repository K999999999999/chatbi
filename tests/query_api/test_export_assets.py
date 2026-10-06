from __future__ import annotations

import hashlib
import json

import pytest

from src.query_api import export_assets
from src.query_api.export_assets import frontend_source_hash, verify_bundle


def _write_bundle(root, source_hash="source"):
    assets = root / "assets"
    assets.mkdir(parents=True)
    payload = b"<!doctype html><html></html>"
    (assets / "export.html").write_bytes(payload)
    (assets / "bundle-manifest.json").write_text(
        json.dumps(
            {
                "version": 1,
                "source_sha256": source_hash,
                "files": {
                    "export.html": {
                        "sha256": hashlib.sha256(payload).hexdigest(),
                        "size": len(payload),
                    }
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return assets


def test_offline_bundle_manifest_verifies_all_file_hashes(tmp_path):
    assets = _write_bundle(tmp_path)
    assert verify_bundle(assets)["version"] == 1
    (assets / "export.html").write_text("changed", encoding="utf-8")
    with pytest.raises(ValueError, match="指纹不匹配"):
        verify_bundle(assets)


def test_development_source_hash_binds_the_export_bundle(tmp_path):
    source = tmp_path / "source"
    (source / "src").mkdir(parents=True)
    for filename in (
        "export.html",
        "vite.export.config.ts",
        "tsconfig.json",
        "package.json",
        "package-lock.json",
    ):
        (source / filename).write_text(filename, encoding="utf-8")
    (source / "src" / "chart.ts").write_text("chart", encoding="utf-8")
    expected = frontend_source_hash(source)
    assets = _write_bundle(tmp_path, expected)
    assert verify_bundle(assets, source)["source_sha256"] == expected
    (source / "tsconfig.json").write_text("changed", encoding="utf-8")
    with pytest.raises(ValueError, match="源码不一致"):
        verify_bundle(assets, source)


def test_runtime_manifest_binds_separate_chart_and_pdf_fonts(tmp_path, monkeypatch):
    _write_bundle(tmp_path)
    browser_root = tmp_path / "browsers"
    browser_root.mkdir()
    executable = browser_root / "chromium"
    executable.write_bytes(b"chromium")
    executable.chmod(0o755)

    chart_font = tmp_path / "noto.ttc"
    pdf_font = tmp_path / "wqy.ttc"
    chart_font.write_bytes(b"noto font")
    pdf_font.write_bytes(b"wqy font")
    matches = {
        "Noto Sans CJK SC": chart_font,
        "WenQuanYi Zen Hei": pdf_font,
    }
    monkeypatch.setattr(
        export_assets, "_playwright_executable", lambda: str(executable)
    )
    monkeypatch.setattr(
        export_assets, "_fontconfig_file", lambda family: matches[family]
    )
    monkeypatch.setattr(export_assets.importlib.metadata, "version", lambda _: "1.0.0")

    export_assets.write_runtime_manifest(
        tmp_path,
        browser_root,
        chart_font,
        pdf_font,
        chart_font_package_version="1:20220127+repack1-1",
        pdf_font_package_version="0.9.45-8",
    )

    runtime = export_assets.verify_runtime_manifest(tmp_path)
    assert runtime["font_paths"] == {
        "chart": chart_font.resolve(),
        "pdf": pdf_font.resolve(),
    }
    manifest = json.loads(
        (tmp_path / "runtime-manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["fonts"]["chart"]["package_version"] == "1:20220127+repack1-1"
    assert manifest["fonts"]["pdf"]["package_version"] == "0.9.45-8"

    pdf_font.write_bytes(b"changed font")
    with pytest.raises(ValueError, match="字体指纹不匹配"):
        export_assets.verify_runtime_manifest(tmp_path)
