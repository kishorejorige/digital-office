import struct
from hashlib import sha256

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import Memory, MemoryEmbedding


@pytest.fixture
def memory_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    Base.metadata.create_all(bind=engine)

    session_factory = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
    )
    session = session_factory()

    try:
        yield engine, session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_memory_tables_can_be_created(memory_session):
    engine, _ = memory_session

    table_names = set(inspect(engine).get_table_names())

    assert "memories" in table_names
    assert "memory_embeddings" in table_names


def test_memory_columns(memory_session):
    engine, _ = memory_session

    columns = {
        column["name"]: column
        for column in inspect(engine).get_columns("memories")
    }

    assert set(columns) == {
        "id",
        "owner_id",
        "title",
        "content",
        "content_hash",
        "source",
        "tags_json",
        "importance",
        "metadata_json",
        "created_at",
        "updated_at",
        "archived_at",
    }
    assert columns["content"]["nullable"] is False
    assert columns["title"]["nullable"] is True
    assert columns["archived_at"]["nullable"] is True


def test_memory_embedding_columns(memory_session):
    engine, _ = memory_session

    columns = {
        column["name"]: column
        for column in inspect(engine).get_columns("memory_embeddings")
    }

    assert set(columns) == {
        "id",
        "memory_id",
        "model",
        "dimension",
        "vector",
        "vector_norm",
        "created_at",
    }
    assert columns["memory_id"]["nullable"] is False
    assert columns["vector"]["nullable"] is False


def test_memory_indexes(memory_session):
    engine, _ = memory_session

    indexes = {
        index["name"]: index
        for index in inspect(engine).get_indexes("memories")
    }

    owner_hash = indexes["ux_memories_owner_hash"]
    assert owner_hash["unique"]
    assert owner_hash["column_names"] == [
        "owner_id",
        "content_hash",
    ]

    assert indexes["ix_memories_owner_archived"]["column_names"] == [
        "owner_id",
        "archived_at",
    ]
    assert indexes["ix_memories_owner_source"]["column_names"] == [
        "owner_id",
        "source",
    ]


def test_memory_embedding_unique_constraint_and_index(memory_session):
    engine, _ = memory_session

    constraints = inspect(engine).get_unique_constraints(
        "memory_embeddings",
    )

    assert any(
        constraint["name"] == "ux_memory_embeddings_memory_model"
        and constraint["column_names"] == ["memory_id", "model"]
        for constraint in constraints
    )

    indexes = {
        index["name"]: index
        for index in inspect(engine).get_indexes("memory_embeddings")
    }

    assert indexes["ix_memory_embeddings_model_dim"]["column_names"] == [
        "model",
        "dimension",
    ]


def test_memory_embedding_foreign_key_declares_cascade(memory_session):
    engine, _ = memory_session

    foreign_keys = inspect(engine).get_foreign_keys("memory_embeddings")

    assert any(
        foreign_key["referred_table"] == "memories"
        and foreign_key["constrained_columns"] == ["memory_id"]
        and foreign_key["referred_columns"] == ["id"]
        for foreign_key in foreign_keys
    )

    declared = next(iter(MemoryEmbedding.__table__.foreign_keys))
    assert declared.target_fullname == "memories.id"
    assert declared.ondelete == "CASCADE"


def test_memory_and_embedding_persist(memory_session):
    _, session = memory_session

    original_content = "  Preserve this exactly.\n"
    memory = Memory(
        content=original_content,
        content_hash=sha256(
            original_content.encode("utf-8"),
        ).hexdigest(),
    )

    session.add(memory)
    session.commit()
    session.refresh(memory)

    assert memory.id is not None
    assert memory.owner_id == "local"
    assert memory.source == "manual"
    assert memory.tags_json == "[]"
    assert memory.importance == 50
    assert memory.metadata_json == "{}"
    assert memory.created_at is not None
    assert memory.updated_at is not None
    assert memory.archived_at is None
    assert memory.content == original_content

    vector = struct.pack("<3f", 1.0, 0.0, 0.0)
    embedding = MemoryEmbedding(
        memory_id=memory.id,
        model="test-model",
        dimension=3,
        vector=vector,
        vector_norm=1.0,
    )

    session.add(embedding)
    session.commit()
    session.refresh(embedding)

    assert embedding.id is not None
    assert embedding.memory_id == memory.id
    assert embedding.model == "test-model"
    assert embedding.dimension == 3
    assert embedding.vector == vector
    assert embedding.vector_norm == pytest.approx(1.0)
    assert embedding.created_at is not None


def test_duplicate_owner_hash_is_rejected(memory_session):
    _, session = memory_session

    content = "duplicate content"
    digest = sha256(content.encode("utf-8")).hexdigest()

    session.add_all(
        [
            Memory(content=content, content_hash=digest),
            Memory(content=content, content_hash=digest),
        ]
    )

    with pytest.raises(IntegrityError):
        session.commit()

    session.rollback()
