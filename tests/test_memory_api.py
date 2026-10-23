import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.memory.embeddings import EmbeddingResult, EmbeddingServiceUnavailableError
from app.memory.routes import router as memories_router
from app.models import Memory


class FakeEmbeddingClient:
    def __init__(self, vector=None, raise_exc=None):
        self.vector = vector if vector is not None else [1.0, 0.0, 0.0]
        self.raise_exc = raise_exc

    def embed(self, text: str) -> EmbeddingResult:
        if self.raise_exc:
            raise self.raise_exc
        return EmbeddingResult(
            vector=tuple(self.vector),
            model="nomic-embed-text:latest",
            dimension=len(self.vector),
        )


@pytest.fixture
def app_client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    app = FastAPI()
    app.include_router(memories_router)

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    from app.memory import routes

    previous_embedding_client = routes.EMBEDDING_CLIENT
    try:
        routes.EMBEDDING_CLIENT = None
        fake_client = FakeEmbeddingClient([1.0, 0.0, 0.0])
        routes.EMBEDDING_CLIENT = fake_client

        client = TestClient(app)
        yield client, SessionLocal
    finally:
        routes.EMBEDDING_CLIENT = previous_embedding_client
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_create_and_retrieve_memory(app_client):
    client, _ = app_client
    response = client.post("/memories", json={"content": "Test memory"})
    assert response.status_code == 201
    data = response.json()
    assert data["content"] == "Test memory"
    assert "vector" not in data
    memory_id = data["id"]

    response2 = client.get(f"/memories/{memory_id}")
    assert response2.status_code == 200
    assert response2.json()["content"] == "Test memory"


def test_list_memories(app_client):
    client, _ = app_client
    client.post("/memories", json={"content": "First"})
    client.post("/memories", json={"content": "Second"})
    response = client.get("/memories")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 2
    assert data["total"] == 2


def test_list_memories_with_filters(app_client):
    client, _ = app_client
    client.post(
        "/memories",
        json={"content": "First", "source": "web", "tags": ["ai"]},
    )
    client.post(
        "/memories",
        json={"content": "Second", "source": "local", "tags": ["other"]},
    )

    response = client.get("/memories", params={"source": "web"})
    assert response.status_code == 200
    assert response.json()["total"] == 1

    response = client.get("/memories", params={"tags": "ai"})
    assert response.status_code == 200
    assert response.json()["total"] == 1


def test_update_archive_restore_delete(app_client):
    client, _ = app_client
    response = client.post("/memories", json={"content": "Original"})
    memory_id = response.json()["id"]

    response = client.patch(f"/memories/{memory_id}", json={"importance": 80})
    assert response.status_code == 200
    assert response.json()["importance"] == 80

    response = client.post(f"/memories/{memory_id}/archive")
    assert response.status_code == 200
    assert response.json()["archived_at"] is not None

    response = client.get("/memories")
    assert response.status_code == 200
    assert len(response.json()["items"]) == 0

    response = client.post(f"/memories/{memory_id}/restore")
    assert response.status_code == 200
    assert response.json()["archived_at"] is None

    response = client.delete(f"/memories/{memory_id}")
    assert response.status_code == 204

    response = client.get(f"/memories/{memory_id}")
    assert response.status_code == 404


def test_semantic_search_with_fake_embeddings(app_client):
    client, _ = app_client
    client.post("/memories", json={"content": "Cat"})
    client.post("/memories", json={"content": "Dog"})

    response = client.post("/memories/search", json={"query": "pet"})
    assert response.status_code == 200
    data = response.json()
    assert "results" in data
    for result in data["results"]:
        assert result["trust"] == "untrusted"
        assert "vector" not in result
        assert "vector" not in result["memory"]


def test_duplicate_memory_conflict(app_client):
    client, _ = app_client
    response = client.post("/memories", json={"content": "Duplicate"})
    assert response.status_code == 201
    response = client.post("/memories", json={"content": "duplicate"})
    assert response.status_code == 409


def test_missing_memory_responses(app_client):
    client, _ = app_client
    response = client.get("/memories/999")
    assert response.status_code == 404
    response = client.patch("/memories/999", json={"importance": 50})
    assert response.status_code == 404
    response = client.delete("/memories/999")
    assert response.status_code == 404


def test_invalid_request_validation(app_client):
    client, _ = app_client
    response = client.post("/memories", json={"content": ""})
    assert response.status_code == 422
    response = client.post("/memories/search", json={"query": ""})
    assert response.status_code == 422


def test_patch_rejects_explicit_null_source(app_client):
    client, _ = app_client
    response = client.post("/memories", json={"content": "Original"})
    memory_id = response.json()["id"]

    response = client.patch(
        f"/memories/{memory_id}",
        json={"source": None},
    )

    assert response.status_code == 422

    response = client.get(f"/memories/{memory_id}")
    assert response.json()["source"] == "manual"


@pytest.mark.parametrize(
    ("tag_count", "expected_status"),
    [
        (20, 200),
        (21, 422),
    ],
    ids=["maximum-tags", "too-many-tags"],
)
def test_list_tag_filter_limit(app_client, tag_count, expected_status):
    client, _ = app_client
    params = [("tags", f"tag-{index}") for index in range(tag_count)]

    response = client.get("/memories", params=params)

    assert response.status_code == expected_status


@pytest.mark.parametrize(
    "vector",
    [
        [10**100],
        [10**400],
        [1e39],
        [1e300],
    ],
    ids=[
        "huge-integer",
        "integer-beyond-float",
        "float32-overflow",
        "huge-float",
    ],
)
def test_invalid_float32_embedding_returns_503(app_client, vector):
    client, _ = app_client
    from app.memory import routes

    routes.EMBEDDING_CLIENT = FakeEmbeddingClient(vector=vector)

    response = client.post("/memories", json={"content": "Test"})

    assert response.status_code == 503


def test_embedding_service_failure(app_client):
    client, _ = app_client
    from app.memory import routes
    routes.EMBEDDING_CLIENT = FakeEmbeddingClient(raise_exc=EmbeddingServiceUnavailableError("fail"))

    response = client.post("/memories", json={"content": "Test"})
    assert response.status_code == 503


def test_responses_never_expose_vectors(app_client):
    client, _ = app_client
    response = client.post("/memories", json={"content": "Test"})
    data = response.json()
    assert "vector" not in data
    assert "vector_bytes" not in data

    response = client.get("/memories")
    for item in response.json()["items"]:
        assert "vector" not in item

    response = client.post("/memories/search", json={"query": "test"})
    for result in response.json()["results"]:
        assert "vector" not in result
        assert "vector_norm" not in result
        assert "vector" not in result["memory"]


def test_request_data_cannot_select_different_owner(app_client):
    client, SessionLocal = app_client
    response = client.post(
        "/memories",
        json={"content": "Test", "owner_id": "other"},
    )
    assert response.status_code == 201
    db = SessionLocal()
    mem = db.query(Memory).first()
    assert mem.owner_id == "local"
    db.close()


def test_search_embedding_failure_returns_503(app_client):
    client, _ = app_client
    from app.memory import routes

    routes.EMBEDDING_CLIENT = FakeEmbeddingClient(
        raise_exc=EmbeddingServiceUnavailableError("fail"),
    )

    response = client.post("/memories/search", json={"query": "test"})
    assert response.status_code == 503


def test_unexpected_database_failure_returns_generic_500(
    app_client,
    monkeypatch,
):
    client, _ = app_client
    from sqlalchemy.exc import SQLAlchemyError

    from app.memory import routes

    def fail(*args, **kwargs):
        raise SQLAlchemyError("sensitive SQL details")

    monkeypatch.setattr(routes, "create_memory", fail)

    response = client.post("/memories", json={"content": "Test"})
    assert response.status_code == 500
    assert "sensitive" not in response.text
    assert "SQL" not in response.text


def test_unexpected_service_failure_returns_generic_500(
    app_client,
    monkeypatch,
):
    client, _ = app_client
    from app.memory import routes

    def fail(*args, **kwargs):
        raise RuntimeError("internal secret")

    monkeypatch.setattr(routes, "get_memory", fail)

    response = client.get("/memories/1")
    assert response.status_code == 500
    assert "secret" not in response.text
    assert "RuntimeError" not in response.text
