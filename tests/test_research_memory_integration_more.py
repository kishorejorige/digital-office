import os

os.environ.setdefault("DIGITAL_OFFICE_SKIP_DB_CREATE", "1")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import research_memory
from app.database import Base, get_db
from app.main import app
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
        # Archived should be excluded
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

        # Different vector so no match
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


def test_unavailable_on_embedding_error_but_research_still_completes():
    engine, _ = setup_app_db()
    try:
        client = TestClient(app)

        retriever = research_memory.ResearchMemoryRetriever(
            embedding_client=FakeEmbeddingClient(raise_exc=EmbeddingServiceUnavailableError("down"))
        )
        research_memory._default_retriever = retriever

        response = client.post(
            "/tasks",
            json={"task": "Find freelance Python automation opportunities"},
        )
        assert response.status_code == 200
        data = response.json()
        # Research still completes
        assert data["agent"] == "research"
        assert data["status"] == "completed"
        assert data["count"] == 3
        assert len(data["opportunities"]) == 3
        # Memory retrieval reports unavailable
        mr = data["memory_retrieval"]
        assert mr["status"] == "unavailable"
        assert mr["count"] == 0
        assert mr["memories"] == []
    finally:
        teardown_app_db(engine)
