from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    name: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )

    source: Mapped[str] = mapped_column(String)

    title: Mapped[str] = mapped_column(String)

    description: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )

    url: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )

    budget: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )

    fit_score: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    payment_score: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    decision: Mapped[str] = mapped_column(
        String,
        default="MAYBE",
    )

    status: Mapped[str] = mapped_column(
        String,
        default="new",
    )

    contacted: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    replied: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    earned_amount: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

class Approval(Base):
    __tablename__ = "approvals"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    lead_id: Mapped[int] = mapped_column(
        Integer,
        index=True,
    )

    approval_type: Mapped[str] = mapped_column(
        String,
        default="proposal",
    )

    draft: Mapped[str] = mapped_column(String)

    status: Mapped[str] = mapped_column(
        String,
        default="pending",
    )