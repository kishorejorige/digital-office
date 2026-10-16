from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints

RouteType = Literal["research", "email", "calendar", "unknown"]

NonBlankString = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
    ),
]


class TaskRequest(BaseModel):
    task: Annotated[
        NonBlankString,
        Field(max_length=2000),
    ]


class TaskState(BaseModel):
    task: str
    route: RouteType
    status: str = "accepted"


class LeadCreate(BaseModel):
    name: str | None = None
    source: NonBlankString
    title: NonBlankString
    description: str | None = None
    url: str | None = None
    budget: str | None = None
    fit_score: int = Field(default=0, ge=0, le=100)
    payment_score: int = Field(default=0, ge=0, le=100)
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


class ApprovalResponse(BaseModel):
    id: int
    lead_id: int
    approval_type: str
    draft: str
    status: str

    model_config = {
        "from_attributes": True,
    }
