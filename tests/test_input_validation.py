import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
    )

    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.mark.parametrize(
    "task",
    [
        "",
        "   ",
    ],
)
def test_tasks_reject_blank_task(client, task):
    response = client.post(
        "/tasks",
        json={"task": task},
    )

    assert response.status_code == 422


def test_tasks_reject_missing_task(client):
    response = client.post("/tasks", json={})

    assert response.status_code == 422


@pytest.mark.parametrize(
    "lead",
    [
        {
            "source": "",
            "title": "Valid title",
        },
        {
            "source": "Manual",
            "title": "   ",
        },
    ],
)
def test_leads_reject_blank_required_fields(client, lead):
    response = client.post("/leads", json=lead)

    assert response.status_code == 422


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("fit_score", -1),
        ("fit_score", 101),
        ("payment_score", -1),
        ("payment_score", 101),
    ],
)
def test_leads_reject_scores_outside_range(client, field, value):
    lead = {
        "source": "Manual",
        "title": "Validation test lead",
        field: value,
    }

    response = client.post("/leads", json=lead)

    assert response.status_code == 422
