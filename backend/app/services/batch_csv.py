"""CSV row validation and future batch-scoring provider contracts."""
import csv
import io
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol, Sequence

from fastapi import HTTPException

REQUIRED_COLUMNS = (
    "review_id", "reviewer_id", "product_id", "rating", "review_date", "review_text",
)
MAX_CSV_BYTES = 8 * 1024 * 1024
MAX_CSV_ROWS = 5000
MAX_EXTERNAL_KEY_LENGTH = 255


@dataclass(frozen=True)
class ValidatedReviewRow:
    row_number: int
    uploaded_review_key: str | None
    reviewer_key: str | None
    product_key: str | None
    rating: int | None
    reviewed_at: datetime | None
    review_text: str | None
    errors: tuple[dict[str, str], ...]

    @property
    def accepted(self) -> bool:
        return not self.errors


def _error(field: str, code: str, message: str) -> dict[str, str]:
    return {"field": field, "code": code, "message": message}


def _parse_review_date(value: str) -> datetime | None:
    candidate = value.strip()
    if not candidate:
        return None
    try:
        parsed = datetime.fromisoformat(candidate.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def parse_review_csv(content: bytes) -> list[ValidatedReviewRow]:
    if len(content) > MAX_CSV_BYTES:
        raise HTTPException(status_code=413, detail={"code": "csv_too_large", "message": "CSV uploads may not exceed 8 MiB."})
    try:
        text_content = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(status_code=422, detail={"code": "invalid_csv_encoding", "message": "CSV must be UTF-8 encoded."})

    try:
        reader = csv.DictReader(io.StringIO(text_content, newline=""))
        headers = reader.fieldnames
        if not headers:
            raise HTTPException(status_code=422, detail={"code": "missing_csv_header", "message": "CSV must include the required header row."})
        normalized_headers = [header.strip() if header is not None else "" for header in headers]
        if len(normalized_headers) != len(set(normalized_headers)):
            raise HTTPException(status_code=422, detail={"code": "duplicate_csv_header", "message": "CSV column names must be unique."})
        missing = sorted(set(REQUIRED_COLUMNS) - set(normalized_headers))
        if missing:
            raise HTTPException(status_code=422, detail={"code": "missing_csv_columns", "message": "CSV is missing required columns.", "columns": missing})

        # Normalize harmless surrounding whitespace in header names.
        reader.fieldnames = normalized_headers
        rows: list[ValidatedReviewRow] = []
        seen_review_keys: set[str] = set()
        for line_number, raw in enumerate(reader, start=2):
            if len(rows) >= MAX_CSV_ROWS:
                raise HTTPException(status_code=413, detail={"code": "too_many_csv_rows", "message": f"CSV uploads may not exceed {MAX_CSV_ROWS} data rows."})
            errors: list[dict[str, str]] = []
            if None in raw:
                errors.append(_error("row", "column_count_mismatch", "Row contains more fields than the CSV header."))
            fields = {key: (value or "").strip() for key, value in raw.items() if key is not None}

            def required_key(name: str) -> str | None:
                value = fields.get(name, "")
                if not value:
                    errors.append(_error(name, "required", f"{name} is required."))
                    return None
                if len(value) > MAX_EXTERNAL_KEY_LENGTH:
                    errors.append(_error(name, "too_long", f"{name} must be at most {MAX_EXTERNAL_KEY_LENGTH} characters."))
                    return None
                return value

            review_key = required_key("review_id")
            reviewer_key = required_key("reviewer_id")
            product_key = required_key("product_id")

            if review_key is not None:
                if review_key in seen_review_keys:
                    errors.append(_error("review_id", "duplicate_in_upload", "review_id is repeated in this CSV."))
                else:
                    seen_review_keys.add(review_key)

            rating_value = fields.get("rating", "")
            rating: int | None = None
            if not rating_value:
                errors.append(_error("rating", "required", "rating is required."))
            else:
                try:
                    rating = int(rating_value)
                except ValueError:
                    errors.append(_error("rating", "invalid_integer", "rating must be an integer from 1 to 5."))
                else:
                    if not 1 <= rating <= 5:
                        errors.append(_error("rating", "out_of_range", "rating must be from 1 to 5."))
                        rating = None

            date_value = fields.get("review_date", "")
            reviewed_at = _parse_review_date(date_value)
            if not date_value:
                errors.append(_error("review_date", "required", "review_date is required."))
            elif reviewed_at is None:
                errors.append(_error("review_date", "invalid_datetime", "review_date must be an ISO-8601 date or datetime."))

            review_text = fields.get("review_text", "")
            if not review_text:
                errors.append(_error("review_text", "required", "review_text must not be empty."))

            rows.append(ValidatedReviewRow(
                row_number=line_number,
                uploaded_review_key=review_key,
                reviewer_key=reviewer_key,
                product_key=product_key,
                rating=rating,
                reviewed_at=reviewed_at,
                review_text=review_text or None,
                errors=tuple(errors),
            ))
        return rows
    except csv.Error:
        raise HTTPException(status_code=422, detail={"code": "malformed_csv", "message": "CSV structure is malformed."})


@dataclass(frozen=True)
class BatchReviewInput:
    """Label-free input contract provided to approved scoring components."""

    review_id: int
    reviewer_id: int
    product_id: int
    rating: int
    reviewed_at: datetime
    review_text: str


@dataclass(frozen=True)
class PermittedHistoricContext:
    graph_snapshot_id: int
    split: str
    reviews: Sequence[BatchReviewInput]


@dataclass(frozen=True)
class RelationEdges:
    """Review-index edge pairs for the RUR, RSR, and RTR relations."""

    rur: Sequence[tuple[int, int]]
    rsr: Sequence[tuple[int, int]]
    rtr: Sequence[tuple[int, int]]
    relation_schema_version: str


@dataclass(frozen=True)
class ModelInputBatch:
    review_ids: Sequence[int]
    semantic_embeddings: Sequence[Sequence[float]]
    behavioral_features: Sequence[Sequence[float]]
    relations: RelationEdges
    preprocessing_sha256: str
    historic_snapshot_id: int


@dataclass(frozen=True)
class ScoredReview:
    review_id: int
    risk_score: float
    predicted_label: int
    attention_weights: dict | None = None


class SemanticEmbeddingProvider(Protocol):
    model_revision: str
    preprocessing_sha256: str
    output_dimension: int

    def embed(self, texts: Sequence[str]) -> Sequence[Sequence[float]]:
        """Return the exact semantic vectors required by the pinned model manifest."""


class BehavioralFeatureProvider(Protocol):
    feature_names: Sequence[str]
    preprocessing_sha256: str
    output_dimension: int

    def build(
        self,
        reviews: Sequence[BatchReviewInput],
        *,
        historic_context: PermittedHistoricContext,
    ) -> Sequence[Sequence[float]]:
        """Return manifest-ordered numeric features without using labels or future events."""


class BatchRelationBuilder(Protocol):
    relation_schema_version: str

    def build(
        self,
        uploaded_reviews: Sequence[BatchReviewInput],
        *,
        historic_context: PermittedHistoricContext,
    ) -> RelationEdges:
        """Build batch-to-batch and batch-to-history edges from the permitted snapshot only."""


class BatchScoringRuntime(Protocol):
    """Runtime assembled only from a verified checkpoint and matching immutable manifests."""

    def score(
        self,
        inputs: ModelInputBatch,
        *,
        model_version_id: int,
        threshold: float,
    ) -> Sequence[ScoredReview]:
        """Return persisted-score candidates with their exact provenance; never fabricate attention."""
