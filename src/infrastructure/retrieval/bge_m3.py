"""BGE-M3 本地 Dense + Sparse 编码适配器。"""

from __future__ import annotations

import math
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from langchain_core.documents import Document
from qdrant_client import models


BGE_DENSE_DIMENSION = 1024


@dataclass(frozen=True)
class EncodedText:
    """一次 BGE-M3 编码得到的 Dense 和 Sparse 结果。"""

    dense: list[float]
    sparse: models.SparseVector


class BGE_M3Encoder:
    """只从本地模型目录加载 BGE-M3，并一次批量生成两种向量。"""

    def __init__(self, model_dir: str | Path, *, use_fp16: bool = False) -> None:
        self.model_dir = Path(model_dir)
        if not self.model_dir.is_dir():
            raise FileNotFoundError(f"BGE model directory not found: {self.model_dir}")

        # 离线索引阶段禁止 Transformers 在本地文件不完整时隐式联网。
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"

        from FlagEmbedding import BGEM3FlagModel

        self._model = BGEM3FlagModel(
            str(self.model_dir),
            use_fp16=use_fp16,
            local_files_only=True,
        )

    @property
    def dense_dimension(self) -> int:
        return BGE_DENSE_DIMENSION

    def encode_documents(self, documents: Sequence[Document]) -> list[EncodedText]:
        """批量编码 Document.page_content，不重新加载模型。"""

        return self.encode_texts([document.page_content for document in documents])

    def encode_texts(self, texts: Sequence[str]) -> list[EncodedText]:
        """一次推理同时返回 Dense 和 Sparse 结果。"""

        if not texts:
            return []

        output = self._model.encode(
            list(texts),
            batch_size=len(texts),
            max_length=8192,
            return_dense=True,
            return_sparse=True,
            return_colbert_vecs=False,
        )
        dense_vectors = output.get("dense_vecs")
        sparse_weights = output.get("lexical_weights")
        if dense_vectors is None or sparse_weights is None:
            raise ValueError("BGE-M3 output must contain dense_vecs and lexical_weights")
        if len(dense_vectors) != len(texts) or len(sparse_weights) != len(texts):
            raise ValueError("BGE-M3 output count does not match input text count")
        if getattr(dense_vectors, "ndim", None) != 2:
            raise ValueError("BGE-M3 Dense output must be a two-dimensional matrix")
        if int(dense_vectors.shape[1]) != BGE_DENSE_DIMENSION:
            raise ValueError(
                f"BGE-M3 Dense dimension must be {BGE_DENSE_DIMENSION}, "
                f"got {dense_vectors.shape[1]}"
            )

        encoded: list[EncodedText] = []
        for dense_vector, lexical_weights in zip(
            dense_vectors, sparse_weights, strict=True
        ):
            dense = [float(value) for value in dense_vector.tolist()]
            if not all(math.isfinite(value) for value in dense):
                raise ValueError("BGE-M3 Dense output contains a non-finite value")
            if not isinstance(lexical_weights, Mapping) or not lexical_weights:
                raise ValueError("BGE-M3 Sparse output is empty")

            pairs = sorted(
                (int(index), float(value))
                for index, value in lexical_weights.items()
            )
            indices = [index for index, _ in pairs]
            values = [value for _, value in pairs]
            if not indices or len(indices) != len(values):
                raise ValueError("BGE-M3 Sparse output has invalid indices/values")
            if not all(math.isfinite(value) for value in values):
                raise ValueError("BGE-M3 Sparse output contains a non-finite value")

            encoded.append(
                EncodedText(
                    dense=dense,
                    sparse=models.SparseVector(indices=indices, values=values),
                )
            )

        return encoded
