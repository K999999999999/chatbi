"""提供 Query Understanding（查询理解）可使用的指标名称词汇。"""

import json
from functools import lru_cache
from pathlib import Path

DEFAULT_METRICS_PATH = Path(__file__).with_name("metrics.json")
MetricVocabulary = tuple[tuple[str, tuple[str, ...]], ...]


@lru_cache(maxsize=8)
def load_metric_vocabulary(
    metrics_path: Path = DEFAULT_METRICS_PATH,
) -> MetricVocabulary:
    """从指标事实源读取规范名称和别名，不加载实现或物理资源信息。"""

    try:
        records = json.loads(metrics_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise ValueError("指标名称词汇无法读取") from None
    if not isinstance(records, list) or not records:
        raise ValueError("指标名称词汇格式无效")

    vocabulary: list[tuple[str, tuple[str, ...]]] = []
    for record in records:
        if not isinstance(record, dict):
            raise TypeError("指标名称词汇格式无效")
        name = record.get("name")
        aliases = record.get("aliases")
        if (
            not isinstance(name, str)
            or not name.strip()
            or not isinstance(aliases, list)
            or any(not isinstance(alias, str) or not alias.strip() for alias in aliases)
        ):
            raise ValueError("指标名称词汇格式无效")
        vocabulary.append((name, tuple(aliases)))
    return tuple(vocabulary)


def format_metric_vocabulary(vocabulary: MetricVocabulary) -> str:
    """将词汇格式化为只含规范名和别名的 JSON。"""

    return json.dumps(
        [{"name": name, "aliases": list(aliases)} for name, aliases in vocabulary],
        ensure_ascii=False,
        separators=(",", ":"),
    )
