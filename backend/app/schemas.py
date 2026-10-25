from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator
from typing import Annotated

Password = Annotated[str, StringConstraints(min_length=12, max_length=256)]


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=256)

    @field_validator("email")
    @classmethod
    def valid_email(cls, value: str) -> str:
        if value.count("@") != 1 or "." not in value.rsplit("@", 1)[-1]:
            raise ValueError("A valid email address is required")
        return value.strip()


class UserCreate(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    username: str | None = Field(default=None, min_length=2, max_length=80)
    password: Password
    role_key: str = "RESEARCHER"

    @field_validator("email")
    @classmethod
    def valid_email(cls, value: str) -> str:
        if value.count("@") != 1 or "." not in value.rsplit("@", 1)[-1]:
            raise ValueError("A valid email address is required")
        return value.strip()


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    user_id: int
    email: str
    username: str | None
    role_key: str
    is_active: bool


class ReviewCreate(BaseModel):
    source_system: str | None = Field(default=None, max_length=100)
    source_review_key: str | None = Field(default=None, max_length=255)
    reviewer_id: int | None = None
    product_id: int | None = None
    rating: int | None = Field(default=None, ge=1, le=5)
    review_text: str | None = None
    reviewed_at: datetime | None = None


class InferenceRequest(BaseModel):
    model_version_id: int = Field(gt=0)
    graph_snapshot_id: int = Field(gt=0)
    review_ids: list[int] = Field(min_length=1, max_length=500)


class VerifiedBaselinePredictionRequest(BaseModel):
    review_ids: list[str] = Field(min_length=1, max_length=100)


class VerifiedMultimodalPredictionRequest(BaseModel):
    review_ids: list[str] = Field(min_length=1, max_length=100)


class GraphSyncCreate(BaseModel):
    operation: str = Field(pattern="^(review_upsert|review_delete|snapshot_rebuild)$")
    review_id: int | None = Field(default=None, gt=0)
    graph_snapshot_id: int | None = Field(default=None, gt=0)


class BatchContextPermissionRequest(BaseModel):
    permitted: bool
    context_scope_key: str | None = Field(default=None, max_length=160)
