from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.agents.email import create_proposal_for_lead
from app.agents.research import run_research_agent
from app.approvals import approve_item, reject_item
from app.database import Base, get_db
from app.main import app
from app.models import Approval, Lead


@pytest.fixture
def test_db():
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

    try:
        with TestingSessionLocal() as db:
            yield db
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


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
        with TestingSessionLocal() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_research_agent_rolls_back_when_commit_fails(test_db):
    with (
        patch.object(
            test_db,
            "commit",
            side_effect=RuntimeError("database failure"),
        ),
        patch.object(test_db, "rollback") as rollback,
        pytest.raises(RuntimeError, match="database failure"),
    ):
        run_research_agent(
            "Find freelance Python automation opportunities",
            db=test_db,
        )

    rollback.assert_called_once()


def test_create_lead_returns_generic_error_when_commit_fails(api_client):
    with (
        patch(
            "sqlalchemy.orm.Session.commit",
            side_effect=SQLAlchemyError("database failure"),
        ),
        patch("sqlalchemy.orm.Session.rollback") as rollback,
    ):
        response = api_client.post(
            "/leads",
            json={
                "source": "Manual",
                "title": "Validation test lead",
            },
        )

    assert response.status_code == 500
    assert "database failure" not in response.text.lower()
    rollback.assert_called_once()

def test_proposal_creation_rolls_back_when_commit_fails(test_db):
    lead = Lead(
        source="Manual",
        title="Test proposal lead",
    )
    test_db.add(lead)
    test_db.commit()
    test_db.refresh(lead)

    with (
        patch.object(
            test_db,
            "commit",
            side_effect=SQLAlchemyError("database failure"),
        ),
        patch.object(test_db, "rollback") as rollback,
        pytest.raises(SQLAlchemyError, match="database failure"),
    ):
        create_proposal_for_lead(lead.id, test_db)

    rollback.assert_called_once()


@pytest.mark.parametrize(
    "action",
    [approve_item, reject_item],
    ids=["approve", "reject"],
)
def test_approval_transition_rolls_back_when_commit_fails(
    test_db,
    action,
):
    lead = Lead(
        source="Manual",
        title="Test approval lead",
    )
    test_db.add(lead)
    test_db.commit()
    test_db.refresh(lead)

    approval = Approval(
        lead_id=lead.id,
        approval_type="proposal",
        draft="Test proposal",
        status="pending",
    )
    test_db.add(approval)
    test_db.commit()
    test_db.refresh(approval)

    with (
        patch.object(
            test_db,
            "commit",
            side_effect=SQLAlchemyError("database failure"),
        ),
        patch.object(test_db, "rollback") as rollback,
        pytest.raises(SQLAlchemyError, match="database failure"),
    ):
        action(approval.id, test_db)

    rollback.assert_called_once()


def test_proposal_endpoint_returns_generic_error_when_commit_fails(
    api_client,
):
    lead_response = api_client.post(
        "/leads",
        json={
            "source": "Manual",
            "title": "Proposal failure test",
        },
    )
    assert lead_response.status_code == 200
    lead_id = lead_response.json()["id"]

    with (
        patch(
            "sqlalchemy.orm.Session.commit",
            side_effect=SQLAlchemyError("database failure"),
        ),
        patch("sqlalchemy.orm.Session.rollback") as rollback,
    ):
        response = api_client.post(
            f"/leads/{lead_id}/proposal"
        )

    assert response.status_code == 500
    assert "database failure" not in response.text.lower()
    rollback.assert_called_once()


@pytest.mark.parametrize(
    "action",
    ["approve", "reject"],
    ids=["approve", "reject"],
)
def test_approval_endpoint_returns_generic_error_when_commit_fails(
    api_client,
    action,
):
    lead_response = api_client.post(
        "/leads",
        json={
            "source": "Manual",
            "title": "Approval failure test",
        },
    )
    assert lead_response.status_code == 200
    lead_id = lead_response.json()["id"]

    proposal_response = api_client.post(
        f"/leads/{lead_id}/proposal"
    )
    assert proposal_response.status_code == 200
    approval_id = proposal_response.json()["id"]

    with (
        patch(
            "sqlalchemy.orm.Session.commit",
            side_effect=SQLAlchemyError("database failure"),
        ),
        patch("sqlalchemy.orm.Session.rollback") as rollback,
    ):
        response = api_client.post(
            f"/approvals/{approval_id}/{action}"
        )

    assert response.status_code == 500
    assert "database failure" not in response.text.lower()
    rollback.assert_called_once()