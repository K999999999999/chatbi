"""Offline Pipeline resource validation, projection, representation, and asset building."""

import copy
import json
import math
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from langchain_core.documents import Document
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

from src.infrastructure.offline_pipeline import (
    DENSE_DIMENSION,
    DENSE_VECTOR_NAME,
    ResourceReadError,
    SPARSE_VECTOR_NAME,
    build_qdrant_point,
    count_qdrant_points,
    create_candidate_collection,
    create_qdrant_client,
    delete_qdrant_collection,
    encode_bge_m3,
    read_json_file,
    scroll_qdrant_points,
    upsert_qdrant_points,
)


TableIdentity = tuple[str, str]
ColumnIdentity = tuple[str, str, str]
_PROJECT_ROOT = Path(__file__).resolve().parents[2]


class M1ValidationError(ValueError):
    """Raised when the complete M1 input cannot be validated."""


class M3GenerationError(ValueError):
    """Raised when complete retrieval representations cannot be generated."""


class M4BuildError(ValueError):
    """Raised when a complete candidate Retrieval Asset cannot be built."""


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


@dataclass(frozen=True)
class RepresentedRetrievalRecord:
    """One M2 Document and its complete V1 Dense + Sparse representation."""

    document: Document
    dense: tuple[float, ...]
    sparse: dict[int, float]


@dataclass(frozen=True)
class BuiltRetrievalAssets:
    """References and counts for the three validated candidate collections."""

    build_token: str
    table_collection: str
    column_collection: str
    metric_collection: str
    table_count: int
    column_count: int
    metric_count: int

    @property
    def total_count(self) -> int:
        return self.table_count + self.column_count + self.metric_count


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


def generate_retrieval_representations(
    documents: list[Document],
    *,
    model_path: Path,
    device: str = "cpu",
    batch_size: int | None = None,
) -> list[RepresentedRetrievalRecord]:
    """Generate one complete Dense + Sparse bundle for every M2 Document."""

    try:
        _validate_m3_input(documents)
        texts = [document.page_content for document in documents]
        dense_vectors, sparse_vectors = encode_bge_m3(
            texts,
            model_path=model_path,
            device=device,
            batch_size=batch_size,
        )
        _validate_m3_output(documents, dense_vectors, sparse_vectors)
        return [
            RepresentedRetrievalRecord(
                document=document,
                dense=dense,
                sparse=sparse,
            )
            for document, dense, sparse in zip(
                documents,
                dense_vectors,
                sparse_vectors,
                strict=True,
            )
        ]
    except M3GenerationError:
        raise
    except Exception as exc:
        raise M3GenerationError(
            "M3 representation generation failed; no partial output is available"
        ) from exc


POINT_ID_NAMESPACE = uuid.UUID("8df2a9b2-0b1c-5f3d-9a3c-7d5e2e1f4b68")
_COLLECTION_PREFIX_BY_RECORD_TYPE = {
    "TABLE": "table_retrieval",
    "COLUMN": "column_retrieval",
    "METRIC": "metric_retrieval",
}


def point_id_for_document(document: Document) -> str:
    """Derive a stable UUID5 from an explicitly ordered identity list."""

    if not isinstance(document, Document) or not isinstance(document.metadata, dict):
        raise M4BuildError("Point ID input must be a Document with metadata")

    record_type = document.metadata.get("record_type")
    if record_type == "TABLE":
        identity_parts = [
            "TABLE",
            _required_identity_value(document.metadata, "schema_name"),
            _required_identity_value(document.metadata, "table_name"),
        ]
    elif record_type == "COLUMN":
        identity_parts = [
            "COLUMN",
            _required_identity_value(document.metadata, "schema_name"),
            _required_identity_value(document.metadata, "table_name"),
            _required_identity_value(document.metadata, "column_name"),
        ]
    elif record_type == "METRIC":
        identity_parts = [
            "METRIC",
            _required_identity_value(document.metadata, "metric_code"),
        ]
    else:
        raise M4BuildError(f"Unsupported retrieval record_type: {record_type}")

    canonical_name = json.dumps(
        identity_parts,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    )
    return str(uuid.uuid5(POINT_ID_NAMESPACE, canonical_name))


def build_retrieval_assets(
    records: list[RepresentedRetrievalRecord],
    *,
    qdrant_url: str = "http://127.0.0.1:6333",
    timeout: int = 20,
    build_token: str | None = None,
) -> BuiltRetrievalAssets:
    """Build and validate three isolated candidate collections in one execution."""

    created_collections: list[str] = []
    client = None
    try:
        grouped_records = _validate_m4_input(records)
        normalized_build_token = _normalize_build_token(build_token)
        collection_names = {
            record_type: _candidate_collection_name(
                record_type, normalized_build_token
            )
            for record_type in _COLLECTION_PREFIX_BY_RECORD_TYPE
        }
        points_by_type = {
            record_type: [
                build_qdrant_point(
                    point_id,
                    dense=record.dense,
                    sparse=record.sparse,
                    payload=_payload_for_document(record.document),
                )
                for point_id, record in grouped_records[record_type]
            ]
            for record_type in _COLLECTION_PREFIX_BY_RECORD_TYPE
        }

        client = create_qdrant_client(qdrant_url, timeout=timeout)
        for record_type in _COLLECTION_PREFIX_BY_RECORD_TYPE:
            collection_name = collection_names[record_type]
            create_candidate_collection(client, collection_name)
            created_collections.append(collection_name)

        for record_type in _COLLECTION_PREFIX_BY_RECORD_TYPE:
            upsert_qdrant_points(
                client,
                collection_names[record_type],
                points_by_type[record_type],
            )

        for record_type in _COLLECTION_PREFIX_BY_RECORD_TYPE:
            _validate_candidate_collection(
                client,
                collection_names[record_type],
                record_type,
                grouped_records[record_type],
            )

        return BuiltRetrievalAssets(
            build_token=normalized_build_token,
            table_collection=collection_names["TABLE"],
            column_collection=collection_names["COLUMN"],
            metric_collection=collection_names["METRIC"],
            table_count=len(grouped_records["TABLE"]),
            column_count=len(grouped_records["COLUMN"]),
            metric_count=len(grouped_records["METRIC"]),
        )
    except M4BuildError:
        _cleanup_candidate_collections(client, created_collections)
        raise
    except Exception as exc:
        _cleanup_candidate_collections(client, created_collections)
        raise M4BuildError(
            "M4 Retrieval Asset build failed; no partial output is available"
        ) from exc


def _validate_m4_input(
    records: list[RepresentedRetrievalRecord],
) -> dict[str, list[tuple[str, RepresentedRetrievalRecord]]]:
    if not isinstance(records, list) or not records:
        raise M4BuildError("M4 input must be a non-empty list of representations")

    grouped: dict[str, list[tuple[str, RepresentedRetrievalRecord]]] = {
        "TABLE": [],
        "COLUMN": [],
        "METRIC": [],
    }
    point_ids: set[str] = set()
    for record in records:
        if not isinstance(record, RepresentedRetrievalRecord):
            raise M4BuildError("M4 input contains an invalid represented record")
        document = record.document
        if not isinstance(document, Document):
            raise M4BuildError("M4 input contains a non-Document record")
        if not isinstance(document.page_content, str) or not document.page_content.strip():
            raise M4BuildError("M4 input contains empty page_content")
        if not isinstance(document.metadata, dict):
            raise M4BuildError("M4 input Document metadata must be a mapping")
        record_type = document.metadata.get("record_type")
        if record_type not in grouped:
            raise M4BuildError(f"Unsupported retrieval record_type: {record_type}")
        source_path = document.metadata.get("source_path")
        if not isinstance(source_path, str) or not source_path.strip():
            raise M4BuildError("M4 input metadata.source_path is required")
        if type(record.dense) is not tuple or len(record.dense) != DENSE_DIMENSION:
            raise M4BuildError("M4 Dense representation must be a 1024-value tuple")
        if any(type(value) is not float or not math.isfinite(value) for value in record.dense):
            raise M4BuildError("M4 Dense values must be finite Python floats")
        if type(record.sparse) is not dict or not record.sparse:
            raise M4BuildError("M4 Sparse representation must be a non-empty dict")
        if any(
            type(index) is not int or index < 0
            for index in record.sparse
        ):
            raise M4BuildError("M4 Sparse indexes must be non-negative Python integers")
        if any(
            type(weight) is not float or not math.isfinite(weight)
            for weight in record.sparse.values()
        ):
            raise M4BuildError("M4 Sparse values must be finite Python floats")

        point_id = point_id_for_document(document)
        if point_id in point_ids:
            raise M4BuildError(f"Duplicate Point ID: {point_id}")
        point_ids.add(point_id)
        grouped[record_type].append((point_id, record))

    return grouped


def _validate_candidate_collection(
    client: object,
    collection_name: str,
    record_type: str,
    expected_records: list[tuple[str, RepresentedRetrievalRecord]],
) -> None:
    if not client.collection_exists(collection_name):
        raise M4BuildError(f"Candidate collection does not exist: {collection_name}")

    expected_by_id = {point_id: record for point_id, record in expected_records}
    expected_count = len(expected_records)
    stored_count = count_qdrant_points(client, collection_name)
    if stored_count != expected_count:
        raise M4BuildError(
            f"Stored Point count mismatch for {collection_name}: "
            f"expected {expected_count}, got {stored_count}"
        )

    stored_points = scroll_qdrant_points(client, collection_name)
    if len(stored_points) != expected_count:
        raise M4BuildError(
            f"Scrolled Point count mismatch for {collection_name}: "
            f"expected {expected_count}, got {len(stored_points)}"
        )

    seen_ids: set[str] = set()
    for point in stored_points:
        point_id = str(point.id)
        if point_id in seen_ids:
            raise M4BuildError(f"Duplicate stored Point ID: {point_id}")
        seen_ids.add(point_id)
        if point_id not in expected_by_id:
            raise M4BuildError(f"Unexpected stored Point ID: {point_id}")

        vectors = getattr(point, "vector", None)
        if not isinstance(vectors, dict) or set(vectors) != {
            DENSE_VECTOR_NAME,
            SPARSE_VECTOR_NAME,
        }:
            raise M4BuildError(f"Invalid named vectors for Point: {point_id}")
        dense = vectors.get(DENSE_VECTOR_NAME)
        if not isinstance(dense, (list, tuple)) or len(dense) != DENSE_DIMENSION:
            raise M4BuildError(f"Invalid Dense vector for Point: {point_id}")
        if any(
            not isinstance(value, (int, float))
            or isinstance(value, bool)
            or not math.isfinite(float(value))
            for value in dense
        ):
            raise M4BuildError(f"Dense vector contains invalid values: {point_id}")

        sparse = vectors.get(SPARSE_VECTOR_NAME)
        indices = getattr(sparse, "indices", None)
        values = getattr(sparse, "values", None)
        if not isinstance(indices, list) or not isinstance(values, list):
            raise M4BuildError(f"Invalid Sparse vector for Point: {point_id}")
        if not indices or len(indices) != len(values):
            raise M4BuildError(f"Sparse indexes and values are invalid: {point_id}")
        if any(type(index) is not int or index < 0 for index in indices):
            raise M4BuildError(f"Sparse indexes are invalid: {point_id}")
        if len(set(indices)) != len(indices):
            raise M4BuildError(f"Sparse indexes are duplicated: {point_id}")
        if any(
            not isinstance(value, (int, float))
            or isinstance(value, bool)
            or not math.isfinite(float(value))
            for value in values
        ):
            raise M4BuildError(f"Sparse values are invalid: {point_id}")

        payload = getattr(point, "payload", None)
        if not isinstance(payload, dict):
            raise M4BuildError(f"Payload is missing: {point_id}")
        page_content = payload.get("page_content")
        metadata = payload.get("metadata")
        if not isinstance(page_content, str) or not page_content.strip():
            raise M4BuildError(f"Payload page_content is missing: {point_id}")
        if not isinstance(metadata, dict):
            raise M4BuildError(f"Payload metadata is missing: {point_id}")
        if metadata.get("record_type") != record_type:
            raise M4BuildError(f"Payload record_type is incorrectly routed: {point_id}")
        source_path = metadata.get("source_path")
        if not isinstance(source_path, str) or not source_path.strip():
            raise M4BuildError(f"Payload source_path is missing: {point_id}")
        if DENSE_VECTOR_NAME in payload or SPARSE_VECTOR_NAME in payload:
            raise M4BuildError(f"Payload must not duplicate vectors: {point_id}")

    if seen_ids != set(expected_by_id):
        raise M4BuildError(f"Stored Point identities mismatch: {collection_name}")


def _payload_for_document(document: Document) -> dict[str, object]:
    return {
        "page_content": document.page_content,
        "metadata": copy.deepcopy(document.metadata),
    }


def _candidate_collection_name(record_type: str, build_token: str) -> str:
    return f"{_COLLECTION_PREFIX_BY_RECORD_TYPE[record_type]}__candidate_{build_token}"


def _normalize_build_token(build_token: str | None) -> str:
    token = uuid.uuid4().hex if build_token is None else build_token
    if not isinstance(token, str) or not token:
        raise M4BuildError("M4 build_token must be a non-empty string")
    if any(character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for character in token):
        raise M4BuildError("M4 build_token contains unsupported characters")
    return token


def _cleanup_candidate_collections(client: object, collection_names: list[str]) -> None:
    if client is None:
        return
    for collection_name in collection_names:
        try:
            delete_qdrant_collection(client, collection_name)
        except Exception:
            # Preserve the original build failure and never report a partial success.
            continue


def _required_identity_value(metadata: dict, field_name: str) -> str:
    value = metadata.get(field_name)
    if not isinstance(value, str) or not value:
        raise M4BuildError(f"Point identity field is missing: {field_name}")
    return value


def _validate_m3_input(documents: list[Document]) -> None:
    if not isinstance(documents, list) or not documents:
        raise M3GenerationError("M3 input must be a non-empty list of Documents")

    allowed_record_types = {"TABLE", "COLUMN", "METRIC"}
    for document in documents:
        if not isinstance(document, Document):
            raise M3GenerationError("M3 input contains a non-Document record")
        if not isinstance(document.page_content, str) or not document.page_content.strip():
            raise M3GenerationError("M3 input contains empty page_content")
        if document.metadata.get("record_type") not in allowed_record_types:
            raise M3GenerationError("M3 input contains an unsupported record_type")


def _validate_m3_output(
    documents: list[Document],
    dense_vectors: object,
    sparse_vectors: object,
) -> None:
    if not isinstance(dense_vectors, list) or not isinstance(sparse_vectors, list):
        raise M3GenerationError("M3 output must contain Dense and Sparse lists")
    if len(dense_vectors) != len(documents):
        raise M3GenerationError("Dense output count does not match input count")
    if len(sparse_vectors) != len(documents):
        raise M3GenerationError("Sparse output count does not match input count")

    dense_dimension: int | None = None
    for dense in dense_vectors:
        if not isinstance(dense, tuple) or not dense:
            raise M3GenerationError("M3 output contains a missing Dense vector")
        if not all(type(value) is float for value in dense):
            raise M3GenerationError("M3 Dense values must be Python floats")
        if dense_dimension is None:
            dense_dimension = len(dense)
        elif len(dense) != dense_dimension:
            raise M3GenerationError("M3 Dense dimensions are inconsistent")

    for sparse in sparse_vectors:
        if not isinstance(sparse, dict) or not sparse:
            raise M3GenerationError("M3 output contains missing Sparse weights")
        if not all(type(index) is int for index in sparse):
            raise M3GenerationError("M3 Sparse indexes must be Python integers")
        if not all(type(weight) is float for weight in sparse.values()):
            raise M3GenerationError("M3 Sparse weights must be Python floats")


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
