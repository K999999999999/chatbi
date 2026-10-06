from __future__ import annotations

import hashlib
import json

import pytest

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
    for filename in ("export.html", "vite.export.config.ts", "tsconfig.json", "package.json", "package-lock.json"):
        (source / filename).write_text(filename, encoding="utf-8")
    (source / "src" / "chart.ts").write_text("chart", encoding="utf-8")
    expected = frontend_source_hash(source)
    assets = _write_bundle(tmp_path, expected)
    assert verify_bundle(assets, source)["source_sha256"] == expected
    (source / "tsconfig.json").write_text("changed", encoding="utf-8")
    with pytest.raises(ValueError, match="源码不一致"):
        verify_bundle(assets, source)
