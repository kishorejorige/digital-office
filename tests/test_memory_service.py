import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.memory.embeddings import EmbeddingResult
from app.memory.schemas import MemoryCreate, MemoryUpdate
from app.memory.service import (
    MemoryDuplicateError,
    MemoryEmbeddingUnavailableError,
    MemoryInvalidEmbeddingResponseError,
    MemoryNotFoundError,
    archive_memory,
    create_memory,
    delete_memory,
    get_memory,
    list_memories,
    restore_memory,
    update_memory,
)
from app.models import Memory, MemoryEmbedding


class FakeEmbeddingClient:
    def __init__(self, vector=None, raise_exc=None, calls=None):
        self.vector = vector if vector is not None else [0.1, 0.2, 0.3]
        self.raise_exc = raise_exc
        self.calls = calls if calls is not None else []

    def embed(self, text: str) -> EmbeddingResult:
        self.calls.append(text)
        if self.raise_exc:
            raise self.raise_exc
        return EmbeddingResult(
            vector=tuple(self.vector),
            model="nomic-embed-text:latest",
            dimension=len(self.vector),
        )


@pytest.fixture
def db_session():
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
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_create_persists_original_content_and_embedding_atomically(db_session):
    client = FakeEmbeddingClient()
    data = MemoryCreate(content="  Hello\nWorld  ")
    result = create_memory(db_session, data, client, owner_id="local")

    assert result.content == "  Hello\nWorld  "  # Original preserved
    assert result.id is not None

    memory = db_session.execute(select(Memory)).scalars().first()
    assert memory.content == "  Hello\nWorld  "
    embedding = db_session.execute(select(MemoryEmbedding)).scalars().first()
    assert embedding is not None
    assert embedding.memory_id == memory.id
    assert embedding.dimension == 3


def test_exact_normalized_duplicate_conflict(db_session):
    client = FakeEmbeddingClient()
    data1 = MemoryCreate(content="Hello World")
    create_memory(db_session, data1, client)

    data2 = MemoryCreate(content="hello   world")  # Different case/whitespace
    with pytest.raises(MemoryDuplicateError):
        create_memory(db_session, data2, client)


def test_distinct_owners_can_have_identical_content(db_session):
    client = FakeEmbeddingClient()
    data = MemoryCreate(content="Same content")
    r1 = create_memory(db_session, data, client, owner_id="owner1")
    r2 = create_memory(db_session, data, client, owner_id="owner2")
    assert r1.id != r2.id


def test_get_list_and_pagination(db_session):
    client = FakeEmbeddingClient()
    for i in range(5):
        create_memory(db_session, MemoryCreate(content=f"Content {i}"), client)

    r = get_memory(db_session, 1)
    assert r.id == 1

    items, total = list_memories(db_session, limit=2, offset=0)
    assert len(items) == 2
    assert total == 5

    items2, _total2 = list_memories(db_session, limit=2, offset=2)
    assert len(items2) == 2


def test_tag_filter_matches_exact_tag_not_substring(db_session):
    client = FakeEmbeddingClient()

    create_memory(
        db_session,
        MemoryCreate(content="Python memory", tags=["python"]),
        client,
    )
    create_memory(
        db_session,
        MemoryCreate(content="Python automation memory", tags=["python-automation"]),
        client,
    )

    items, total = list_memories(db_session, tags=["python"])

    assert total == 1
    assert len(items) == 1
    assert items[0].content == "Python memory"


def test_tag_filtered_listing_paginates_matching_records_correctly(db_session):
    client = FakeEmbeddingClient()

    create_memory(
        db_session,
        MemoryCreate(content="Untagged first"),
        client,
    )
    create_memory(
        db_session,
        MemoryCreate(content="Tagged second", tags=["target"]),
        client,
    )
    create_memory(
        db_session,
        MemoryCreate(content="Untagged third"),
        client,
    )
    create_memory(
        db_session,
        MemoryCreate(content="Tagged fourth", tags=["target"]),
        client,
    )

    items, total = list_memories(
        db_session,
        tags=["target"],
        limit=1,
        offset=1,
    )

    assert total == 2
    assert len(items) == 1
    assert items[0].content == "Tagged fourth"


def test_tag_filter_is_case_sensitive(db_session):
    client = FakeEmbeddingClient()

    create_memory(
        db_session,
        MemoryCreate(content="Lowercase tag", tags=["python"]),
        client,
    )
    create_memory(
        db_session,
        MemoryCreate(content="Uppercase tag", tags=["Python"]),
        client,
    )

    lower_items, lower_total = list_memories(db_session, tags=["python"])
    upper_items, upper_total = list_memories(db_session, tags=["Python"])

    assert lower_total == 1
    assert [item.content for item in lower_items] == ["Lowercase tag"]
    assert upper_total == 1
    assert [item.content for item in upper_items] == ["Uppercase tag"]


def test_tag_filter_matches_quotes_and_backslashes(db_session):
    client = FakeEmbeddingClient()

    create_memory(
        db_session,
        MemoryCreate(content="Quoted tag", tags=['say "hello"']),
        client,
    )
    create_memory(
        db_session,
        MemoryCreate(content="Backslash tag", tags=[r"C:\temp\notes"]),
        client,
    )
    create_memory(
        db_session,
        MemoryCreate(content="Decoy tags", tags=["say hello", "C:tempnotes"]),
        client,
    )

    quoted_items, quoted_total = list_memories(db_session, tags=['say "hello"'])
    backslash_items, backslash_total = list_memories(
        db_session,
        tags=[r"C:\temp\notes"],
    )

    assert quoted_total == 1
    assert [item.content for item in quoted_items] == ["Quoted tag"]
    assert backslash_total == 1
    assert [item.content for item in backslash_items] == ["Backslash tag"]


def test_tag_filter_treats_percent_and_underscore_literally(db_session):
    client = FakeEmbeddingClient()

    create_memory(
        db_session,
        MemoryCreate(content="Literal percent", tags=["100%"]),
        client,
    )
    create_memory(
        db_session,
        MemoryCreate(content="Literal underscore", tags=["a_b"]),
        client,
    )
    create_memory(
        db_session,
        MemoryCreate(content="Wildcard decoys", tags=["1000", "axb"]),
        client,
    )

    percent_items, percent_total = list_memories(db_session, tags=["100%"])
    underscore_items, underscore_total = list_memories(db_session, tags=["a_b"])

    assert percent_total == 1
    assert [item.content for item in percent_items] == ["Literal percent"]
    assert underscore_total == 1
    assert [item.content for item in underscore_items] == ["Literal underscore"]


def test_tag_filter_requires_all_supplied_tags(db_session):
    client = FakeEmbeddingClient()

    create_memory(
        db_session,
        MemoryCreate(content="Both tags", tags=["alpha", "beta"]),
        client,
    )
    create_memory(
        db_session,
        MemoryCreate(content="Alpha only", tags=["alpha"]),
        client,
    )
    create_memory(
        db_session,
        MemoryCreate(content="Beta only", tags=["beta"]),
        client,
    )

    items, total = list_memories(db_session, tags=["alpha", "beta"])

    assert total == 1
    assert [item.content for item in items] == ["Both tags"]


def test_tag_filter_counts_and_paginates_only_matching_records(db_session):
    client = FakeEmbeddingClient()

    create_memory(db_session, MemoryCreate(content="Nonmatch one"), client)
    create_memory(
        db_session,
        MemoryCreate(content="Match one", tags=["target"]),
        client,
    )
    create_memory(
        db_session,
        MemoryCreate(content="Nonmatch two", tags=["other"]),
        client,
    )
    create_memory(
        db_session,
        MemoryCreate(content="Match two", tags=["target", "extra"]),
        client,
    )
    create_memory(db_session, MemoryCreate(content="Nonmatch three"), client)
    create_memory(
        db_session,
        MemoryCreate(content="Match three", tags=["target"]),
        client,
    )

    items, total = list_memories(
        db_session,
        tags=["target"],
        limit=1,
        offset=1,
    )

    assert total == 3
    assert [item.content for item in items] == ["Match two"]


def test_metadata_only_update_makes_no_embedding_call(db_session):
    client = FakeEmbeddingClient()
    create_memory(db_session, MemoryCreate(content="Test content"), client)
    calls_before = len(client.calls)

    update_memory(
        db_session,
        1,
        MemoryUpdate(importance=75, tags=["tag1"]),
        client,
    )
    assert len(client.calls) == calls_before


def test_content_update_regenerates_embedding_and_updates_hash_timestamp(db_session):
    client = FakeEmbeddingClient([0.1, 0.2])
    create_memory(db_session, MemoryCreate(content="Original"), client)
    old_mem = db_session.execute(select(Memory)).scalars().first()
    old_hash = old_mem.content_hash
    old_updated = old_mem.updated_at

    client2 = FakeEmbeddingClient([0.3, 0.4])
    result = update_memory(
        db_session,
        1,
        MemoryUpdate(content="Updated content"),
        client2,
    )
    assert result.content == "Updated content"
    assert len(client2.calls) == 1
    mem = db_session.execute(select(Memory)).scalars().first()
    assert mem.content_hash != old_hash
    assert mem.updated_at >= old_updated
    emb = db_session.execute(select(MemoryEmbedding)).scalars().first()
    assert emb.dimension == 2


def test_duplicate_content_update_fails_without_corrupting_old_record(db_session):
    client = FakeEmbeddingClient()
    create_memory(db_session, MemoryCreate(content="Content A"), client)
    create_memory(db_session, MemoryCreate(content="Content B"), client)

    with pytest.raises(MemoryDuplicateError):
        update_memory(
            db_session,
            2,
            MemoryUpdate(content="content a"),  # duplicate of first
            client,
        )
    mem = db_session.get(Memory, 2)
    assert mem.content == "Content B"


def test_update_flush_constraint_failure_rolls_back_and_preserves_old_state(tmp_path):
    engine = create_engine(
        f"sqlite:///{(tmp_path / 'flush-race.db').as_posix()}",
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
    )
    db = session_factory()
    conflicting_db = session_factory()
    try:
        created = create_memory(
            db,
            MemoryCreate(content="Original content"),
            FakeEmbeddingClient([0.1, 0.2, 0.3]),
        )
        original = db.get(Memory, created.id)
        old_hash = original.content_hash
        old_embedding = db.execute(
            select(MemoryEmbedding).where(
                MemoryEmbedding.memory_id == created.id,
            ),
        ).scalars().one()
        old_embedding_id = old_embedding.id
        old_embedding_vector = old_embedding.vector

        racy_content = "Racy content"

        class RacingEmbeddingClient:
            def embed(self, text: str) -> EmbeddingResult:
                assert text == racy_content
                create_memory(
                    conflicting_db,
                    MemoryCreate(content=racy_content),
                    FakeEmbeddingClient([0.4, 0.5, 0.6]),
                )
                return EmbeddingResult(
                    vector=(0.7, 0.8, 0.9),
                    model="nomic-embed-text:latest",
                    dimension=3,
                )

        with pytest.raises(MemoryDuplicateError):
            update_memory(
                db,
                created.id,
                MemoryUpdate(content=racy_content),
                RacingEmbeddingClient(),
            )

        db.expire_all()
        memory = db.get(Memory, created.id)
        assert memory.content == "Original content"
        assert memory.content_hash == old_hash

        embeddings = db.execute(
            select(MemoryEmbedding).where(
                MemoryEmbedding.memory_id == created.id,
            ),
        ).scalars().all()
        assert len(embeddings) == 1
        assert embeddings[0].id == old_embedding_id
        assert embeddings[0].vector == old_embedding_vector

        reused = create_memory(
            db,
            MemoryCreate(content="After failure"),
            FakeEmbeddingClient([0.9, 0.8, 0.7]),
        )
        assert reused.id is not None
    finally:
        db.close()
        conflicting_db.close()
        engine.dispose()


def test_archive_excludes_from_default_listing_restore_makes_available(db_session):
    client = FakeEmbeddingClient()
    create_memory(db_session, MemoryCreate(content="Test"), client)

    _items, total = list_memories(db_session)
    assert total == 1

    archive_memory(db_session, 1)
    _items_a, total = list_memories(db_session)
    assert total == 0
    _items_b, total = list_memories(db_session, include_archived=True)
    assert total == 1

    restore_memory(db_session, 1)
    _items_c, total = list_memories(db_session)
    assert total == 1


def test_repeated_archive_restore_behavior(db_session):
    client = FakeEmbeddingClient()
    create_memory(db_session, MemoryCreate(content="Test"), client)

    # Archive already archived is idempotent
    archive_memory(db_session, 1)
    archive_memory(db_session, 1)  # Should not error
    mem = db_session.get(Memory, 1)
    assert mem.archived_at is not None

    # Restore already active is idempotent
    restore_memory(db_session, 1)
    restore_memory(db_session, 1)  # Should not error
    mem = db_session.get(Memory, 1)
    assert mem.archived_at is None


def test_delete_removes_memory_and_associated_embeddings(db_session):
    client = FakeEmbeddingClient()
    create_memory(db_session, MemoryCreate(content="To delete"), client)
    assert db_session.execute(select(Memory)).scalars().first() is not None
    assert db_session.execute(select(MemoryEmbedding)).scalars().first() is not None

    delete_memory(db_session, 1)
    assert db_session.execute(select(Memory)).scalars().first() is None
    assert db_session.execute(select(MemoryEmbedding)).scalars().first() is None


def test_owner_isolation_across_all_operations(db_session):
    client = FakeEmbeddingClient()
    create_memory(db_session, MemoryCreate(content="Owner1 content"), client, owner_id="owner1")
    create_memory(db_session, MemoryCreate(content="Owner2 content"), client, owner_id="owner2")

    with pytest.raises(MemoryNotFoundError):
        get_memory(db_session, 1, owner_id="owner2")
    with pytest.raises(MemoryNotFoundError):
        update_memory(db_session, 1, MemoryUpdate(importance=10), client, owner_id="owner2")
    with pytest.raises(MemoryNotFoundError):
        archive_memory(db_session, 1, owner_id="owner2")
    with pytest.raises(MemoryNotFoundError):
        delete_memory(db_session, 1, owner_id="owner2")

    items1, total1 = list_memories(db_session, owner_id="owner1")
    items2, total2 = list_memories(db_session, owner_id="owner2")
    assert total1 == 1 and total2 == 1
    assert items1[0].content != items2[0].content


def test_rollback_on_embedding_failure(db_session):
    from app.memory.embeddings import EmbeddingServiceUnavailableError

    client = FakeEmbeddingClient(raise_exc=EmbeddingServiceUnavailableError("fail"))
    with pytest.raises(MemoryEmbeddingUnavailableError):
        create_memory(db_session, MemoryCreate(content="Test"), client)
    assert db_session.execute(select(Memory)).scalars().first() is None
    assert db_session.execute(select(MemoryEmbedding)).scalars().first() is None


@pytest.mark.parametrize(
    "vector",
    [
        [10**100],
        [10**400],
        [1e39],
        [1e300],
    ],
    ids=[
        "huge-integer",
        "integer-beyond-float",
        "float32-overflow",
        "huge-float",
    ],
)
def test_invalid_float32_embedding_is_rejected_without_persistence(
    db_session,
    vector,
):
    client = FakeEmbeddingClient(vector)

    with pytest.raises(MemoryInvalidEmbeddingResponseError):
        create_memory(db_session, MemoryCreate(content="Test"), client)

    assert db_session.execute(select(Memory)).scalars().first() is None
    assert db_session.execute(select(MemoryEmbedding)).scalars().first() is None


def test_create_rolls_back_when_commit_fails(db_session, monkeypatch):
    client = FakeEmbeddingClient()

    def fail_commit():
        raise SQLAlchemyError("commit failed")

    monkeypatch.setattr(db_session, "commit", fail_commit)

    with pytest.raises(SQLAlchemyError, match="commit failed"):
        create_memory(db_session, MemoryCreate(content="Test"), client)

    assert db_session.execute(select(Memory)).scalars().first() is None
    assert db_session.execute(select(MemoryEmbedding)).scalars().first() is None


def test_update_rolls_back_content_and_embedding_when_commit_fails(
    db_session,
    monkeypatch,
):
    memory = create_memory(
        db_session,
        MemoryCreate(content="Original"),
        FakeEmbeddingClient(),
    )
    memory_id = memory.id
    memory_row = db_session.get(Memory, memory_id)
    original_hash = memory_row.content_hash
    original_updated_at = memory_row.updated_at
    original_embedding = db_session.execute(select(MemoryEmbedding)).scalar_one()
    original_vector = original_embedding.vector

    def fail_commit():
        raise SQLAlchemyError("commit failed")

    monkeypatch.setattr(db_session, "commit", fail_commit)

    with pytest.raises(SQLAlchemyError, match="commit failed"):
        update_memory(
            db_session,
            memory_id,
            MemoryUpdate(content="Updated"),
            FakeEmbeddingClient([0.4, 0.5, 0.6]),
        )

    db_session.expire_all()
    stored_memory = db_session.get(Memory, memory_id)
    assert stored_memory.content == "Original"
    assert stored_memory.content_hash == original_hash
    assert stored_memory.updated_at == original_updated_at

    embeddings = db_session.execute(select(MemoryEmbedding)).scalars().all()
    assert len(embeddings) == 1
    assert embeddings[0].memory_id == memory_id
    assert embeddings[0].vector == original_vector


def test_duplicate_precheck_rejects_without_creating_second_memory(db_session):
    client = FakeEmbeddingClient()
    create_memory(db_session, MemoryCreate(content="Test"), client)

    with pytest.raises(MemoryDuplicateError):
        create_memory(db_session, MemoryCreate(content="test"), client)

    memories = db_session.execute(select(Memory)).scalars().all()
    embeddings = db_session.execute(select(MemoryEmbedding)).scalars().all()
    assert len(memories) == 1
    assert len(embeddings) == 1
    assert memories[0].content == "Test"


@pytest.mark.parametrize(
    "metadata",
    [
        {"bad": object()},
        {"data": "x" * 5000},
    ],
    ids=["non-json-serializable", "oversized"],
)
def test_invalid_metadata_is_rejected_by_schema(metadata):
    with pytest.raises(ValidationError):
        MemoryCreate(content="Test", metadata=metadata)


def test_blank_content_is_rejected_by_schema():
    with pytest.raises(ValidationError):
        MemoryCreate(content="")
