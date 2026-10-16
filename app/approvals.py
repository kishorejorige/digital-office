
from sqlalchemy.orm import Session

from app.models import Approval


class InvalidApprovalStateError(ValueError):
    """Raised when an approval is not pending."""


def list_pending_approvals(
    db: Session,
) -> list[Approval]:
    return (
        db.query(Approval)
        .filter(Approval.status == "pending")
        .all()
    )


def _get_approval(
    approval_id: int,
    db: Session,
) -> Approval | None:
    return (
        db.query(Approval)
        .filter(Approval.id == approval_id)
        .first()
    )


def _require_pending(
    approval: Approval,
) -> None:
    if approval.status != "pending":
        raise InvalidApprovalStateError(
            f"Approval {approval.id} is already "
            f"{approval.status}; only pending approvals "
            "can be changed."
        )


def approve_item(
    approval_id: int,
    db: Session,
) -> Approval | None:
    approval = _get_approval(approval_id, db)

    if approval is None:
        return None

    _require_pending(approval)

    approval.status = "approved"
    db.commit()
    db.refresh(approval)

    return approval


def reject_item(
    approval_id: int,
    db: Session,
) -> Approval | None:
    approval = _get_approval(approval_id, db)

    if approval is None:
        return None

    _require_pending(approval)

    approval.status = "rejected"
    db.commit()
    db.refresh(approval)

    return approval
