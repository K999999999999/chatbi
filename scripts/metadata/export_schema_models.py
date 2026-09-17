"""Metadata Export 的模型、常量和稳定输出名称。"""

from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TARGET_SCHEMA = "mart_sales"
EXPECTED_TABLES = frozenset(
    {
        "dim_date",
        "dim_customer",
        "dim_product",
        "dim_sales_region",
        "dim_currency",
        "fct_exchange_rate_daily",
        "fct_sales_order_line",
    }
)
OUTPUT_FILES = {
    "tables": "tables.json",
    "columns": "columns.json",
    "relationships": "relationships.json",
}
DEFAULT_OUTPUT_DIR = ROOT / "src" / "structure" / "generated"


class MetadataExportError(RuntimeError):
    """Schema Metadata（结构元数据）无法满足当前导出契约。"""


ColumnIdentity = tuple[str, str, str]


@dataclass(frozen=True)
class TableMetadata:
    schema_name: str
    table_name: str
    table_type: str
    description: str | None


@dataclass(frozen=True)
class ColumnMetadata:
    schema_name: str
    table_name: str
    column_name: str
    ordinal_position: int
    data_type: str
    nullable: bool
    default: str | None
    description: str | None
    is_primary_key: bool = False
    is_foreign_key: bool = False
    is_identity: bool = False
    identity_generation: str | None = None


@dataclass(frozen=True)
class ConstraintMetadata:
    schema_name: str
    table_name: str
    column_names: tuple[str, ...]
    constraint_name: str


@dataclass(frozen=True)
class ForeignKeyMetadata:
    schema_name: str
    table_name: str
    column_names: tuple[str, ...]
    referenced_schema: str
    referenced_table: str
    referenced_column_names: tuple[str, ...]
    constraint_name: str


@dataclass(frozen=True)
class UniqueIndexMetadata:
    schema_name: str
    table_name: str
    index_name: str
    column_names: tuple[str, ...]
    predicate: str | None


@dataclass(frozen=True)
class CanonicalSchema:
    """一次 PostgreSQL 扫描形成的统一结构模型。"""

    schema_name: str
    tables: tuple[TableMetadata, ...]
    columns: tuple[ColumnMetadata, ...]
    primary_keys: tuple[ConstraintMetadata, ...]
    unique_constraints: tuple[ConstraintMetadata, ...]
    foreign_keys: tuple[ForeignKeyMetadata, ...]
    unique_indexes: tuple[UniqueIndexMetadata, ...]
