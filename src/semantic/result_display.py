"""显示属性属于Semantic；公式与物理结构仍引用既有权威记录。"""

from functools import lru_cache
import json
from pathlib import Path


@lru_cache(maxsize=1)
def load_display_facts() -> tuple[list[dict], dict, list[dict]]:
    root = Path(__file__).resolve().parent
    metrics = json.loads((root / "metrics.json").read_text())
    traits = json.loads((root / "result_display.json").read_text())
    columns = json.loads((root.parent / "structure/generated/columns.json").read_text())
    names = {metric["name"] for metric in metrics}
    dimensions = {
        item["name"] for item in json.loads((root / "dimensions.json").read_text())
    }
    physical = {
        f"{c['schema_name']}.{c['table_name']}.{c['column_name']}" for c in columns
    }
    valid_dimensions = {
        name: value
        for name, value in traits["dimensions"].items()
        if name in dimensions
        and isinstance(value, dict)
        and value.get("column") in physical
    }
    valid_metrics = {}
    for name, value in traits["metrics"].items():
        if name not in names or not isinstance(value, dict):
            continue
        if value.get("format") not in {"money", "count", "ratio", "number"}:
            continue
        unit = value.get("unit")
        if unit is not None and (
            not isinstance(unit, dict)
            or set(unit) != {"key", "label"}
            or not all(isinstance(v, str) and v for v in unit.values())
        ):
            continue
        if value["format"] == "money" and (unit is None or unit["key"] != "CNY"):
            continue
        if value["format"] == "ratio" and (unit is None or unit["key"] != "ratio"):
            continue
        valid_metrics[name] = value
    return metrics, {"metrics": valid_metrics, "dimensions": valid_dimensions}, columns
