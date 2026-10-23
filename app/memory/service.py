import json
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any, Protocol

from pydantic import ValidationError
from sqlalchemy import and_, func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from app.memory.config import DEFAULT_CONFIG
from app.memory.embeddings import (
    EmbeddingError,
    EmbeddingResult,
    EmbeddingServiceUnavailableError,
    InvalidEmbeddingResponseError,
)
from app.memory.schemas import (
    MemoryCreate,
    MemoryResponse,
    MemoryUpdate,
)
from app.memory.vectors import (
    VectorError,
    cosine_similarity,
    decode_vector,
    encode_vector,
    vector_norm,
)
from app.models import Memory, MemoryEmbedding


class MemoryError(Exception):
    pass


class MemoryNotFoundError(MemoryError):
    pass


class MemoryDuplicateError(MemoryError):
    pass


class MemoryValidationError(MemoryError):
    pass


class MemoryEmbeddingUnavailableError(MemoryError):
    pass


class MemoryInvalidEmbeddingResponseError(MemoryError):
    pass


class EmbeddingClient(Protocol):
    def embed(self, text: str) -> EmbeddingResult: ...


DEFAULT_OWNER_ID = "local"
DEFAULT_EMBEDDING_MODEL = DEFAULT_CONFIG.embedding_model


@dataclass(frozen=True, slots=True)
class MemorySearchHit:
    memory: MemoryResponse
    score: float
    trust: str = "untrusted"


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _normalize_for_hash(content: str) -> str:
    normalized = unicodedata.normalize("NFKC", content)
    normalized = " ".join(normalized.split())
    return normalized.casefold().strip()


def compute_content_hash(content: str) -> str:
    normalized = _normalize_for_hash(content)
    return sha256(normalized.encode("utf-8")).hexdigest()


def _validate_memory_create(data: MemoryCreate) -> MemoryCreate:
    return data


def _validate_memory_update(data: MemoryUpdate) -> MemoryUpdate:
    return data


def _serialize_tags(tags: list[str]) -> str:
    return json.dumps(tags, ensure_ascii=False, separators=(",", ":"))


def _deserialize_tags(tags_json: str) -> list[str]:
    try:
        parsed = json.loads(tags_json)
    except (TypeError, ValueError):
        return []
    if not isinstance(parsed, list):
        return []
    return [item for item in parsed if isinstance(item, str)]


def _serialize_metadata(metadata: dict[str, Any]) -> str:
    return json.dumps(metadata, ensure_ascii=False, separators=(",", ":"))


def _deserialize_metadata(metadata_json: str) -> dict[str, Any]:
    try:
        parsed = json.loads(metadata_json)
    except (TypeError, ValueError):
        return {}
    if not isinstance(parsed, dict):
        return {}
    return parsed


def _exact_tag_condition(tag: str) -> ColumnElement[bool]:
    tag_values = func.json_each(Memory.tags_json).table_valued("value")
    return (
        select(1)
        .select_from(tag_values)
        .where(tag_values.c.value == tag)
        .exists()
    )


def _memory_to_response(memory: Memory) -> MemoryResponse:
    return MemoryResponse(
        id=memory.id,
        title=memory.title,
        content=memory.content,
        source=memory.source,
        tags=_deserialize_tags(memory.tags_json),
        importance=memory.importance,
        metadata=_deserialize_metadata(memory.metadata_json),
        created_at=memory.created_at,
        updated_at=memory.updated_at,
        archived_at=memory.archived_at,
    )


def _map_embedding_error(exc: EmbeddingError) -> MemoryError:
    if isinstance(exc, EmbeddingServiceUnavailableError):
        return MemoryEmbeddingUnavailableError(
            "embedding service unavailable",
        )
    if isinstance(exc, InvalidEmbeddingResponseError):
        return MemoryInvalidEmbeddingResponseError(
            "invalid embedding response",
        )
    return MemoryEmbeddingUnavailableError("embedding service unavailable")


def _get_memory_or_raise(
    db: Session,
    memory_id: int,
    owner_id: str,
    *,
    include_archived: bool = True,
) -> Memory:
    stmt = select(Memory).where(
        Memory.id == memory_id,
        Memory.owner_id == owner_id,
    )
    memory = db.execute(stmt).scalars().first()
    if memory is None:
        raise MemoryNotFoundError("Memory not found")
    if not include_archived and memory.archived_at is not None:
        raise MemoryNotFoundError("Memory not found")
    return memory


def create_memory(
    db: Session,
    data: MemoryCreate,
    embedding_client: EmbeddingClient,
    *,
    owner_id: str = DEFAULT_OWNER_ID,
    model: str | None = None,
) -> MemoryResponse:
    try:
        validated = _validate_memory_create(data)
    except ValidationError as exc:
        raise MemoryValidationError("invalid memory data") from exc

    content_hash = compute_content_hash(validated.content)

    existing = db.execute(
        select(Memory).where(
            and_(
                Memory.owner_id == owner_id,
                Memory.content_hash == content_hash,
            ),
        ),
    ).scalars().first()
    if existing is not None:
        raise MemoryDuplicateError("duplicate memory")

    try:
        result = embedding_client.embed(validated.content)
    except EmbeddingError as exc:
        raise _map_embedding_error(exc) from exc

    try:
        vector_bytes = encode_vector(result.vector)
        norm = vector_norm(result.vector)
    except (VectorError, ValueError) as exc:
        raise MemoryInvalidEmbeddingResponseError(
            "invalid embedding response",
        ) from exc

    embedding_model = model if model is not None else result.model

    memory = Memory(
        owner_id=owner_id,
        title=validated.title,
        content=validated.content,
        content_hash=content_hash,
        source=validated.source,
        tags_json=_serialize_tags(validated.tags),
        importance=validated.importance,
        metadata_json=_serialize_metadata(validated.metadata),
    )

    try:
        db.add(memory)
        db.flush()
        embedding_row = MemoryEmbedding(
            memory_id=memory.id,
            model=embedding_model,
            dimension=len(result.vector),
            vector=vector_bytes,
            vector_norm=norm,
        )
        db.add(embedding_row)
        db.commit()
        db.refresh(memory)
        return _memory_to_response(memory)
    except IntegrityError as exc:
        db.rollback()
        # Check if it's a duplicate hash conflict
        if "content_hash" in str(exc).lower() or "ux_memories_owner_hash" in str(
            exc
        ).lower():
            raise MemoryDuplicateError("duplicate memory") from exc
        raise
    except SQLAlchemyError:
        db.rollback()
        raise


def get_memory(
    db: Session,
    memory_id: int,
    *,
    owner_id: str = DEFAULT_OWNER_ID,
    include_archived: bool = True,
) -> MemoryResponse:
    memory = _get_memory_or_raise(
        db,
        memory_id,
        owner_id,
        include_archived=include_archived,
    )
    return _memory_to_response(memory)


def list_memories(
    db: Session,
    *,
    owner_id: str = DEFAULT_OWNER_ID,
    include_archived: bool = False,
    source: str | None = None,
    tags: list[str] | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[MemoryResponse], int]:
    conditions = [Memory.owner_id == owner_id]
    if not include_archived:
        conditions.append(Memory.archived_at.is_(None))
    if source is not None:
        conditions.append(Memory.source == source)

    if tags:
        conditions.extend(_exact_tag_condition(tag) for tag in tags)

    base_stmt = select(Memory).where(and_(*conditions))
    count_stmt = select(func.count()).select_from(Memory).where(and_(*conditions))

    memories = db.execute(
        base_stmt.order_by(Memory.id).offset(offset).limit(limit),
    ).scalars().all()

    total = db.execute(count_stmt).scalar_one()

    return [_memory_to_response(memory) for memory in memories], total


def update_memory(
    db: Session,
    memory_id: int,
    data: MemoryUpdate,
    embedding_client: EmbeddingClient,
    *,
    owner_id: str = DEFAULT_OWNER_ID,
    model: str | None = None,
) -> MemoryResponse:
    try:
        validated = _validate_memory_update(data)
    except ValidationError as exc:
        raise MemoryValidationError("invalid memory data") from exc

    memory = _get_memory_or_raise(
        db,
        memory_id,
        owner_id,
        include_archived=True,
    )

    update_data = validated.model_dump(exclude_unset=True)
    content_changed = "content" in update_data and update_data["content"] is not None

    if content_changed:
        new_content = update_data["content"]
        new_hash = compute_content_hash(new_content)

        existing = db.execute(
            select(Memory).where(
                and_(
                    Memory.owner_id == owner_id,
                    Memory.content_hash == new_hash,
                    Memory.id != memory_id,
                ),
            ),
        ).scalars().first()
        if existing is not None:
            raise MemoryDuplicateError("duplicate memory")

        try:
            result = embedding_client.embed(new_content)
        except EmbeddingError as exc:
            raise _map_embedding_error(exc) from exc

        try:
            vector_bytes = encode_vector(result.vector)
            norm = vector_norm(result.vector)
        except (VectorError, ValueError) as exc:
            raise MemoryInvalidEmbeddingResponseError(
                "invalid embedding response",
            ) from exc

        embedding_model = model if model is not None else result.model

        memory.content = new_content
        memory.content_hash = new_hash

        # Remove old embeddings for this memory and add new one
        for emb in db.execute(
            select(MemoryEmbedding).where(MemoryEmbedding.memory_id == memory_id),
        ).scalars().all():
            db.delete(emb)

        try:
            db.flush()
        except IntegrityError as exc:
            db.rollback()
            if "content_hash" in str(exc).lower():
                raise MemoryDuplicateError("duplicate memory") from exc
            raise
        except SQLAlchemyError:
            db.rollback()
            raise

        embedding_row = MemoryEmbedding(
            memory_id=memory_id,
            model=embedding_model,
            dimension=len(result.vector),
            vector=vector_bytes,
            vector_norm=norm,
        )
        db.add(embedding_row)

    if "title" in update_data:
        memory.title = update_data["title"]
    if "source" in update_data:
        memory.source = update_data["source"]
    if "tags" in update_data and update_data["tags"] is not None:
        memory.tags_json = _serialize_tags(update_data["tags"])
    if "importance" in update_data and update_data["importance"] is not None:
        memory.importance = update_data["importance"]
    if "metadata" in update_data and update_data["metadata"] is not None:
        memory.metadata_json = _serialize_metadata(update_data["metadata"])

    memory.updated_at = _utc_now()

    try:
        db.commit()
        db.refresh(memory)
        return _memory_to_response(memory)
    except IntegrityError as exc:
        db.rollback()
        if "content_hash" in str(exc).lower():
            raise MemoryDuplicateError("duplicate memory") from exc
        raise
    except SQLAlchemyError:
        db.rollback()
        raise


def archive_memory(
    db: Session,
    memory_id: int,
    *,
    owner_id: str = DEFAULT_OWNER_ID,
) -> MemoryResponse:
    memory = _get_memory_or_raise(
        db,
        memory_id,
        owner_id,
        include_archived=True,
    )
    if memory.archived_at is None:
        memory.archived_at = _utc_now()
        memory.updated_at = _utc_now()
    try:
        db.commit()
        db.refresh(memory)
        return _memory_to_response(memory)
    except SQLAlchemyError:
        db.rollback()
        raise


def restore_memory(
    db: Session,
    memory_id: int,
    *,
    owner_id: str = DEFAULT_OWNER_ID,
) -> MemoryResponse:
    memory = _get_memory_or_raise(
        db,
        memory_id,
        owner_id,
        include_archived=True,
    )
    if memory.archived_at is not None:
        memory.archived_at = None
        memory.updated_at = _utc_now()
    try:
        db.commit()
        db.refresh(memory)
        return _memory_to_response(memory)
    except SQLAlchemyError:
        db.rollback()
        raise


def delete_memory(
    db: Session,
    memory_id: int,
    *,
    owner_id: str = DEFAULT_OWNER_ID,
) -> None:
    memory = _get_memory_or_raise(
        db,
        memory_id,
        owner_id,
        include_archived=True,
    )
    try:
        # Delete embeddings first (don't rely on CASCADE)
        for emb in db.execute(
            select(MemoryEmbedding).where(MemoryEmbedding.memory_id == memory_id),
        ).scalars().all():
            db.delete(emb)
        db.delete(memory)
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise


def search_memories(
    db: Session,
    query: str,
    embedding_client: EmbeddingClient,
    *,
    owner_id: str = DEFAULT_OWNER_ID,
    top_k: int = 10,
    min_score: float = 0.0,
    source: str | None = None,
    tags: list[str] | None = None,
    include_archived: bool = False,
    model: str | None = None,
) -> list[MemorySearchHit]:
    try:
        result = embedding_client.embed(query)
    except EmbeddingError as exc:
        raise _map_embedding_error(exc) from exc

    query_vector = result.vector
    query_model = model if model is not None else result.model

    conditions = [
        Memory.owner_id == owner_id,
    ]
    if not include_archived:
        conditions.append(Memory.archived_at.is_(None))
    if source is not None:
        conditions.append(Memory.source == source)

    # Get memories with their embeddings
    stmt = (
        select(Memory, MemoryEmbedding)
        .join(MemoryEmbedding, MemoryEmbedding.memory_id == Memory.id)
        .where(and_(*conditions))
        .where(MemoryEmbedding.model == query_model)
    )

    rows = db.execute(stmt).all()

    candidates = []
    for memory, embedding in rows:
        if tags:
            memory_tags = _deserialize_tags(memory.tags_json)
            if not all(tag in memory_tags for tag in tags):
                continue

        try:
            stored_vector = decode_vector(
                embedding.vector,
                embedding.dimension,
            )
        except (VectorError, ValueError):
            continue  # Skip malformed vectors

        if len(stored_vector) != len(query_vector):
            continue  # Skip incompatible dimensions

        try:
            score = cosine_similarity(query_vector, stored_vector)
        except (VectorError, ValueError):
            continue  # Skip on error

        if score < min_score:
            continue

        candidates.append(
            (score, memory),
        )

    candidates.sort(key=lambda x: x[0], reverse=True)
    candidates = candidates[:top_k]

    hits = []
    for score, memory in candidates:
        hits.append(
            MemorySearchHit(
                memory=_memory_to_response(memory),
                score=score,
                trust="untrusted",
            ),
        )
    return hits
