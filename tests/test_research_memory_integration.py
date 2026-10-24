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


def test_research_returns_memory_retrieval_with_results():
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
            fake = FakeEmbeddingClient(vector=[0.1, 0.2, 0.3])
            create_memory(db, MemoryCreate(content="Python automation for invoices"), fake)
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
        assert "memory_retrieval" in data
        mr = data["memory_retrieval"]
        assert mr["status"] in ("success", "no_matches")
        assert isinstance(mr["count"], int)
        assert mr["count"] <= 5
        assert isinstance(mr["memories"], list)
        if mr["memories"]:
            for m in mr["memories"]:
                assert "id" in m
                assert "title" in m
                assert "score" in m
                assert m["trust"] == "untrusted"
                assert "content" not in m
                assert "embeddings" not in m
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
