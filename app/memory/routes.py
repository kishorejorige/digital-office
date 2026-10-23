import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db
from app.memory.config import DEFAULT_CONFIG
from app.memory.embeddings import (
    EmbeddingError,
    EmbeddingResult,
    EmbeddingServiceUnavailableError,
    InvalidEmbeddingResponseError,
    OllamaEmbeddingClient,
)
from app.memory.schemas import (
    MemoryCreate,
    MemoryListQuery,
    MemoryListResponse,
    MemoryResponse,
    MemorySearchRequest,
    MemorySearchResponse,
    MemorySearchResult,
    MemoryUpdate,
)
from app.memory.service import (
    MemoryDuplicateError,
    MemoryEmbeddingUnavailableError,
    MemoryInvalidEmbeddingResponseError,
    MemoryNotFoundError,
    MemoryValidationError,
    archive_memory,
    create_memory,
    delete_memory,
    get_memory,
    list_memories,
    restore_memory,
    search_memories,
    update_memory,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/memories", tags=["memories"])

EMBEDDING_CLIENT: OllamaEmbeddingClient | None = None


class _RouteEmbeddingClient:
    def embed(self, text: str) -> EmbeddingResult:
        global EMBEDDING_CLIENT
        if EMBEDDING_CLIENT is None:
            EMBEDDING_CLIENT = OllamaEmbeddingClient(config=DEFAULT_CONFIG)
        return EMBEDDING_CLIENT.embed(text)


def get_embedding_client() -> _RouteEmbeddingClient:
    return _RouteEmbeddingClient()


@router.post("", response_model=MemoryResponse, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=MemoryResponse, status_code=status.HTTP_201_CREATED)
def create_memory_endpoint(
    data: MemoryCreate,
    db: Session = Depends(get_db),
    embedding_client: _RouteEmbeddingClient = Depends(get_embedding_client),
):
    try:
        return create_memory(db, data, embedding_client)
    except MemoryValidationError as exc:
        raise HTTPException(status_code=422, detail="Invalid memory data") from exc
    except MemoryDuplicateError as exc:
        raise HTTPException(status_code=409, detail="Duplicate memory") from exc
    except MemoryEmbeddingUnavailableError as exc:
        raise HTTPException(status_code=503, detail="Embedding service unavailable") from exc
    except MemoryInvalidEmbeddingResponseError as exc:
        raise HTTPException(status_code=503, detail="Embedding service unavailable") from exc
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail="Invalid memory data") from exc
    except SQLAlchemyError:
        logger.error("Database error while creating memory")
        raise HTTPException(
            status_code=500,
            detail="Unable to create memory due to a database error",
        ) from None
    except Exception:  # noqa: BLE001
        logger.error("Unexpected error while creating memory")
        raise HTTPException(
            status_code=500,
            detail="Unable to create memory",
        ) from None


@router.get("", response_model=MemoryListResponse)
@router.get("/", response_model=MemoryListResponse)
def list_memories_endpoint(
    query: Annotated[MemoryListQuery, Query()],
    db: Session = Depends(get_db),
):
    try:
        items, total = list_memories(
            db,
            include_archived=query.include_archived,
            source=query.source,
            tags=query.tags,
            limit=query.limit,
            offset=query.offset,
        )
        return MemoryListResponse(
            items=items,
            total=total,
            limit=query.limit,
            offset=query.offset,
        )
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail="Invalid query parameters") from exc
    except SQLAlchemyError:
        logger.error("Database error while listing memories")
        raise HTTPException(
            status_code=500,
            detail="Unable to list memories due to a database error",
        ) from None
    except Exception:  # noqa: BLE001
        logger.error("Unexpected error while listing memories")
        raise HTTPException(
            status_code=500,
            detail="Unable to list memories",
        ) from None


@router.get("/{memory_id}", response_model=MemoryResponse)
def get_memory_endpoint(
    memory_id: int,
    db: Session = Depends(get_db),
    include_archived: bool = Query(default=True),
):
    try:
        return get_memory(db, memory_id, include_archived=include_archived)
    except MemoryNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Memory not found") from exc
    except SQLAlchemyError:
        logger.error("Database error while retrieving memory")
        raise HTTPException(
            status_code=500,
            detail="Unable to retrieve memory due to a database error",
        ) from None
    except Exception:  # noqa: BLE001
        logger.error("Unexpected error while retrieving memory")
        raise HTTPException(
            status_code=500,
            detail="Unable to retrieve memory",
        ) from None


@router.patch("/{memory_id}", response_model=MemoryResponse)
def update_memory_endpoint(
    memory_id: int,
    data: MemoryUpdate,
    db: Session = Depends(get_db),
    embedding_client: _RouteEmbeddingClient = Depends(get_embedding_client),
):
    try:
        return update_memory(db, memory_id, data, embedding_client)
    except MemoryNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Memory not found") from exc
    except MemoryValidationError as exc:
        raise HTTPException(status_code=422, detail="Invalid memory data") from exc
    except MemoryDuplicateError as exc:
        raise HTTPException(status_code=409, detail="Duplicate memory") from exc
    except MemoryEmbeddingUnavailableError as exc:
        raise HTTPException(status_code=503, detail="Embedding service unavailable") from exc
    except MemoryInvalidEmbeddingResponseError as exc:
        raise HTTPException(status_code=503, detail="Embedding service unavailable") from exc
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail="Invalid memory data") from exc
    except SQLAlchemyError:
        logger.error("Database error while updating memory")
        raise HTTPException(
            status_code=500,
            detail="Unable to update memory due to a database error",
        ) from None
    except Exception:  # noqa: BLE001
        logger.error("Unexpected error while updating memory")
        raise HTTPException(
            status_code=500,
            detail="Unable to update memory",
        ) from None


@router.post("/{memory_id}/archive", response_model=MemoryResponse)
def archive_memory_endpoint(
    memory_id: int,
    db: Session = Depends(get_db),
):
    try:
        return archive_memory(db, memory_id)
    except MemoryNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Memory not found") from exc
    except SQLAlchemyError:
        logger.error("Database error while archiving memory")
        raise HTTPException(
            status_code=500,
            detail="Unable to archive memory due to a database error",
        ) from None
    except Exception:  # noqa: BLE001
        logger.error("Unexpected error while archiving memory")
        raise HTTPException(
            status_code=500,
            detail="Unable to archive memory",
        ) from None


@router.post("/{memory_id}/restore", response_model=MemoryResponse)
def restore_memory_endpoint(
    memory_id: int,
    db: Session = Depends(get_db),
):
    try:
        return restore_memory(db, memory_id)
    except MemoryNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Memory not found") from exc
    except SQLAlchemyError:
        logger.error("Database error while restoring memory")
        raise HTTPException(
            status_code=500,
            detail="Unable to restore memory due to a database error",
        ) from None
    except Exception:  # noqa: BLE001
        logger.error("Unexpected error while restoring memory")
        raise HTTPException(
            status_code=500,
            detail="Unable to restore memory",
        ) from None


@router.delete("/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_memory_endpoint(
    memory_id: int,
    db: Session = Depends(get_db),
):
    try:
        delete_memory(db, memory_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except MemoryNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Memory not found") from exc
    except SQLAlchemyError:
        logger.error("Database error while deleting memory")
        raise HTTPException(
            status_code=500,
            detail="Unable to delete memory due to a database error",
        ) from None
    except Exception:  # noqa: BLE001
        logger.error("Unexpected error while deleting memory")
        raise HTTPException(
            status_code=500,
            detail="Unable to delete memory",
        ) from None


@router.post("/search", response_model=MemorySearchResponse)
def search_memories_endpoint(
    request: MemorySearchRequest,
    db: Session = Depends(get_db),
    embedding_client: _RouteEmbeddingClient = Depends(get_embedding_client),
):
    try:
        hits = search_memories(
            db,
            request.query,
            embedding_client,
            top_k=request.top_k,
            min_score=request.min_score,
            source=request.source,
            tags=request.tags,
            include_archived=request.include_archived,
        )
        results = [
            MemorySearchResult(memory=hit.memory, score=hit.score, trust=hit.trust)
            for hit in hits
        ]
        return MemorySearchResponse(results=results)
    except MemoryEmbeddingUnavailableError as exc:
        raise HTTPException(status_code=503, detail="Embedding service unavailable") from exc
    except MemoryInvalidEmbeddingResponseError as exc:
        raise HTTPException(status_code=503, detail="Embedding service unavailable") from exc
    except EmbeddingServiceUnavailableError as exc:
        raise HTTPException(status_code=503, detail="Embedding service unavailable") from exc
    except InvalidEmbeddingResponseError as exc:
        raise HTTPException(status_code=503, detail="Embedding service unavailable") from exc
    except EmbeddingError as exc:
        raise HTTPException(status_code=503, detail="Embedding service unavailable") from exc
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail="Invalid search request") from exc
    except SQLAlchemyError:
        logger.error("Database error while searching memories")
        raise HTTPException(
            status_code=500,
            detail="Unable to search memories due to a database error",
        ) from None
    except Exception:  # noqa: BLE001
        logger.error("Unexpected error while searching memories")
        raise HTTPException(
            status_code=500,
            detail="Unable to search memories",
        ) from None
