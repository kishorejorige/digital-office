from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _utc_now() -> datetime:
    return datetime.now(UTC)


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


class Memory(Base):
    __tablename__ = "memories"
    __table_args__ = (
        Index(
            "ux_memories_owner_hash",
            "owner_id",
            "content_hash",
            unique=True,
        ),
        Index(
            "ix_memories_owner_archived",
            "owner_id",
            "archived_at",
        ),
        Index(
            "ix_memories_owner_source",
            "owner_id",
            "source",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    owner_id: Mapped[str] = mapped_column(
        String(64),
        default="local",
    )

    title: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
    )

    content: Mapped[str] = mapped_column(Text)

    content_hash: Mapped[str] = mapped_column(String(64))

    source: Mapped[str] = mapped_column(
        String(100),
        default="manual",
    )

    tags_json: Mapped[str] = mapped_column(
        Text,
        default="[]",
    )

    importance: Mapped[int] = mapped_column(
        Integer,
        default=50,
    )

    metadata_json: Mapped[str] = mapped_column(
        Text,
        default="{}",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utc_now,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utc_now,
        onupdate=_utc_now,
    )

    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


class MemoryEmbedding(Base):
    __tablename__ = "memory_embeddings"
    __table_args__ = (
        UniqueConstraint(
            "memory_id",
            "model",
            name="ux_memory_embeddings_memory_model",
        ),
        Index(
            "ix_memory_embeddings_model_dim",
            "model",
            "dimension",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    memory_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("memories.id", ondelete="CASCADE"),
        nullable=False,
    )

    model: Mapped[str] = mapped_column(String(100))

    dimension: Mapped[int] = mapped_column(Integer)

    vector: Mapped[bytes] = mapped_column(LargeBinary)

    vector_norm: Mapped[float] = mapped_column(Float)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utc_now,
    )