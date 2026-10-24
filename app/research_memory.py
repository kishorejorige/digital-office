import logging

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.memory.config import DEFAULT_CONFIG, RESEARCH_MEMORY_MIN_SCORE
from app.memory.embeddings import OllamaEmbeddingClient
from app.memory.service import (
    MemoryEmbeddingUnavailableError,
    MemoryError,
    MemoryInvalidEmbeddingResponseError,
    search_memories,
)

logger = logging.getLogger(__name__)

DEFAULT_MIN_SCORE = RESEARCH_MEMORY_MIN_SCORE
DEFAULT_MAX_RESULTS = 5


class ResearchMemoryRetriever:
    def __init__(self, embedding_client=None, min_score: float | None = None, max_results: int = DEFAULT_MAX_RESULTS):
        if min_score is None:
            min_score = RESEARCH_MEMORY_MIN_SCORE
        self.embedding_client = embedding_client
        self.min_score = min_score
        self.max_results = max_results

    def retrieve(self, db: Session, task: str) -> dict:
        if db is None:
            return {
                "status": "unavailable",
                "count": 0,
                "memories": [],
            }

        try:
            client = self.embedding_client
            if client is None:
                client = OllamaEmbeddingClient(config=DEFAULT_CONFIG)

            hits = search_memories(
                db,
                task,
                client,
                top_k=self.max_results,
                min_score=self.min_score,
                include_archived=False,
            )
        except (MemoryEmbeddingUnavailableError, MemoryInvalidEmbeddingResponseError):
            try:
                db.rollback()
            except SQLAlchemyError:
                logger.warning("Failed to roll back after research memory embedding error")
            return {
                "status": "unavailable",
                "count": 0,
                "memories": [],
            }
        except MemoryError:
            try:
                db.rollback()
            except SQLAlchemyError:
                logger.warning("Failed to roll back after research memory error")
            return {
                "status": "unavailable",
                "count": 0,
                "memories": [],
            }
        except SQLAlchemyError:
            try:
                db.rollback()
            except SQLAlchemyError:
                logger.warning("Failed to roll back after research memory database error")
            logger.warning("Database error while retrieving research memories")
            return {
                "status": "unavailable",
                "count": 0,
                "memories": [],
            }

        if not hits:
            return {
                "status": "no_matches",
                "count": 0,
                "memories": [],
            }

        memories = []
        for hit in hits:
            mem = hit.memory
            memories.append(
                {
                    "id": mem.id,
                    "title": mem.title,
                    "score": hit.score,
                    "trust": hit.trust,
                }
            )

        return {
            "status": "success",
            "count": len(memories),
            "memories": memories,
        }


_default_retriever = ResearchMemoryRetriever()


def retrieve_research_memories(db: Session, task: str) -> dict:
    return _default_retriever.retrieve(db, task)
