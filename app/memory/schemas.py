import json
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import AfterValidator, BaseModel, Field, field_validator

from app.memory.config import (
    DEFAULT_PAGE_SIZE,
    DEFAULT_TOP_K,
    MAX_MEMORY_CONTENT_LENGTH,
    MAX_MEMORY_METADATA_LENGTH,
    MAX_MEMORY_SOURCE_LENGTH,
    MAX_MEMORY_TAG_LENGTH,
    MAX_MEMORY_TAGS,
    MAX_MEMORY_TITLE_LENGTH,
    MAX_PAGE_SIZE,
    MAX_TOP_K,
)
from app.state import NonBlankString


def _validate_content(value: str) -> str:
    if not value.strip():
        raise ValueError("content must not be blank")
    return value


def _validate_metadata(value: dict[str, Any]) -> dict[str, Any]:
    try:
        serialized = json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "metadata must be JSON-serializable",
        ) from exc

    if len(serialized.encode("utf-8")) > MAX_MEMORY_METADATA_LENGTH:
        raise ValueError("metadata exceeds maximum size")

    return value


MemoryContent = Annotated[
    str,
    Field(
        min_length=1,
        max_length=MAX_MEMORY_CONTENT_LENGTH,
    ),
    AfterValidator(_validate_content),
]

MemoryTitle = Annotated[
    NonBlankString,
    Field(max_length=MAX_MEMORY_TITLE_LENGTH),
]

MemorySource = Annotated[
    NonBlankString,
    Field(max_length=MAX_MEMORY_SOURCE_LENGTH),
]

MemoryTag = Annotated[
    NonBlankString,
    Field(max_length=MAX_MEMORY_TAG_LENGTH),
]

MemoryMetadata = Annotated[
    dict[str, Any],
    AfterValidator(_validate_metadata),
]


class MemoryCreate(BaseModel):
    title: MemoryTitle | None = None
    content: MemoryContent
    source: MemorySource = "manual"
    tags: list[MemoryTag] = Field(
        default_factory=list,
        max_length=MAX_MEMORY_TAGS,
    )
    importance: int = Field(default=50, ge=0, le=100)
    metadata: MemoryMetadata = Field(default_factory=dict)


class MemoryUpdate(BaseModel):
    title: MemoryTitle | None = None
    content: MemoryContent | None = None
    source: MemorySource | None = None
    tags: list[MemoryTag] | None = Field(
        default=None,
        max_length=MAX_MEMORY_TAGS,
    )
    importance: int | None = Field(default=None, ge=0, le=100)
    metadata: MemoryMetadata | None = None

    @field_validator("source", mode="before")
    @classmethod
    def _reject_null_source(cls, value: object) -> object:
        if value is None:
            raise ValueError("source must not be null")
        return value


class MemoryResponse(BaseModel):
    id: int
    title: str | None
    content: str
    source: str
    tags: list[str]
    importance: int
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None


class MemoryListQuery(BaseModel):
    limit: int = Field(
        default=DEFAULT_PAGE_SIZE,
        ge=1,
        le=MAX_PAGE_SIZE,
    )
    offset: int = Field(default=0, ge=0)
    include_archived: bool = False
    tags: list[MemoryTag] = Field(
        default_factory=list,
        max_length=MAX_MEMORY_TAGS,
    )
    source: MemorySource | None = None


class MemoryListResponse(BaseModel):
    items: list[MemoryResponse]
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=MAX_PAGE_SIZE)
    offset: int = Field(ge=0)


class MemorySearchRequest(BaseModel):
    query: MemoryContent
    top_k: int = Field(
        default=DEFAULT_TOP_K,
        ge=1,
        le=MAX_TOP_K,
    )
    min_score: float = Field(default=0.0, ge=-1.0, le=1.0)
    tags: list[MemoryTag] = Field(
        default_factory=list,
        max_length=MAX_MEMORY_TAGS,
    )
    source: MemorySource | None = None
    include_archived: bool = False


class MemorySearchResult(BaseModel):
    memory: MemoryResponse
    score: float = Field(ge=-1.0, le=1.0)
    trust: Literal["untrusted"] = "untrusted"


class MemorySearchResponse(BaseModel):
    results: list[MemorySearchResult]
