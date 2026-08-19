"""Offline Pipeline file access and BGE-M3 representation generation."""

import json
import math
from pathlib import Path
from typing import Any

from FlagEmbedding import BGEM3FlagModel
from qdrant_client import QdrantClient
from qdrant_client.http.models import (
    Distance,
    PointStruct,
    SparseVector,
    SparseVectorParams,
    VectorParams,
)


DENSE_VECTOR_NAME = "dense"
SPARSE_VECTOR_NAME = "sparse"
DENSE_DIMENSION = 1024


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


def create_qdrant_client(
    url: str = "http://127.0.0.1:6333",
    *,
    timeout: int = 20,
) -> QdrantClient:
    """Create the one V1 Qdrant client with the current local proxy bypass."""

    return QdrantClient(
        url=url,
        timeout=timeout,
        trust_env=False,
        check_compatibility=False,
    )


def create_candidate_collection(client: QdrantClient, collection_name: str) -> None:
    """Create one candidate collection with the shared V1 named-vector schema."""

    client.create_collection(
        collection_name=collection_name,
        vectors_config={
            DENSE_VECTOR_NAME: VectorParams(
                size=DENSE_DIMENSION,
                distance=Distance.COSINE,
            )
        },
        sparse_vectors_config={SPARSE_VECTOR_NAME: SparseVectorParams()},
    )


def build_qdrant_point(
    point_id: str,
    *,
    dense: tuple[float, ...],
    sparse: dict[int, float],
    payload: dict[str, Any],
) -> PointStruct:
    """Convert neutral M3 representations into one physical Qdrant point."""

    sparse_items = sorted(sparse.items(), key=lambda item: item[0])
    return PointStruct(
        id=point_id,
        vector={
            DENSE_VECTOR_NAME: list(dense),
            SPARSE_VECTOR_NAME: SparseVector(
                indices=[index for index, _ in sparse_items],
                values=[weight for _, weight in sparse_items],
            ),
        },
        payload=payload,
    )


def upsert_qdrant_points(
    client: QdrantClient,
    collection_name: str,
    points: list[PointStruct],
) -> None:
    """Write precomputed points without invoking any embedding provider."""

    if points:
        client.upsert(collection_name=collection_name, points=points, wait=True)


def count_qdrant_points(client: QdrantClient, collection_name: str) -> int:
    return int(client.count(collection_name=collection_name, exact=True).count)


def scroll_qdrant_points(client: QdrantClient, collection_name: str) -> list[Any]:
    """Read all points and explicitly request both vectors and payload."""

    points: list[Any] = []
    offset = None
    while True:
        batch, next_offset = client.scroll(
            collection_name=collection_name,
            offset=offset,
            limit=256,
            with_payload=True,
            with_vectors=True,
        )
        points.extend(batch)
        if next_offset is None:
            return points
        if next_offset == offset:
            raise RuntimeError("Qdrant scroll offset did not advance")
        offset = next_offset


def delete_qdrant_collection(client: QdrantClient, collection_name: str) -> None:
    client.delete_collection(collection_name=collection_name)
