"""Metadata Export 的本地输入和配置读取。"""

from collections.abc import Mapping
import json
from pathlib import Path
from typing import Any

from .export_schema_models import ColumnIdentity, MetadataExportError


def load_column_value_examples(
    columns_path: Path,
) -> dict[ColumnIdentity, tuple[str, ...]]:
    """读取并校验已有 columns.json 中的字段值示例。"""

    if not columns_path.exists():
        return {}

    try:
        records = json.loads(columns_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise MetadataExportError("已有 columns.json 无法读取") from exc

    if not isinstance(records, list):
        raise MetadataExportError("已有 columns.json 必须是 JSON 数组")

    examples_by_column: dict[ColumnIdentity, tuple[str, ...]] = {}
    seen_columns: set[ColumnIdentity] = set()
    for record in records:
        if not isinstance(record, dict):
            raise MetadataExportError("已有 columns.json 的记录必须是 JSON 对象")
        identity = _column_identity(record)
        if identity in seen_columns:
            raise MetadataExportError("已有 columns.json 存在重复字段")
        seen_columns.add(identity)

        if "value_examples" not in record:
            continue
        values = record["value_examples"]
        if not isinstance(values, list):
            raise MetadataExportError("value_examples 必须是字符串数组")

        normalized: list[str] = []
        for value in values:
            if not isinstance(value, str) or not value.strip():
                raise MetadataExportError("value_examples 不能包含空值")
            normalized.append(value.strip())
        if len(set(normalized)) != len(normalized):
            raise MetadataExportError("value_examples 不能包含重复值")
        if normalized:
            examples_by_column[identity] = tuple(normalized)

    return examples_by_column


def _column_identity(record: Mapping[str, Any]) -> ColumnIdentity:
    values: list[str] = []
    for field in ("schema_name", "table_name", "column_name"):
        value = record.get(field)
        if not isinstance(value, str) or not value.strip():
            raise MetadataExportError(f"已有 columns.json 缺少有效的 {field}")
        values.append(value.strip())
    return values[0], values[1], values[2]


def load_env(path: Path) -> dict[str, str]:
    """读取本地连接配置，不输出任何 Secret（敏感信息）。"""

    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[key.strip()] = value
    return values


def connection_config(env: dict[str, str]) -> dict[str, Any]:
    """构造只用于本地元数据读取的 PostgreSQL 连接配置。"""

    required = ("POSTGRES_MIGRATOR_USER", "POSTGRES_MIGRATOR_PASSWORD")
    missing = [key for key in required if not env.get(key)]
    if missing:
        raise MetadataExportError(f".env 缺少必要配置：{', '.join(missing)}")
    return {
        "host": env.get("POSTGRES_HOST", "127.0.0.1"),
        "port": int(env.get("POSTGRES_PORT", "5432")),
        "dbname": env.get("POSTGRES_DB", "chatbi_mvp"),
        "user": env["POSTGRES_MIGRATOR_USER"],
        "password": env["POSTGRES_MIGRATOR_PASSWORD"],
        "connect_timeout": 10,
    }
