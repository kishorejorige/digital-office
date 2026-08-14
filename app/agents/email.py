from sqlalchemy.orm import Session

from app.models import Approval, Lead
from app.tools.email_tools import build_proposal_draft


def create_proposal_for_lead(
    lead_id: int,
    db: Session,
) -> Approval | None:
    lead = (
        db.query(Lead)
        .filter(Lead.id == lead_id)
        .first()
    )

    if lead is None:
        return None

    draft = build_proposal_draft(
        title=lead.title,
        description=lead.description,
    )

    approval = Approval(
        lead_id=lead.id,
        approval_type="proposal",
        draft=draft,
        status="pending",
    )

    db.add(approval)
    db.commit()
    db.refresh(approval)

    return approval