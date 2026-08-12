"""仅验证本地 BGE-M3 的模型加载、Dense 和 Sparse 输出。"""

from __future__ import annotations

import math
import os
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
MODEL_NAME = "BAAI/bge-m3"
DEFAULT_MODEL_DIR = ROOT / "models" / "bge-m3"


def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[key.strip()] = value
    return values


def configured_model_dir(env: dict[str, str]) -> Path:
    configured = env.get("BGE_MODEL_DIR", "models/bge-m3")
    model_dir = Path(configured)
    if not model_dir.is_absolute():
        model_dir = ROOT / model_dir
    return model_dir


def dense_norm(vector: Any) -> float:
    return math.sqrt(sum(float(value) * float(value) for value in vector))


def print_status(
    model_dir: Path,
    model_load: str,
    dense: str,
    sparse: str,
    validation: str,
) -> None:
    print(f"model={MODEL_NAME}")
    print(f"model_dir={model_dir}")
    print(f"model_load={model_load}")
    print(f"dense={dense}")
    print(f"sparse={sparse}")
    print("vectors=not_printed")
    print(f"validation_result={validation}")


def main() -> int:
    env = load_env(ROOT / ".env")
    model_dir = configured_model_dir(env)
    use_fp16 = env.get("BGE_USE_FP16", "false").lower() in {"1", "true", "yes"}

    # 模型获取与功能验证分离：验证阶段只允许读取项目内的本地模型，
    # 防止本地目录不完整时由 Transformers 隐式触发远程下载。
    if not model_dir.is_dir():
        print_status(
            model_dir,
            "BLOCKED (local_model_directory_missing)",
            "NOT_RUN",
            "NOT_RUN",
            "BLOCKED",
        )
        return 2

    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"

    try:
        from FlagEmbedding import BGEM3FlagModel

        model = BGEM3FlagModel(
            str(model_dir),
            use_fp16=use_fp16,
            local_files_only=True,
        )
    except Exception as exc:
        print_status(
            model_dir,
            f"BLOCKED ({type(exc).__name__})",
            "NOT_RUN",
            "NOT_RUN",
            "BLOCKED",
        )
        return 2

    texts = [
        "查询各区域的订单收入。",
        "统计不同产品线的销售数量和金额。",
        "查看每月各部门的费用情况。",
    ]
    try:
        output = model.encode(
            texts,
            batch_size=len(texts),
            max_length=8192,
            return_dense=True,
            return_sparse=True,
            return_colbert_vecs=False,
        )
    except Exception as exc:
        error = f"FAIL ({type(exc).__name__})"
        print_status(model_dir, "PASS", error, error, "FAIL")
        return 1

    dense_status = "PASS"
    sparse_status = "PASS"
    dense_vectors = output.get("dense_vecs")
    sparse_weights = output.get("lexical_weights")

    try:
        if dense_vectors is None:
            raise RuntimeError("dense_vecs_missing")
        if len(dense_vectors) != len(texts):
            raise RuntimeError("dense_result_count_mismatch")
        if getattr(dense_vectors, "ndim", None) != 2:
            raise RuntimeError("dense_embedding_not_two_dimensional")
        dense_dimension = int(dense_vectors.shape[1])
        norms = [dense_norm(vector) for vector in dense_vectors]
        if dense_dimension <= 0 or not all(
            math.isfinite(value) and value > 0 for value in norms
        ):
            raise RuntimeError("dense_embedding_invalid")
    except Exception as exc:
        dense_status = f"FAIL ({type(exc).__name__})"
        dense_dimension = 0
        norms = []

    try:
        if sparse_weights is None:
            raise RuntimeError("lexical_weights_missing")
        if len(sparse_weights) != len(texts):
            raise RuntimeError("sparse_result_count_mismatch")
        sparse_nonzero_counts = [len(weights) for weights in sparse_weights]
        if any(count <= 0 for count in sparse_nonzero_counts):
            raise RuntimeError("sparse_embedding_empty")
    except Exception as exc:
        sparse_status = f"FAIL ({type(exc).__name__})"
        sparse_nonzero_counts = []

    validation = dense_status == "PASS" and sparse_status == "PASS"
    print_status(
        model_dir,
        "PASS",
        dense_status,
        sparse_status,
        "PASS" if validation else "FAIL",
    )
    if dense_status == "PASS":
        print(f"dense_dimension={dense_dimension}")
        print(f"dense_norms={[round(value, 4) for value in norms]}")
    if sparse_status == "PASS":
        print(f"sparse_nonzero_counts={sparse_nonzero_counts}")

    if validation:
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
