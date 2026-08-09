"""Schema 离线索引构建所需的基础加载器入口。"""

from .column_loader import load_column_documents
from .table_loader import load_table_documents

__all__ = ["load_column_documents", "load_table_documents"]
