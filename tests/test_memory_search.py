import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.memory.embeddings import EmbeddingResult, EmbeddingServiceUnavailableError
from app.memory.schemas import MemoryCreate
from app.memory.service import (
    MemoryEmbeddingUnavailableError,
    create_memory,
    search_memories,
)
from app.models import Memory, MemoryEmbedding


class FakeEmbeddingClient:
    def __init__(self, vector=None, raise_exc=None, calls=None):
        self.vector = vector if vector is not None else [1.0, 0.0, 0.0]
        self.raise_exc = raise_exc
        self.calls = calls if calls is not None else []

    def embed(self, text: str) -> EmbeddingResult:
        self.calls.append(text)
        if self.raise_exc:
            raise self.raise_exc
        return EmbeddingResult(
            vector=tuple(self.vector),
            model="nomic-embed-text:latest",
            dimension=len(self.vector),
        )


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
    )
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_similarity_ranking_identical_orthogonal_opposite(db_session):
    # Create memories with different vectors
    client1 = FakeEmbeddingClient([1.0, 0.0])
    create_memory(db_session, MemoryCreate(content="Doc1"), client1)

    client2 = FakeEmbeddingClient([0.0, 1.0])
    create_memory(db_session, MemoryCreate(content="Doc2"), client2)

    client3 = FakeEmbeddingClient([-1.0, 0.0])
    create_memory(db_session, MemoryCreate(content="Doc3"), client3)

    # Query with identical to doc1
    query_client = FakeEmbeddingClient([1.0, 0.0])
    results = search_memories(db_session, "query", query_client)
    assert len(results) == 2
    assert results[0].memory.content == "Doc1"  # identical
    assert results[0].score == pytest.approx(1.0)
    assert results[1].memory.content == "Doc2"  # orthogonal
    assert results[1].score == pytest.approx(0.0)

    # With min_score -1.0 we can get opposite too
    results_all = search_memories(db_session, "query", query_client, min_score=-1.0)
    assert len(results_all) == 3
    assert results_all[2].memory.content == "Doc3"
    assert results_all[2].score == pytest.approx(-1.0)


def test_top_k_and_min_score_filters(db_session):
    client1 = FakeEmbeddingClient([1.0, 0.0])
    create_memory(db_session, MemoryCreate(content="Doc1"), client1)
    client2 = FakeEmbeddingClient([0.8, 0.6])
    create_memory(db_session, MemoryCreate(content="Doc2"), client2)
    client3 = FakeEmbeddingClient([0.0, 1.0])
    create_memory(db_session, MemoryCreate(content="Doc3"), client3)

    query_client = FakeEmbeddingClient([1.0, 0.0])
    results = search_memories(db_session, "query", query_client, top_k=2)
    assert len(results) == 2

    results2 = search_memories(
        db_session,
        "query",
        query_client,
        min_score=0.5,
    )
    assert len(results2) >= 1
    for r in results2:
        assert r.score >= 0.5


def test_source_and_tag_filters(db_session):
    client = FakeEmbeddingClient([1.0, 0.0])
    create_memory(
        db_session,
        MemoryCreate(content="Doc1", source="web", tags=["ai"]),
        client,
    )
    create_memory(
        db_session,
        MemoryCreate(content="Doc2", source="local", tags=["other"]),
        client,
    )

    query_client = FakeEmbeddingClient([1.0, 0.0])
    results = search_memories(
        db_session,
        "query",
        query_client,
        source="web",
    )
    assert len(results) == 1
    assert results[0].memory.content == "Doc1"

    results2 = search_memories(
        db_session,
        "query",
        query_client,
        tags=["ai"],
    )
    assert len(results2) == 1
    assert results2[0].memory.content == "Doc1"


def test_archived_records_excluded(db_session):
    client = FakeEmbeddingClient([1.0, 0.0])
    create_memory(db_session, MemoryCreate(content="Doc1"), client)
    from app.memory.service import archive_memory

    archive_memory(db_session, 1)

    query_client = FakeEmbeddingClient([1.0, 0.0])
    results = search_memories(db_session, "query", query_client)
    assert len(results) == 0

    results2 = search_memories(db_session, "query", query_client, include_archived=True)
    assert len(results2) == 1


def test_owner_isolation_in_search(db_session):
    client1 = FakeEmbeddingClient([1.0, 0.0])
    create_memory(db_session, MemoryCreate(content="Owner1"), client1, owner_id="owner1")
    client2 = FakeEmbeddingClient([1.0, 0.0])
    create_memory(db_session, MemoryCreate(content="Owner2"), client2, owner_id="owner2")

    query_client = FakeEmbeddingClient([1.0, 0.0])
    results = search_memories(db_session, "query", query_client, owner_id="owner1")
    assert len(results) == 1
    assert results[0].memory.content == "Owner1"


def test_active_model_and_dimension_filtering(db_session):
    # Create with different dimensions
    client1 = FakeEmbeddingClient([1.0, 0.0, 0.0])  # dim 3
    create_memory(db_session, MemoryCreate(content="Doc1"), client1)

    query_client = FakeEmbeddingClient([1.0, 0.0])  # dim 2
    results = search_memories(db_session, "query", query_client)
    assert len(results) == 0  # incompatible dimension filtered out


def test_empty_store_behavior(db_session):
    query_client = FakeEmbeddingClient([1.0, 0.0])
    results = search_memories(db_session, "query", query_client)
    assert results == []


def test_embedding_failure_leaves_database_unchanged(db_session):
    client = FakeEmbeddingClient([1.0, 0.0])
    create_memory(db_session, MemoryCreate(content="Doc1"), client)

    query_client = FakeEmbeddingClient(
        raise_exc=EmbeddingServiceUnavailableError("fail"),
    )
    with pytest.raises(MemoryEmbeddingUnavailableError):
        search_memories(db_session, "query", query_client)
    assert db_session.query(Memory).count() == 1


def test_malformed_stored_vectors_are_safely_excluded(db_session):
    client = FakeEmbeddingClient([1.0, 0.0])
    create_memory(db_session, MemoryCreate(content="Doc1"), client)

    # Corrupt the vector
    emb = db_session.query(MemoryEmbedding).first()
    emb.vector = b"bad"  # too short
    db_session.commit()

    query_client = FakeEmbeddingClient([1.0, 0.0])
    results = search_memories(db_session, "query", query_client)
    assert len(results) == 0


def test_result_trust_label_and_no_vector_exposure(db_session):
    client = FakeEmbeddingClient([1.0, 0.0])
    create_memory(db_session, MemoryCreate(content="Doc1"), client)

    query_client = FakeEmbeddingClient([1.0, 0.0])
    results = search_memories(db_session, "query", query_client)
    assert len(results) == 1
    assert results[0].trust == "untrusted"
    # Ensure no vector attributes exposed
    assert not hasattr(results[0], "vector")
    assert not hasattr(results[0], "vector_norm")
    # Check memory response has no vector fields
    assert not hasattr(results[0].memory, "vector")


def test_search_does_not_modify_database_records(db_session):
    client = FakeEmbeddingClient([1.0, 0.0])
    create_memory(db_session, MemoryCreate(content="Doc1"), client)

    mem_before = db_session.query(Memory).first()
    updated_before = mem_before.updated_at
    archived_before = mem_before.archived_at

    query_client = FakeEmbeddingClient([1.0, 0.0])
    search_memories(db_session, "query", query_client)

    db_session.refresh(mem_before)
    assert mem_before.updated_at == updated_before
    assert mem_before.archived_at == archived_before
