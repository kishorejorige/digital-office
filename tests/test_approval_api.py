
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import Approval


@pytest.fixture
def api_client():
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

    with TestClient(app) as client:
        yield client, TestingSessionLocal

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def create_approval(session_factory, status="pending"):
    with session_factory() as db:
        approval = Approval(
            lead_id=1,
            approval_type="proposal",
            draft="Test proposal",
            status=status,
        )
        db.add(approval)
        db.commit()
        db.refresh(approval)
        return approval.id


def test_approve_pending_approval_returns_200(api_client):
    client, session_factory = api_client
    approval_id = create_approval(session_factory)

    response = client.post(
        f"/approvals/{approval_id}/approve"
    )

    assert response.status_code == 200
    assert response.json()["status"] == "approved"


def test_reject_pending_approval_returns_200(api_client):
    client, session_factory = api_client
    approval_id = create_approval(session_factory)

    response = client.post(
        f"/approvals/{approval_id}/reject"
    )

    assert response.status_code == 200
    assert response.json()["status"] == "rejected"


@pytest.mark.parametrize(
    ("initial_status", "action"),
    [
        ("approved", "approve"),
        ("approved", "reject"),
        ("rejected", "approve"),
        ("rejected", "reject"),
    ],
)
def test_non_pending_approval_returns_409(
    api_client,
    initial_status,
    action,
):
    client, session_factory = api_client
    approval_id = create_approval(
        session_factory,
        status=initial_status,
    )

    response = client.post(
        f"/approvals/{approval_id}/{action}"
    )

    assert response.status_code == 409
    assert "only pending approvals" in response.json()["detail"]


@pytest.mark.parametrize("action", ["approve", "reject"])
def test_missing_approval_returns_404(api_client, action):
    client, _ = api_client

    response = client.post(
        f"/approvals/99999/{action}"
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Approval not found"
