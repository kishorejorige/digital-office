import os

os.environ.setdefault("DIGITAL_OFFICE_SKIP_DB_CREATE", "1")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import research_memory
from app.database import Base, get_db
from app.main import app
from app.memory.embeddings import EmbeddingResult
from app.memory.schemas import MemoryCreate
from app.memory.service import create_memory


class FakeEmbeddingClient:
    def __init__(self, vector=None):
        self.vector = vector if vector is not None else [0.5, 0.5, 0.5]

    def embed(self, text: str) -> EmbeddingResult:
        return EmbeddingResult(
            vector=tuple(self.vector),
            model="nomic-embed-text:latest",
            dimension=len(self.vector),
        )


def test_limit_to_five_and_no_full_content():
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
    try:
        client = TestClient(app)
        db = TestingSessionLocal()
        try:
            fake = FakeEmbeddingClient([0.5, 0.5, 0.5])
            for i in range(10):
                create_memory(db, MemoryCreate(content=f"Python automation task {i}"), fake)
        finally:
            db.close()

        retriever = research_memory.ResearchMemoryRetriever(
            embedding_client=FakeEmbeddingClient([0.5, 0.5, 0.5])
        )
        research_memory._default_retriever = retriever

        response = client.post(
            "/tasks",
            json={"task": "Find freelance Python automation opportunities"},
        )
        assert response.status_code == 200
        data = response.json()
        mr = data["memory_retrieval"]
        assert mr["count"] <= 5
        assert len(mr["memories"]) <= 5
        for m in mr["memories"]:
            assert set(m.keys()) == {"id", "title", "score", "trust"}
            assert m["trust"] == "untrusted"
        # research unchanged
        assert data["agent"] == "research"
        assert data["status"] == "completed"
        for opp in data["opportunities"]:
            assert 0 <= opp["fit_score"] <= 100
            assert opp["decision"] in ("APPLY", "MAYBE", "SKIP")
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_email_calendar_unknown_unaffected():
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
    try:
        client = TestClient(app)

        r1 = client.post("/tasks", json={"task": "Write an email proposal to the client"})
        assert r1.status_code == 200
        d1 = r1.json()
        assert d1.get("route") == "email"
        assert d1.get("status") == "accepted"
        assert "memory_retrieval" not in d1

        r2 = client.post("/tasks", json={"task": "Schedule a meeting with the client"})
        assert r2.status_code == 200
        d2 = r2.json()
        assert d2.get("route") == "calendar"
        assert d2.get("status") == "accepted"
        assert "memory_retrieval" not in d2

        r3 = client.post("/tasks", json={"task": "Make me a cup of tea"})
        assert r3.status_code == 200
        d3 = r3.json()
        assert d3.get("route") == "unknown"
        assert d3.get("status") == "accepted"
        assert "memory_retrieval" not in d3
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
