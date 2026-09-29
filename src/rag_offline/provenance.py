"""Stable fingerprints for RAG source facts and build configuration."""

import hashlib
import json
from collections.abc import Mapping
from typing import Any

from .sources import Facts


def build_provenance(
    facts: Facts,
    embedding_config: Mapping[str, Any],
) -> dict[str, str]:
    """Return non-secret hashes identifying the exact build inputs."""

    source_hashes = facts.source_hashes or {}
    structure_payload: Any
    if all(name in source_hashes for name in ("tables", "columns", "relationships")):
        structure_payload = {
            name: source_hashes[name] for name in ("tables", "columns", "relationships")
        }
    else:
        structure_payload = {
            "tables": facts.tables,
            "columns": facts.columns,
            "relationships": facts.relationships,
        }

    schema_fingerprint = _sha256(structure_payload)
    metrics_fingerprint = source_hashes.get("metrics") or _sha256(facts.metrics)
    embedding_fingerprint = _sha256(embedding_config)
    source_fingerprint = _sha256(
        {
            "schema_metadata_sha256": schema_fingerprint,
            "metrics_sha256": metrics_fingerprint,
            "embedding_config_sha256": embedding_fingerprint,
        }
    )
    return {
        "schema_metadata_sha256": schema_fingerprint,
        "metrics_sha256": metrics_fingerprint,
        "embedding_config_sha256": embedding_fingerprint,
        "source_sha256": source_fingerprint,
    }


def _sha256(value: Any) -> str:
    canonical = json.dumps(
        _json_value(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _json_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"Unsupported fingerprint value: {type(value).__name__}")
