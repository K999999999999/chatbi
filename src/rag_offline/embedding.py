"""Embedding Provider（向量化提供者）及 BGE-M3 适配器。"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import math
from typing import Any, Protocol


class EmbeddingError(RuntimeError):
    """Embedding 调用或输出校验失败。"""


@dataclass(frozen=True, slots=True)
class SparseEmbedding:
    """Qdrant SparseVector（稀疏向量）的可序列化表示。"""

    indices: tuple[int, ...]
    values: tuple[float, ...]

    def __post_init__(self) -> None:
        if len(self.indices) != len(self.values):
            raise EmbeddingError("稀疏向量的索引和值数量不一致")
        if any(not isinstance(index, int) or index < 0 for index in self.indices):
            raise EmbeddingError("稀疏向量索引必须是非负整数")
        if tuple(sorted(set(self.indices))) != self.indices:
            raise EmbeddingError("稀疏向量索引必须严格递增且不能重复")
        if any(not math.isfinite(value) for value in self.values):
            raise EmbeddingError("稀疏向量包含非有限数值")


@dataclass(frozen=True, slots=True)
class EmbeddedText:
    """一段文本对应的 dense 和 sparse 向量。"""

    dense: tuple[float, ...]
    sparse: SparseEmbedding

    def __post_init__(self) -> None:
        if not self.dense:
            raise EmbeddingError("dense 向量不能为空")
        if any(not math.isfinite(value) for value in self.dense):
            raise EmbeddingError("dense 向量包含非有限数值")

    @property
    def dimension(self) -> int:
        return len(self.dense)


class EmbeddingProvider(Protocol):
    """离线构建所需的最小向量化契约。"""

    @property
    def dimension(self) -> int:
        """返回 dense 向量维度。"""

    @property
    def config(self) -> Mapping[str, Any]:
        """返回可写入构建清单的非敏感配置。"""

    def embed_documents(self, texts: Sequence[str]) -> tuple[EmbeddedText, ...]:
        """只接收 page_content，返回与输入一一对应的向量。"""

    def embed_query(self, text: str) -> EmbeddedText:
        """将评测查询向量化。"""


class BgeM3EmbeddingProvider:
    """基于 FlagEmbedding.BGEM3FlagModel 的 BGE-M3 适配器。

    模型在第一次调用时才加载，避免仅运行事实源和契约测试时引入模型运行时。
    """

    MODEL_DIMENSION = 1024

    def __init__(
        self,
        model_name_or_path: str = "BAAI/bge-m3",
        *,
        batch_size: int = 8,
        use_fp16: bool = False,
        devices: str | list[str] | None = None,
        model: Any | None = None,
    ) -> None:
        if not model_name_or_path.strip():
            raise EmbeddingError("Embedding 模型路径不能为空")
        if batch_size <= 0:
            raise EmbeddingError("Embedding batch_size 必须为正数")
        self.model_name_or_path = model_name_or_path
        self.batch_size = batch_size
        self.use_fp16 = use_fp16
        self.devices = devices
        self._model = model

    @property
    def dimension(self) -> int:
        return self.MODEL_DIMENSION

    @property
    def config(self) -> Mapping[str, Any]:
        return {
            "provider": "FlagEmbedding.BGEM3FlagModel",
            "model": self.model_name_or_path,
            "dimension": self.dimension,
            "dense": True,
            "sparse": True,
            "use_fp16": self.use_fp16,
            "batch_size": self.batch_size,
            "devices": self.devices,
        }

    def embed_documents(self, texts: Sequence[str]) -> tuple[EmbeddedText, ...]:
        normalized = _validate_texts(texts, "documents")
        if not normalized:
            return ()
        model = self._load_model()
        try:
            output = model.encode(
                normalized,
                batch_size=self.batch_size,
                return_dense=True,
                return_sparse=True,
                return_colbert_vecs=False,
            )
        except Exception as exc:
            raise EmbeddingError(f"文档 Embedding 调用失败：{exc}") from exc
        return _parse_output(output, len(normalized), self.dimension)

    def embed_query(self, text: str) -> EmbeddedText:
        normalized = _validate_texts((text,), "query")
        model = self._load_model()
        try:
            encode_queries = getattr(model, "encode_queries", None)
            if encode_queries is None:
                output = model.encode(
                    normalized,
                    batch_size=1,
                    return_dense=True,
                    return_sparse=True,
                    return_colbert_vecs=False,
                )
            else:
                output = encode_queries(
                    normalized,
                    batch_size=1,
                    return_dense=True,
                    return_sparse=True,
                    return_colbert_vecs=False,
                )
        except Exception as exc:
            raise EmbeddingError(f"查询 Embedding 调用失败：{exc}") from exc
        return _parse_output(output, 1, self.dimension)[0]

    def _load_model(self) -> Any:
        if self._model is not None:
            return self._model
        try:
            from FlagEmbedding import BGEM3FlagModel
        except ImportError as exc:
            raise EmbeddingError(
                "未安装 FlagEmbedding，无法加载 BGE-M3；请先同步项目依赖"
            ) from exc
        try:
            self._model = BGEM3FlagModel(
                self.model_name_or_path,
                use_fp16=self.use_fp16,
                devices=self.devices,
            )
        except Exception as exc:
            raise EmbeddingError(
                f"无法加载 Embedding 模型 {self.model_name_or_path}：{exc}"
            ) from exc
        return self._model


def _validate_texts(texts: Sequence[str], label: str) -> tuple[str, ...]:
    normalized = tuple(texts)
    for index, text in enumerate(normalized, 1):
        if not isinstance(text, str) or not text.strip():
            raise EmbeddingError(f"{label} 第 {index} 段文本不能为空")
    return normalized


def _parse_output(
    output: Any,
    expected_count: int,
    dimension: int,
) -> tuple[EmbeddedText, ...]:
    dense_rows = _get_output_value(output, "dense_vecs")
    sparse_rows = _get_output_value(output, "lexical_weights")
    if dense_rows is None or sparse_rows is None:
        raise EmbeddingError("Embedding 输出必须同时包含 dense_vecs 和 lexical_weights")
    if len(dense_rows) != expected_count or len(sparse_rows) != expected_count:
        raise EmbeddingError("Embedding 输出数量与输入文本数量不一致")

    embeddings: list[EmbeddedText] = []
    for index, (dense_row, sparse_row) in enumerate(
        zip(dense_rows, sparse_rows, strict=True),
        1,
    ):
        dense = _to_float_tuple(dense_row, f"dense_vecs 第 {index} 条")
        if len(dense) != dimension:
            raise EmbeddingError(
                f"dense_vecs 第 {index} 条维度为 {len(dense)}，期望 {dimension}"
            )
        if any(not math.isfinite(value) for value in dense):
            raise EmbeddingError(f"dense_vecs 第 {index} 条包含非有限数值")
        sparse = _parse_sparse(sparse_row, index)
        embeddings.append(EmbeddedText(dense=dense, sparse=sparse))
    return tuple(embeddings)


def _get_output_value(output: Any, key: str) -> Any:
    if isinstance(output, Mapping):
        return output.get(key)
    return getattr(output, key, None)


def _to_float_tuple(value: Any, label: str) -> tuple[float, ...]:
    if hasattr(value, "tolist"):
        value = value.tolist()
    try:
        return tuple(float(item) for item in value)
    except (TypeError, ValueError) as exc:
        raise EmbeddingError(f"{label} 不是有效数值数组") from exc


def _parse_sparse(value: Any, index: int) -> SparseEmbedding:
    if hasattr(value, "items"):
        items = value.items()
    else:
        try:
            items = value
        except TypeError as exc:
            raise EmbeddingError(f"lexical_weights 第 {index} 条格式无效") from exc

    normalized: dict[int, float] = {}
    try:
        for raw_key, raw_value in items:
            key = int(raw_key)
            weight = float(raw_value)
            if not math.isfinite(weight):
                raise EmbeddingError(f"lexical_weights 第 {index} 条包含非有限数值")
            if weight != 0.0:
                normalized[key] = weight
    except (TypeError, ValueError) as exc:
        raise EmbeddingError(f"lexical_weights 第 {index} 条格式无效") from exc
    return SparseEmbedding(
        indices=tuple(sorted(normalized)),
        values=tuple(normalized[key] for key in sorted(normalized)),
    )
