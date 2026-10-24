from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import research_memory
from app.database import Base, get_db
from app.main import app
from app.memory.config import (
    ConfigurationError,
    _validate_research_min_score,
    load_research_config,
)
from app.memory.embeddings import EmbeddingResult, EmbeddingServiceUnavailableError
from app.memory.schemas import MemoryCreate
from app.memory.service import archive_memory, create_memory


class FakeEmbeddingClient:
    def __init__(self, vector=None, raise_exc=None):
        self.vector = vector if vector is not None else [0.1, 0.2, 0.3]
        self.raise_exc = raise_exc
        self.calls = []

    def embed(self, text: str) -> EmbeddingResult:
        self.calls.append(text)
        if self.raise_exc:
            raise self.raise_exc
        return EmbeddingResult(
            vector=tuple(self.vector),
            model="nomic-embed-text:latest",
            dimension=len(self.vector),
        )


def setup_app_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
    )
    app.dependency_overrides[get_db] = lambda: TestingSessionLocal()
    return engine, TestingSessionLocal


def teardown_app_db(engine):
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def test_research_memory_min_score_default_zero():
    assert load_research_config({}) == 0.0


def test_research_memory_min_score_valid_range():
    assert load_research_config({"RESEARCH_MEMORY_MIN_SCORE": "-1.0"}) == -1.0
    assert load_research_config({"RESEARCH_MEMORY_MIN_SCORE": "1.0"}) == 1.0
    assert load_research_config({"RESEARCH_MEMORY_MIN_SCORE": "0.5"}) == 0.5


def test_research_memory_min_score_invalid():
    import pytest

    for bad in ["", " ", "abc", "nan", "inf", "-inf", "2.0", "-1.1", None]:
        if bad is None:
            continue
        with pytest.raises(ConfigurationError):
            load_research_config({"RESEARCH_MEMORY_MIN_SCORE": bad})
    with pytest.raises(ConfigurationError):
        _validate_research_min_score(float("nan"))
    with pytest.raises(ConfigurationError):
        _validate_research_min_score(float("inf"))


def test_score_exactly_at_threshold_included_with_default_semantics():
    engine, TestingSessionLocal = setup_app_db()
    try:
        client = TestClient(app)
        db = TestingSessionLocal()
        try:
            fake = FakeEmbeddingClient(vector=[1.0, 0.0, 0.0])
            create_memory(db, MemoryCreate(content="Python automation for invoices"), fake)
        finally:
            db.close()

        retriever = research_memory.ResearchMemoryRetriever(
            embedding_client=FakeEmbeddingClient(vector=[1.0, 0.0, 0.0]),
            min_score=1.0,
        )
        research_memory._default_retriever = retriever

        response = client.post(
            "/tasks",
            json={"task": "Find freelance Python automation opportunities"},
        )
        assert response.status_code == 200
        data = response.json()
        mr = data["memory_retrieval"]
        assert mr["status"] == "success"
        assert mr["count"] >= 1
        for m in mr["memories"]:
            assert set(m.keys()) == {"id", "title", "score", "trust"}
            assert m["trust"] == "untrusted"
            assert "content" not in m
            assert "embeddings" not in m
    finally:
        teardown_app_db(engine)


def test_score_below_threshold_excluded():
    engine, TestingSessionLocal = setup_app_db()
    try:
        client = TestClient(app)
        db = TestingSessionLocal()
        try:
            fake = FakeEmbeddingClient(vector=[1.0, 0.0, 0.0])
            create_memory(db, MemoryCreate(content="some unrelated content"), fake)
        finally:
            db.close()

        retriever = research_memory.ResearchMemoryRetriever(
            embedding_client=FakeEmbeddingClient(vector=[-1.0, 0.0, 0.0]),
            min_score=0.0,
        )
        research_memory._default_retriever = retriever

        response = client.post(
            "/tasks",
            json={"task": "Find freelance Python automation opportunities"},
        )
        assert response.status_code == 200
        data = response.json()
        mr = data["memory_retrieval"]
        assert mr["status"] == "no_matches"
        assert mr["count"] == 0
        assert mr["memories"] == []
    finally:
        teardown_app_db(engine)


def test_archived_memories_excluded():
    engine, TestingSessionLocal = setup_app_db()
    try:
        client = TestClient(app)
        db = TestingSessionLocal()
        try:
            fake = FakeEmbeddingClient(vector=[0.1, 0.2, 0.3])
            mem = create_memory(db, MemoryCreate(content="archived content here"), fake)
            archive_memory(db, mem.id)
        finally:
            db.close()

        retriever = research_memory.ResearchMemoryRetriever(
            embedding_client=FakeEmbeddingClient(vector=[0.1, 0.2, 0.3])
        )
        research_memory._default_retriever = retriever

        response = client.post(
            "/tasks",
            json={"task": "Find freelance Python automation opportunities"},
        )
        assert response.status_code == 200
        data = response.json()
        mr = data["memory_retrieval"]
        assert mr["status"] == "no_matches"
        assert mr["count"] == 0
        assert mr["memories"] == []
    finally:
        teardown_app_db(engine)


def test_no_matches_reports_no_matches():
    engine, TestingSessionLocal = setup_app_db()
    try:
        client = TestClient(app)
        db = TestingSessionLocal()
        try:
            fake = FakeEmbeddingClient(vector=[0.1, 0.2, 0.3])
            create_memory(db, MemoryCreate(content="some unrelated content"), fake)
        finally:
            db.close()

        retriever = research_memory.ResearchMemoryRetriever(
            embedding_client=FakeEmbeddingClient(vector=[1.0, 0.0, 0.0]),
            min_score=0.99,
        )
        research_memory._default_retriever = retriever

        response = client.post(
            "/tasks",
            json={"task": "Find freelance Python automation opportunities"},
        )
        assert response.status_code == 200
        data = response.json()
        mr = data["memory_retrieval"]
        assert mr["status"] == "no_matches"
        assert mr["count"] == 0
        assert mr["memories"] == []
    finally:
        teardown_app_db(engine)


def test_unavailable_on_embedding_timeout_but_research_still_completes():
    engine, _ = setup_app_db()
    try:
        client = TestClient(app)

        retriever = research_memory.ResearchMemoryRetriever(
            embedding_client=FakeEmbeddingClient(raise_exc=EmbeddingServiceUnavailableError("embedding service timed out"))
        )
        research_memory._default_retriever = retriever

        response = client.post(
            "/tasks",
            json={"task": "Find freelance Python automation opportunities"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["agent"] == "research"
        assert data["status"] == "completed"
        assert data["count"] == 3
        assert len(data["opportunities"]) == 3
        mr = data["memory_retrieval"]
        assert mr["status"] == "unavailable"
        assert mr["count"] == 0
        assert mr["memories"] == []
    finally:
        teardown_app_db(engine)


def test_db_retrieval_failure_triggers_safe_rollback_and_fallback():
    engine, TestingSessionLocal = setup_app_db()
    try:
        client = TestClient(app)
        db = TestingSessionLocal()
        try:
            pass
        finally:
            db.close()

        class FailingSearchClient:
            def embed(self, text: str) -> EmbeddingResult:
                return EmbeddingResult(
                    vector=(0.1, 0.2, 0.3),
                    model="nomic-embed-text:latest",
                    dimension=3,
                )

        orig_search = research_memory.search_memories

        def failing_search(*args, **kwargs):
            raise SQLAlchemyError("db failure")

        research_memory.search_memories = failing_search
        retriever = research_memory.ResearchMemoryRetriever(embedding_client=FailingSearchClient())
        research_memory._default_retriever = retriever
        try:
            response = client.post(
                "/tasks",
                json={"task": "Find freelance Python automation opportunities"},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["agent"] == "research"
            assert data["status"] == "completed"
            mr = data["memory_retrieval"]
            assert mr["status"] == "unavailable"
            assert mr["count"] == 0
            assert mr["memories"] == []
        finally:
            research_memory.search_memories = orig_search
    finally:
        teardown_app_db(engine)
