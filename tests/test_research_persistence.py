from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.agents.research import run_research_agent
from app.database import Base
from app.models import Lead


def create_test_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    TestingSessionLocal = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)

    return engine, TestingSessionLocal()


def test_research_agent_saves_apply_leads_and_skips_repeat_runs():
    engine, db = create_test_session()

    try:
        task = "Find freelance Python automation opportunities"

        first_result = run_research_agent(task, db=db)
        assert first_result["saved_leads"] == 3
        assert db.query(Lead).count() == 3

        second_result = run_research_agent(task, db=db)
        assert second_result["saved_leads"] == 0
        assert db.query(Lead).count() == 3

    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_same_title_with_different_urls_is_not_a_duplicate():
    engine, db = create_test_session()

    try:
        db.add(
            Lead(
                source="Research Agent",
                title="Python Automation Developer",
                url="https://example.com/opportunity-1",
                budget="$150",
                fit_score=100,
                payment_score=60,
                decision="APPLY",
            )
        )
        db.commit()

        result = run_research_agent(
            "Find freelance Python automation opportunities",
            db=db,
        )

        assert result["saved_leads"] == 3
        assert db.query(Lead).count() == 4

    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_same_title_without_urls_is_treated_as_duplicate():
    engine, db = create_test_session()

    try:
        db.add(
            Lead(
                source="Research Agent",
                title="Python Automation Developer",
                budget="$150",
                fit_score=100,
                payment_score=60,
                decision="APPLY",
            )
        )
        db.commit()

        result = run_research_agent(
            "Find freelance Python automation opportunities",
            db=db,
        )

        assert result["saved_leads"] == 2
        assert db.query(Lead).count() == 3

    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
