from hashlib import sha256

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import (
    Base,
    _enable_sqlite_foreign_keys,
)
from app.memory.vectors import encode_vector
from app.models import Memory, MemoryEmbedding


@pytest.fixture
def fk_engine():
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    event.listen(
        test_engine,
        "connect",
        _enable_sqlite_foreign_keys,
    )
    Base.metadata.create_all(bind=test_engine)

    try:
        yield test_engine
    finally:
        Base.metadata.drop_all(bind=test_engine)
        test_engine.dispose()


@pytest.fixture
def fk_session(fk_engine):
    session_factory = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=fk_engine,
    )
    session = session_factory()

    try:
        yield session
    finally:
        session.close()


def test_isolated_sqlite_connections_enable_foreign_keys(fk_engine):
    with fk_engine.connect() as connection:
        enabled = connection.exec_driver_sql(
            "PRAGMA foreign_keys",
        ).scalar_one()

    assert enabled == 1


def test_isolated_sqlite_connection_rejects_orphaned_embedding(fk_session):
    embedding = MemoryEmbedding(
        memory_id=999,
        model="test-model",
        dimension=1,
        vector=encode_vector([1.0]),
        vector_norm=1.0,
    )
    fk_session.add(embedding)

    with pytest.raises(IntegrityError):
        fk_session.commit()

    fk_session.rollback()


def test_deleting_memory_cascades_to_embedding(fk_session):
    content = "cascade test"
    memory = Memory(
        content=content,
        content_hash=sha256(content.encode("utf-8")).hexdigest(),
    )
    fk_session.add(memory)
    fk_session.flush()

    embedding = MemoryEmbedding(
        memory_id=memory.id,
        model="test-model",
        dimension=1,
        vector=encode_vector([1.0]),
        vector_norm=1.0,
    )
    fk_session.add(embedding)
    fk_session.commit()

    fk_session.delete(memory)
    fk_session.commit()

    remaining = fk_session.execute(
        select(MemoryEmbedding),
    ).scalars().all()

    assert remaining == []
