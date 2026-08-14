from typing import Literal

from pydantic import BaseModel


RouteType = Literal["research", "email", "calendar", "unknown"]


class TaskRequest(BaseModel):
    task: str


class TaskState(BaseModel):
    task: str
    route: RouteType
    status: str = "accepted"

class LeadCreate(BaseModel):
    name: str | None = None
    source: str
    title: str
    description: str | None = None
    url: str | None = None
    budget: str | None = None
    fit_score: int = 0
    payment_score: int = 0
    decision: str = "MAYBE"

class LeadResponse(LeadCreate):
    id: int
    status: str
    contacted: bool
    replied: bool
    earned_amount: int

    model_config = {
        "from_attributes": True,
    }