"""Offline Pipeline file access and BGE-M3 representation generation."""

import json
import math
from pathlib import Path
from typing import Any

from FlagEmbedding import BGEM3FlagModel


class ResourceReadError(RuntimeError):
    """Raised when an explicitly supplied resource file cannot be read."""


def read_json_file(path: Path) -> Any:
    """Read one explicitly supplied UTF-8 JSON file without discovering others."""

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ResourceReadError(f"Unable to read JSON resource: {path}") from exc


def encode_bge_m3(
    texts: list[str],
    *,
    model_path: Path,
    device: str = "cpu",
    batch_size: int | None = None,
) -> tuple[list[tuple[float, ...]], list[dict[int, float]]]:
    """Encode one text batch with BGE-M3 and return neutral Python values."""

    if not texts:
        raise ValueError("M3 input batch must not be empty")

    model = BGEM3FlagModel(
        str(model_path),
        use_fp16=False,
        devices=device,
        return_dense=True,
        return_sparse=True,
        return_colbert_vecs=False,
    )

    encode_kwargs = {
        "return_dense": True,
        "return_sparse": True,
        "return_colbert_vecs": False,
    }
    if batch_size is not None:
        encode_kwargs["batch_size"] = batch_size

    output = model.encode(texts, **encode_kwargs)
    if not isinstance(output, dict):
        raise ValueError("BGE-M3 output must be a mapping")
    if output.get("dense_vecs") is None:
        raise ValueError("BGE-M3 dense output is missing")
    if output.get("lexical_weights") is None:
        raise ValueError("BGE-M3 sparse output is missing")
    if output.get("colbert_vecs") is not None:
        raise ValueError("BGE-M3 ColBERT output must be disabled")

    try:
        dense_vectors = [
            tuple(_require_finite_float(value) for value in row)
            for row in output["dense_vecs"]
        ]
        sparse_vectors = [
            _normalize_sparse_weights(item)
            for item in output["lexical_weights"]
        ]
    except (TypeError, ValueError, KeyError) as exc:
        raise ValueError("BGE-M3 output structure is invalid") from exc

    if len(dense_vectors) != len(texts):
        raise ValueError("BGE-M3 dense output count does not match input count")
    if len(sparse_vectors) != len(texts):
        raise ValueError("BGE-M3 sparse output count does not match input count")
    if not dense_vectors or any(not vector for vector in dense_vectors):
        raise ValueError("BGE-M3 dense output contains an empty vector")
    if not sparse_vectors or any(not weights for weights in sparse_vectors):
        raise ValueError("BGE-M3 sparse output contains empty lexical weights")

    dense_dimension = len(dense_vectors[0])
    if any(len(vector) != dense_dimension for vector in dense_vectors):
        raise ValueError("BGE-M3 dense dimensions are inconsistent")

    return dense_vectors, sparse_vectors


def _require_finite_float(value: object) -> float:
    converted = float(value)
    if not math.isfinite(converted):
        raise ValueError("Representation value must be finite")
    return converted


def _normalize_sparse_weights(raw_weights: object) -> dict[int, float]:
    if not hasattr(raw_weights, "items"):
        raise ValueError("Sparse lexical weights must be a mapping")

    normalized: dict[int, float] = {}
    for raw_index, raw_weight in raw_weights.items():
        try:
            index = int(raw_index)
        except (TypeError, ValueError) as exc:
            raise ValueError("Sparse dimension index must be an integer") from exc
        if index < 0:
            raise ValueError("Sparse dimension index must not be negative")
        if index in normalized:
            raise ValueError("Sparse dimension indexes must be unique")
        normalized[index] = _require_finite_float(raw_weight)

    if len(normalized) != len(raw_weights):
        raise ValueError("Sparse normalization changed the number of dimensions")
    return normalized
