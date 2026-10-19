from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.agents.research import run_research_agent
from app.database import Base, get_db
from app.main import app


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
