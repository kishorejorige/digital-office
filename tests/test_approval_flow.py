from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.agents.email import create_proposal_for_lead
from app.approvals import approve_item
from app.database import Base
from app.models import Lead


def test_proposal_approval_flow():
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
        lead = Lead(
            source="Test",
            title="AI RAG Developer",
            budget="$300",
            fit_score=100,
            payment_score=100,
            decision="APPLY",
        )

        db.add(lead)
        db.commit()
        db.refresh(lead)

        approval = create_proposal_for_lead(
            lead.id,
            db,
        )

        assert approval is not None
        assert approval.status == "pending"
        assert approval.lead_id == lead.id

        approved = approve_item(
            approval.id,
            db,
        )

        assert approved is not None
        assert approved.status == "approved"

    finally:
        db.close()