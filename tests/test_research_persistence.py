from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.agents.research import run_research_agent
from app.database import Base
from app.models import Lead


def test_research_agent_saves_apply_leads():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    TestingSessionLocal = sessionmaker(
        bind=engine,
    )

    Base.metadata.create_all(bind=engine)

    db = TestingSessionLocal()

    try:
        result = run_research_agent(
            "Find freelance Python automation opportunities",
            db=db,
        )

        leads = db.query(Lead).all()

        assert result["saved_leads"] == 3
        assert len(leads) == 3

    finally:
        db.close()