"""将表级 Schema 目录加载为 LangChain Document。"""

from __future__ import annotations

import json
from pathlib import Path

from langchain_core.documents import Document


def load_table_documents(path: str | Path) -> list[Document]:
    """读取 tables.json，并为每个表对象创建一个 Document。"""

    source_path = Path(path)
    data = json.loads(source_path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("tables.json must contain a JSON array")

    documents: list[Document] = []
    for index, item in enumerate(data):
        if not isinstance(item, dict):
            raise ValueError(f"table object at index {index} must be a JSON object")
        table_name = item.get("table_name")
        description = item.get("description")
        if not isinstance(table_name, str) or not isinstance(description, str):
            raise ValueError(
                f"table object at index {index} must contain text table_name and description"
            )

        documents.append(
            Document(
                page_content=f"表：{table_name}\n业务含义：{description}",
                metadata={"kind": "table", "table_name": table_name},
            )
        )

    return documents
