"""将字段级 Schema 目录加载为 LangChain Document。"""

from __future__ import annotations

import json
from pathlib import Path

from langchain_core.documents import Document


def load_column_documents(path: str | Path) -> list[Document]:
    """读取 columns.json，并为每个字段对象创建一个 Document。"""

    source_path = Path(path)
    data = json.loads(source_path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("columns.json must contain a JSON array")

    documents: list[Document] = []
    for index, item in enumerate(data):
        if not isinstance(item, dict):
            raise ValueError(f"column object at index {index} must be a JSON object")
        table_name = item.get("table_name")
        column_name = item.get("column_name")
        data_type = item.get("data_type")
        description = item.get("description")
        values = (table_name, column_name, data_type, description)
        if not all(isinstance(value, str) for value in values):
            raise ValueError(
                "column object at index "
                f"{index} must contain text table_name, column_name, data_type, and description"
            )

        documents.append(
            Document(
                page_content=(
                    f"表：{table_name}\n"
                    f"字段：{column_name}\n"
                    f"类型：{data_type}\n"
                    f"含义：{description}"
                ),
                metadata={
                    "kind": "column",
                    "table_name": table_name,
                    "column_name": column_name,
                    "data_type": data_type,
                },
            )
        )

    return documents
