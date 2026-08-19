"""M1 resource parsing and deterministic cross-resource validation."""

from pathlib import Path
from typing import Literal

from langchain_core.documents import Document
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

from src.infrastructure.offline_pipeline import ResourceReadError, read_json_file


TableIdentity = tuple[str, str]
ColumnIdentity = tuple[str, str, str]
_PROJECT_ROOT = Path(__file__).resolve().parents[2]


class M1ValidationError(ValueError):
    """Raised when the complete M1 input cannot be validated."""


class _ResourceModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class TableResource(_ResourceModel):
    schema_name: str = Field(min_length=1)
    table_name: str = Field(min_length=1)
    table_type: str = Field(min_length=1)
    description: str | None = None


class ColumnResource(_ResourceModel):
    schema_name: str = Field(min_length=1)
    table_name: str = Field(min_length=1)
    column_name: str = Field(min_length=1)
    ordinal_position: int = Field(ge=1)
    data_type: str = Field(min_length=1)
    nullable: bool
    default: str | None = None
    description: str | None = None
    is_primary_key: bool
    is_foreign_key: bool
    is_identity: bool
    identity_generation: Literal["ALWAYS", "BY DEFAULT"] | None = None


class MetricResource(_ResourceModel):
    metric_code: str = Field(min_length=1)
    metric_name: str = Field(min_length=1)
    metric_type: Literal["atomic", "derived"]
    aliases: list[str]
    business_definition: str = Field(min_length=1)
    expression: str = Field(min_length=1)
    filters: list[str]
    depends_on: list[str]
    default_time_column_identity: str = Field(min_length=1)
    unit: str = Field(min_length=1)
    source_table: str | None = None
    source_columns: list[str] | None = None
    null_if: str | None = None


class ColumnConstraintResource(_ResourceModel):
    schema_name: str = Field(min_length=1)
    table_name: str = Field(min_length=1)
    column_names: list[str] = Field(min_length=1)


class ForeignKeyResource(_ResourceModel):
    schema_name: str = Field(min_length=1)
    table_name: str = Field(min_length=1)
    column_names: list[str] = Field(min_length=1)
    referenced_schema: str = Field(min_length=1)
    referenced_table: str = Field(min_length=1)
    referenced_column_names: list[str] = Field(min_length=1)


class UniqueIndexResource(_ResourceModel):
    schema_name: str = Field(min_length=1)
    table_name: str = Field(min_length=1)
    index_name: str = Field(min_length=1)
    column_names: list[str] = Field(min_length=1)
    predicate: str | None = None


class RelationshipCatalogResource(_ResourceModel):
    schema_version: int = Field(ge=1)
    primary_keys: list[ColumnConstraintResource]
    unique_constraints: list[ColumnConstraintResource]
    foreign_keys: list[ForeignKeyResource]
    unique_indexes: list[UniqueIndexResource]


class ValidatedCatalogs(BaseModel):
    """The complete M1 output; constructed only after every validation passes."""

    model_config = ConfigDict(extra="forbid")

    tables: tuple[TableResource, ...]
    columns: tuple[ColumnResource, ...]
    relationships: RelationshipCatalogResource
    metrics: tuple[MetricResource, ...]
    tables_path: Path
    columns_path: Path
    relationships_path: Path
    metrics_path: Path


def load_validated_catalogs(
    *,
    tables_path: Path,
    columns_path: Path,
    relationships_path: Path,
    metrics_path: Path,
) -> ValidatedCatalogs:
    """Load exactly four resources and return them only if all checks pass."""

    try:
        tables_raw = read_json_file(tables_path)
        columns_raw = read_json_file(columns_path)
        relationships_raw = read_json_file(relationships_path)
        metrics_raw = read_json_file(metrics_path)
    except ResourceReadError as exc:
        raise M1ValidationError(str(exc)) from exc

    tables = _parse_list(tables_raw, TableResource, "tables.json")
    columns = _parse_list(columns_raw, ColumnResource, "columns.json")
    relationships = _parse_relationships(relationships_raw)
    metrics = _parse_list(metrics_raw, MetricResource, "metrics.json")

    _validate_catalogs(tables, columns, relationships, metrics)

    return ValidatedCatalogs(
        tables=tuple(tables),
        columns=tuple(columns),
        relationships=relationships,
        metrics=tuple(metrics),
        tables_path=tables_path,
        columns_path=columns_path,
        relationships_path=relationships_path,
        metrics_path=metrics_path,
    )


def project_tables(catalogs: ValidatedCatalogs) -> list[Document]:
    source_path = _stable_source_path(catalogs.tables_path)
    documents: list[Document] = []
    for table in catalogs.tables:
        content = [f"table_name: {table.table_name}"]
        if table.description:
            content.append(f"description: {table.description}")
        documents.append(
            Document(
                page_content="\n".join(content),
                metadata={
                    "record_type": "TABLE",
                    "schema_name": table.schema_name,
                    "table_name": table.table_name,
                    "source_path": source_path,
                },
            )
        )
    return documents


def project_columns(catalogs: ValidatedCatalogs) -> list[Document]:
    source_path = _stable_source_path(catalogs.columns_path)
    documents: list[Document] = []
    for column in catalogs.columns:
        content = [f"column_name: {column.column_name}"]
        if column.description:
            content.append(f"description: {column.description}")
        documents.append(
            Document(
                page_content="\n".join(content),
                metadata={
                    "record_type": "COLUMN",
                    "schema_name": column.schema_name,
                    "table_name": column.table_name,
                    "column_name": column.column_name,
                    "source_path": source_path,
                },
            )
        )
    return documents


def project_metrics(catalogs: ValidatedCatalogs) -> list[Document]:
    source_path = _stable_source_path(catalogs.metrics_path)
    documents: list[Document] = []
    for metric in catalogs.metrics:
        content = [
            f"metric_code: {metric.metric_code}",
            f"metric_name: {metric.metric_name}",
        ]
        if metric.aliases:
            content.append(f"aliases: {'; '.join(metric.aliases)}")
        content.extend(
            [
                f"business_definition: {metric.business_definition}",
                f"expression: {metric.expression}",
            ]
        )
        documents.append(
            Document(
                page_content="\n".join(content),
                metadata={
                    "record_type": "METRIC",
                    "metric_code": metric.metric_code,
                    "source_path": source_path,
                    "metric_type": metric.metric_type,
                    "filters": list(metric.filters),
                    "depends_on": list(metric.depends_on),
                    "default_time_column_identity": metric.default_time_column_identity,
                    "unit": metric.unit,
                    "source_table": metric.source_table,
                    "source_columns": (
                        list(metric.source_columns)
                        if metric.source_columns is not None
                        else None
                    ),
                    "null_if": metric.null_if,
                },
            )
        )
    return documents


def project_retrieval_records(catalogs: ValidatedCatalogs) -> list[Document]:
    """Project each supported source object into exactly one Document."""

    return [
        *project_tables(catalogs),
        *project_columns(catalogs),
        *project_metrics(catalogs),
    ]


def _stable_source_path(path: Path) -> str:
    resolved_path = path.resolve()
    try:
        relative_path = resolved_path.relative_to(_PROJECT_ROOT)
    except ValueError as exc:
        raise ValueError(f"Source path is outside the project: {path}") from exc
    return relative_path.as_posix()


def _parse_list(raw: object, model_type: type[BaseModel], resource_name: str) -> list:
    if not isinstance(raw, list):
        raise M1ValidationError(f"{resource_name} must contain a JSON array")

    try:
        return TypeAdapter(list[model_type]).validate_python(raw)
    except ValidationError as exc:
        raise M1ValidationError(f"{resource_name} schema validation failed: {exc}") from exc


def _parse_relationships(raw: object) -> RelationshipCatalogResource:
    if not isinstance(raw, dict):
        raise M1ValidationError("relationships.json must contain a JSON object")

    try:
        return RelationshipCatalogResource.model_validate(raw)
    except ValidationError as exc:
        raise M1ValidationError(
            f"relationships.json schema validation failed: {exc}"
        ) from exc


def _validate_catalogs(
    tables: list[TableResource],
    columns: list[ColumnResource],
    relationships: RelationshipCatalogResource,
    metrics: list[MetricResource],
) -> None:
    if not tables:
        raise M1ValidationError("tables.json must not be empty")
    if not columns:
        raise M1ValidationError("columns.json must not be empty")
    if not metrics:
        raise M1ValidationError("metrics.json must not be empty")
    if relationships.schema_version != 1:
        raise M1ValidationError(
            f"Unsupported relationships schema_version: {relationships.schema_version}"
        )

    table_ids = [(table.schema_name, table.table_name) for table in tables]
    column_ids = [
        (column.schema_name, column.table_name, column.column_name)
        for column in columns
    ]
    metric_codes = [metric.metric_code for metric in metrics]
    _ensure_unique(table_ids, "table identity")
    _ensure_unique(column_ids, "column identity")
    _ensure_unique(metric_codes, "metric identity")

    table_index = {identity: table for identity, table in zip(table_ids, tables)}
    column_index = {identity: column for identity, column in zip(column_ids, columns)}
    metric_index = {metric.metric_code: metric for metric in metrics}

    if {identity[:2] for identity in column_ids} != set(table_index):
        raise M1ValidationError(
            "columns.json table references must cover exactly the table catalog"
        )

    _validate_metrics(metrics, metric_index, table_index, column_index)
    _validate_relationships(relationships, table_index, column_index, columns)


def _validate_metrics(
    metrics: list[MetricResource],
    metric_index: dict[str, MetricResource],
    table_index: dict[TableIdentity, TableResource],
    column_index: dict[ColumnIdentity, ColumnResource],
) -> None:
    for metric in metrics:
        default_time_identity = _parse_column_identity(
            metric.default_time_column_identity,
            f"metric {metric.metric_code} default_time_column_identity",
        )
        if default_time_identity not in column_index:
            raise M1ValidationError(
                f"Metric {metric.metric_code} default time column does not exist: "
                f"{metric.default_time_column_identity}"
            )

        has_source_table = metric.source_table is not None
        has_source_columns = metric.source_columns is not None
        if has_source_table != has_source_columns:
            raise M1ValidationError(
                f"Metric {metric.metric_code} physical mapping must provide both "
                "source_table and source_columns"
            )
        if metric.metric_type == "atomic" and not has_source_table:
            raise M1ValidationError(
                f"Atomic metric {metric.metric_code} must provide physical mapping"
            )
        if has_source_table:
            source_table = metric.source_table
            source_columns = metric.source_columns
            if source_table is None or source_columns is None:
                raise M1ValidationError(
                    f"Metric {metric.metric_code} physical mapping is incomplete"
                )
            if not source_columns:
                raise M1ValidationError(
                    f"Metric {metric.metric_code} source_columns must not be empty"
                )
            _ensure_unique(
                source_columns,
                f"metric {metric.metric_code} source column reference",
            )
            source_table_identity = _resolve_table_name(
                source_table, table_index, metric.metric_code
            )
            for source_column in source_columns:
                column_identity = (*source_table_identity, source_column)
                if column_identity not in column_index:
                    raise M1ValidationError(
                        f"Metric {metric.metric_code} physical column does not exist: "
                        f"{source_table_identity[0]}.{source_table_identity[1]}."
                        f"{source_column}"
                    )

        _ensure_unique(
            metric.depends_on, f"metric {metric.metric_code} dependency reference"
        )
        for dependency in metric.depends_on:
            if dependency not in metric_index:
                raise M1ValidationError(
                    f"Metric {metric.metric_code} dependency does not exist: {dependency}"
                )

    visit_state: dict[str, int] = {}

    def visit(metric_code: str) -> None:
        state = visit_state.get(metric_code, 0)
        if state == 1:
            raise M1ValidationError(f"Metric dependency cycle detected at: {metric_code}")
        if state == 2:
            return
        visit_state[metric_code] = 1
        for dependency in metric_index[metric_code].depends_on:
            visit(dependency)
        visit_state[metric_code] = 2

    for metric in metrics:
        visit(metric.metric_code)


def _validate_relationships(
    relationships: RelationshipCatalogResource,
    table_index: dict[TableIdentity, TableResource],
    column_index: dict[ColumnIdentity, ColumnResource],
    columns: list[ColumnResource],
) -> None:
    primary_key_columns = _validate_constraints(
        relationships.primary_keys, "primary key", table_index, column_index
    )
    _validate_constraints(
        relationships.unique_constraints,
        "unique constraint",
        table_index,
        column_index,
    )
    foreign_key_columns = _validate_foreign_keys(
        relationships.foreign_keys, table_index, column_index
    )
    _validate_unique_indexes(relationships.unique_indexes, table_index, column_index)

    for column in columns:
        identity = (column.schema_name, column.table_name, column.column_name)
        if column.is_primary_key != (identity in primary_key_columns):
            raise M1ValidationError(
                f"Column primary-key flag disagrees with relationships.json: {identity}"
            )
        if column.is_foreign_key != (identity in foreign_key_columns):
            raise M1ValidationError(
                f"Column foreign-key flag disagrees with relationships.json: {identity}"
            )


def _validate_constraints(
    constraints: list[ColumnConstraintResource],
    label: str,
    table_index: dict[TableIdentity, TableResource],
    column_index: dict[ColumnIdentity, ColumnResource],
) -> set[ColumnIdentity]:
    constraint_ids: set[tuple[TableIdentity, tuple[str, ...]]] = set()
    referenced_columns: set[ColumnIdentity] = set()
    for constraint in constraints:
        table_identity = (constraint.schema_name, constraint.table_name)
        if table_identity not in table_index:
            raise M1ValidationError(f"{label} table does not exist: {table_identity}")
        _ensure_unique(constraint.column_names, f"{label} column reference")
        constraint_id = (table_identity, tuple(constraint.column_names))
        if constraint_id in constraint_ids:
            raise M1ValidationError(f"Duplicate {label}: {constraint_id}")
        constraint_ids.add(constraint_id)
        for column_name in constraint.column_names:
            column_identity = (*table_identity, column_name)
            if column_identity not in column_index:
                raise M1ValidationError(
                    f"{label} column does not exist: {column_identity}"
                )
            referenced_columns.add(column_identity)
    return referenced_columns


def _validate_foreign_keys(
    foreign_keys: list[ForeignKeyResource],
    table_index: dict[TableIdentity, TableResource],
    column_index: dict[ColumnIdentity, ColumnResource],
) -> set[ColumnIdentity]:
    foreign_key_ids: set[
        tuple[TableIdentity, tuple[str, ...], TableIdentity, tuple[str, ...]]
    ] = set()
    referenced_source_columns: set[ColumnIdentity] = set()
    for foreign_key in foreign_keys:
        source_table = (foreign_key.schema_name, foreign_key.table_name)
        target_table = (foreign_key.referenced_schema, foreign_key.referenced_table)
        if source_table not in table_index:
            raise M1ValidationError(f"foreign key source table does not exist: {source_table}")
        if target_table not in table_index:
            raise M1ValidationError(f"foreign key target table does not exist: {target_table}")
        if len(foreign_key.column_names) != len(foreign_key.referenced_column_names):
            raise M1ValidationError(
                f"foreign key column counts do not match: {source_table} -> {target_table}"
            )
        _ensure_unique(foreign_key.column_names, "foreign key source column reference")
        _ensure_unique(
            foreign_key.referenced_column_names,
            "foreign key target column reference",
        )
        foreign_key_id = (
            source_table,
            tuple(foreign_key.column_names),
            target_table,
            tuple(foreign_key.referenced_column_names),
        )
        if foreign_key_id in foreign_key_ids:
            raise M1ValidationError(f"Duplicate foreign key: {foreign_key_id}")
        foreign_key_ids.add(foreign_key_id)

        for source_column, target_column in zip(
            foreign_key.column_names, foreign_key.referenced_column_names
        ):
            source_identity = (*source_table, source_column)
            target_identity = (*target_table, target_column)
            if source_identity not in column_index:
                raise M1ValidationError(
                    f"foreign key source column does not exist: {source_identity}"
                )
            if target_identity not in column_index:
                raise M1ValidationError(
                    f"foreign key target column does not exist: {target_identity}"
                )
            referenced_source_columns.add(source_identity)
    return referenced_source_columns


def _validate_unique_indexes(
    indexes: list[UniqueIndexResource],
    table_index: dict[TableIdentity, TableResource],
    column_index: dict[ColumnIdentity, ColumnResource],
) -> None:
    index_ids: set[tuple[TableIdentity, str]] = set()
    for index in indexes:
        table_identity = (index.schema_name, index.table_name)
        if table_identity not in table_index:
            raise M1ValidationError(
                f"unique index table does not exist: {table_identity}"
            )
        _ensure_unique(index.column_names, "unique index column reference")
        index_id = (table_identity, index.index_name)
        if index_id in index_ids:
            raise M1ValidationError(f"Duplicate unique index: {index_id}")
        index_ids.add(index_id)
        for column_name in index.column_names:
            column_identity = (*table_identity, column_name)
            if column_identity not in column_index:
                raise M1ValidationError(
                    f"unique index column does not exist: {column_identity}"
                )
        if index.predicate is not None and not index.predicate.strip():
            raise M1ValidationError(f"unique index predicate must not be empty: {index_id}")


def _resolve_table_name(
    table_name: str,
    table_index: dict[TableIdentity, TableResource],
    metric_code: str,
) -> TableIdentity:
    candidates = [identity for identity in table_index if identity[1] == table_name]
    if not candidates:
        raise M1ValidationError(
            f"Metric {metric_code} physical table does not exist: {table_name}"
        )
    if len(candidates) > 1:
        raise M1ValidationError(
            f"Metric {metric_code} physical table is ambiguous: {table_name}"
        )
    return candidates[0]


def _parse_column_identity(value: str, label: str) -> ColumnIdentity:
    parts = value.split(".")
    if len(parts) != 3 or any(not part for part in parts):
        raise M1ValidationError(f"{label} must be schema.table.column: {value}")
    return parts[0], parts[1], parts[2]


def _ensure_unique(values: list, label: str) -> None:
    seen = set()
    for value in values:
        if value in seen:
            raise M1ValidationError(f"Duplicate {label}: {value}")
        seen.add(value)
