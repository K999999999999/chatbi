"""Read-only comparison of live PostgreSQL structure and exported metadata."""

import json
from pathlib import Path
from typing import Any

import psycopg

from scripts.metadata.export_schema_database import extract_schema
from scripts.metadata.export_schema_models import MetadataExportError
from scripts.metadata.export_schema_output import project_outputs
from src.rag_offline.sources import DEFAULT_STRUCTURE_DIR


class StructureMetadataMismatchError(RuntimeError):
    """Live PostgreSQL structure does not match its exported projection."""


def verify_catalog_matches_metadata(
    connection: Any,
    structure_dir: Path = DEFAULT_STRUCTURE_DIR,
) -> None:
    """Compare catalog tables, columns and relationships with exported JSON."""

    try:
        actual = project_outputs(extract_schema(connection))
        expected = {
            name: _read_records(structure_dir / f"{name}.json", name)
            for name in ("tables", "columns", "relationships")
        }
    except StructureMetadataMismatchError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError, MetadataExportError) as exc:
        raise StructureMetadataMismatchError(
            f"无法读取或投影 PostgreSQL Structure Metadata：{type(exc).__name__}"
        ) from None
    except psycopg.Error as exc:
        # Database driver errors may contain connection details; expose only the
        # failure type at the production readiness boundary.
        raise StructureMetadataMismatchError(
            f"无法读取 PostgreSQL Schema catalog：{type(exc).__name__}"
        ) from None

    for name in ("tables", "columns", "relationships"):
        expected_records = expected[name]
        if name == "columns":
            expected_records = [
                {key: value for key, value in record.items() if key != "value_examples"}
                for record in expected_records
            ]
        if _canonical_records(expected_records) != _canonical_records(actual[name]):
            raise StructureMetadataMismatchError(
                f"PostgreSQL {name} 与 Structure Metadata 不一致；请从数据库重新导出结构"
            )


def _read_records(path: Path, label: str) -> list[dict[str, Any]]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise StructureMetadataMismatchError(
            f"缺少 Structure Metadata：{label}"
        ) from None
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise StructureMetadataMismatchError(
            f"Structure Metadata 无法读取：{label}"
        ) from None
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise StructureMetadataMismatchError(f"Structure Metadata 格式无效：{label}")
    return value


def _canonical_records(records: list[dict[str, Any]]) -> tuple[str, ...]:
    return tuple(
        sorted(
            json.dumps(
                record, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            )
            for record in records
        )
    )
