from fastapi import Depends, FastAPI
from sqlalchemy.orm import Session

from app.agents.research import run_research_agent
from app.database import Base, engine, get_db
from app.graph import route_task
from app.models import Lead
from app.state import LeadCreate, LeadResponse, TaskRequest


Base.metadata.create_all(bind=engine)


app = FastAPI(
    title="Digital Office",
    version="0.3.0",
)


@app.get("/")
def home():
    return {
        "app": "Digital Office",
        "status": "running",
        "version": "0.3.0",
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