from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.orm import Session

from app.agents.email import create_proposal_for_lead
from app.agents.research import run_research_agent
from app.approvals import (
    InvalidApprovalStateError,
    approve_item,
    list_pending_approvals,
    reject_item,
)
from app.database import Base, engine, get_db
from app.graph import route_task
from app.models import Lead
from app.state import ApprovalResponse, LeadCreate, LeadResponse, TaskRequest

Base.metadata.create_all(bind=engine)


app = FastAPI(
    title="Digital Office",
    version="0.5.0",
)


@app.get("/")
def home():
    return {
        "app": "Digital Office",
        "status": "running",
        "version": "0.5.0",
    }


@app.post("/tasks")
def create_task(
    request: TaskRequest,
    db: Session = Depends(get_db),
):
    route = route_task(request.task)

    if route == "research":
        return run_research_agent(
            request.task,
            db=db,
        )

    return {
        "task": request.task,
        "route": route,
        "status": "accepted",
    }


@app.post(
    "/leads",
    response_model=LeadResponse,
)
def create_lead(
    lead: LeadCreate,
    db: Session = Depends(get_db),
):
    db_lead = Lead(**lead.model_dump())

    db.add(db_lead)
    db.commit()
    db.refresh(db_lead)

    return db_lead


@app.get(
    "/leads",
    response_model=list[LeadResponse],
)
def list_leads(
    db: Session = Depends(get_db),
):
    return db.query(Lead).all()

@app.post(
    "/leads/{lead_id}/proposal",
    response_model=ApprovalResponse,
)
def create_proposal(
    lead_id: int,
    db: Session = Depends(get_db),
):
    approval = create_proposal_for_lead(
        lead_id,
        db,
    )

    if approval is None:
        raise HTTPException(
            status_code=404,
            detail="Lead not found",
        )

    return approval


@app.get(
    "/approvals",
    response_model=list[ApprovalResponse],
)
def get_approvals(
    db: Session = Depends(get_db),
):
    return list_pending_approvals(db)


@app.post(
    "/approvals/{approval_id}/approve",
    response_model=ApprovalResponse,
)
def approve_proposal(
    approval_id: int,
    db: Session = Depends(get_db),
):
    try:
        approval = approve_item(
            approval_id,
            db,
        )
    except InvalidApprovalStateError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc

    if approval is None:
        raise HTTPException(
            status_code=404,
            detail="Approval not found",
        )

    return approval


@app.post(
    "/approvals/{approval_id}/reject",
    response_model=ApprovalResponse,
)
def reject_proposal(
    approval_id: int,
    db: Session = Depends(get_db),
):
    try:
        approval = reject_item(
            approval_id,
            db,
        )
    except InvalidApprovalStateError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc

    if approval is None:
        raise HTTPException(
            status_code=404,
            detail="Approval not found",
        )

    return approval