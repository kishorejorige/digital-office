from sqlalchemy.orm import Session

from app.models import Approval


def list_pending_approvals(
    db: Session,
) -> list[Approval]:
    return (
        db.query(Approval)
        .filter(Approval.status == "pending")
        .all()
    )


def approve_item(
    approval_id: int,
    db: Session,
) -> Approval | None:
    approval = (
        db.query(Approval)
        .filter(Approval.id == approval_id)
        .first()
    )

    if approval is None:
        return None

    approval.status = "approved"

    db.commit()
    db.refresh(approval)

    return approval


def reject_item(
    approval_id: int,
    db: Session,
) -> Approval | None:
    approval = (
        db.query(Approval)
        .filter(Approval.id == approval_id)
        .first()
    )

    if approval is None:
        return None

    approval.status = "rejected"

    db.commit()
    db.refresh(approval)

    return approval