# Digital Office

Digital Office is an AI-assisted personal operations system being built to help manage research, freelance opportunities, leads, proposals, approvals, and eventually email and calendar workflows.

Current version: v0.6.0
Development milestone: v0.6 — Safety & Reliability

## Overview

This project is a lightweight FastAPI-based prototype for building an operational workflow around personal business development. It currently handles:

- FastAPI backend
- Task routing
- Research Agent
- Opportunity fit scoring
- Payment scoring
- APPLY / MAYBE / SKIP decisions
- Automatic qualified-lead persistence
- SQLite + SQLAlchemy
- Duplicate protection for research leads
- Email proposal drafting
- Human approval queue
- Approve/reject workflow
- Local semantic memory with Ollama embeddings
- Pytest test suite

This is currently an internal, local-first prototype. Real Gmail and Calendar integrations should not be enabled until security, approval safeguards, and validation are completed.

**Security warning:** the API has no authentication. It defaults to `127.0.0.1` and must not be exposed to untrusted networks, including an untrusted LAN.

## Current architecture

```text
Task → Router → Agent → Tools → Database → Approval

Memory API → Memory service → SQLite + local Ollama embeddings
```

The task flow is intentionally simple:

1. A task is submitted to the API.
2. The router decides whether it is a research, email, or calendar task.
3. A matching agent processes the request.
4. Tools score opportunities and draft proposals.
5. Valid leads are saved to SQLite.
6. Proposals move into a human approval queue.

Memory is a separate feature. It is not wired into task routing, agents, prompts, or tool execution.

## Project structure

```text
.
├── app/
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── email.py
│   │   └── research.py
│   ├── memory/
│   │   ├── __init__.py
│   │   ├── config.py
│   │   ├── embeddings.py
│   │   ├── routes.py
│   │   ├── schemas.py
│   │   ├── service.py
│   │   └── vectors.py
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── email_tools.py
│   │   └── research_tools.py
│   ├── __init__.py
│   ├── approvals.py
│   ├── database.py
│   ├── graph.py
│   ├── main.py
│   ├── models.py
│   └── state.py
├── tests/
│   ├── test_approval_api.py
│   ├── test_approval_flow.py
│   ├── test_database_foreign_keys.py
│   ├── test_error_handling.py
│   ├── test_input_validation.py
│   ├── test_memory_api.py
│   ├── test_memory_embeddings.py
│   ├── test_memory_models.py
│   ├── test_memory_search.py
│   ├── test_memory_service.py
│   ├── test_memory_vectors.py
│   ├── test_research_agent.py
│   ├── test_research_persistence.py
│   └── test_routing.py
├── .python-version
├── main.py
├── pyproject.toml
├── README.md
├── uv.lock
└── .gitignore
```

`digital_office.db` is created locally and is gitignored.

## Local setup with uv

This project uses Python 3.12 and `uv` for dependency management.

### 1) Install dependencies

```bash
uv sync
```

### 2) Prepare local semantic memory (optional)

Memory creation, content-changing updates, and semantic search require a local Ollama instance and the configured embedding model. Metadata-only updates do not require Ollama. Defaults:

- Ollama base URL: `http://127.0.0.1:11434`
- Embedding model: `nomic-embed-text:latest`

For example:

```bash
ollama serve
ollama pull nomic-embed-text:latest
```

Only `http` loopback URLs using `127.0.0.1` or `localhost` are accepted. If Ollama or the model is unavailable, memory creation, content-changing updates, and semantic search requests return HTTP 503. Non-memory endpoints remain usable.

### 3) Run tests and lint

```bash
uv run pytest -q
uv run ruff check app tests --ignore B008
git diff --check
```

Test counts are intentionally not documented here; use the current test output.

### 4) Start the FastAPI app

```bash
uv run uvicorn app.main:app --host 127.0.0.1 --port 8585
```

`127.0.0.1` is the supported local-development binding. The API has no authentication, so do not bind to `0.0.0.0` or expose it to untrusted networks.

### 5) Open Swagger docs

```text
http://localhost:8585/docs
```

## API endpoints

| Method | Endpoint | Description |
| --- | --- | --- |
| GET | `/` | Health check / app info |
| POST | `/tasks` | Submit a task and route it to an agent |
| POST | `/leads` | Create a lead record |
| GET | `/leads` | List saved leads |
| POST | `/leads/{lead_id}/proposal` | Generate a proposal draft for a lead |
| GET | `/approvals` | List pending approval items |
| POST | `/approvals/{approval_id}/approve` | Approve an approval record |
| POST | `/approvals/{approval_id}/reject` | Reject an approval record |
| POST | `/memories` | Create a memory and its local embedding |
| GET | `/memories` | List memories with optional filters |
| GET | `/memories/{memory_id}` | Retrieve one memory |
| PATCH | `/memories/{memory_id}` | Partially update a memory |
| POST | `/memories/{memory_id}/archive` | Archive a memory |
| POST | `/memories/{memory_id}/restore` | Restore an archived memory |
| DELETE | `/memories/{memory_id}` | Delete a memory and its embedding |
| POST | `/memories/search` | Semantic search over compatible embeddings |

## Semantic memory

### Ownership and access

All memory records are scoped to the fixed owner value `owner_id="local"`. API requests cannot select a different owner. This is not authentication and does not provide multi-user isolation.

The API is unauthenticated. Run it only on a trusted local machine.

### Request and response behavior

Memory responses contain `id`, `title`, `content`, `source`, `tags`, `importance`, `metadata`, `created_at`, `updated_at`, and `archived_at`. Embedding vectors and norms are never returned.

**Create:** `POST /memories`

- `content` is required, non-blank, and limited to 10,000 characters.
- `title` is optional and limited to 200 characters.
- `source` is an optional non-blank string up to 100 characters, defaulting to `manual`.
- `tags` is a list of up to 20 non-blank tags, each up to 50 characters.
- `importance` is an integer from 0 to 100, defaulting to 50.
- `metadata` is a JSON object, defaulting to `{}`, limited to 4,096 serialized bytes.
- Normalized duplicate content returns HTTP 409. Normalization applies NFKC, whitespace collapsing, and case folding.
- Successful creation returns HTTP 201.

**List:** `GET /memories`

- `limit` defaults to 20 and must be 1–100.
- `offset` defaults to 0.
- `include_archived` defaults to `false`.
- `source` optionally filters by exact source value.
- `tags` accepts up to 20 repeated tag filters. All supplied tags must be present (AND semantics), matched exactly and case-sensitively. Exact tag filtering requires SQLite JSON1 support and the `json_each()` function.
- `total` is the count after all filters and before pagination.

**Retrieve:** `GET /memories/{memory_id}`

- `include_archived` defaults to `true` for this endpoint.
- Unknown memory IDs return HTTP 404.

**Update:** `PATCH /memories/{memory_id}`

- This is a partial update; omitted fields are unchanged.
- An explicitly supplied `"source": null` is rejected with HTTP 422.
- Updating `content` regenerates the embedding, including when the same content text is supplied. Metadata-only updates do not regenerate embeddings.
- Duplicate content returns HTTP 409; embedding failures return HTTP 503.

**Archive, restore, and delete**

- `POST /memories/{memory_id}/archive` and `POST /memories/{memory_id}/restore` are idempotent.
- `DELETE /memories/{memory_id}` returns HTTP 204 and removes the associated embedding.

**Search:** `POST /memories/search`

- `query` is required and non-blank.
- `top_k` defaults to 10 and must be 1–50.
- `min_score` defaults to 0 and must be between -1 and 1.
- `tags` accepts up to 20 exact filters with AND semantics.
- `source` and `include_archived` behave as in listing.
- Results contain the memory, cosine similarity score, and `trust: "untrusted"`.
- Search compares only stored embeddings whose model matches the model used for the query.

### Embedding configuration

Configuration is read from process environment variables at startup. Changes require a restart. No `.env` loading is implemented.

| Variable | Default | Validation |
| --- | --- | --- |
| `OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | `http` loopback only (`127.0.0.1` or `localhost`); no credentials, query, or fragment; no path other than `/`; port 1–65535 |
| `OLLAMA_EMBEDDING_MODEL` | `nomic-embed-text:latest` | Non-blank string |
| `OLLAMA_CONNECT_TIMEOUT_SECONDS` | `2.0` | Greater than 0 and at most 300 seconds |
| `OLLAMA_READ_TIMEOUT_SECONDS` | `30.0` | Greater than 0 and at most 300 seconds |
| `OLLAMA_WRITE_TIMEOUT_SECONDS` | `10.0` | Greater than 0 and at most 300 seconds |
| `OLLAMA_POOL_TIMEOUT_SECONDS` | `2.0` | Greater than 0 and at most 300 seconds |

Embedding responses must contain exactly one finite vector with no more than 4,096 dimensions. Vectors are stored as float32 values.

### Model changes and re-indexing

Each stored embedding records the model that produced it. Search filters to embeddings created with the model used for the query.

Changing `OLLAMA_EMBEDDING_MODEL` affects new memories and content updates. Existing embeddings are not migrated or re-indexed automatically. A bulk re-index endpoint is not implemented. To re-embed an existing memory, PATCH its `content` (even with the same text) so its embedding is regenerated. Until then, that memory may not appear in searches using the new model. Deleting and recreating a memory also regenerates its embedding.

### Retrieval trust boundary

Search results are untrusted data. The API marks them with `trust: "untrusted"` and does not automatically inject them into LLM prompts, execute them, or treat them as tool instructions. Any future integration must keep retrieved content separated from instructions and require explicit validation.

## Current features in detail

### Task routing

The router uses keyword matching to classify tasks as research, email, calendar, or unknown.

### Research Agent

The research flow evaluates sample freelance opportunities using:

- fit scoring
- payment scoring
- APPLY / MAYBE / SKIP decisioning
- persistence of qualified leads to SQLite

### Duplicate protection

Research lead persistence includes a duplicate check based on existing lead titles before saving a qualified opportunity.

### Proposal drafting and approval

The system can create a proposal draft for a lead and then place it into a human approval queue. Approvals can be approved or rejected.

### Data layer

- FastAPI application
- SQLAlchemy models
- SQLite local persistence
- Session-based request handling
- SQLite foreign-key enforcement and cascading embedding deletion

## Known limitations

- No authentication, authorization, or multi-user isolation.
- All memory operations use the fixed `owner_id="local"`.
- No bulk memory re-indexing or embedding-model migration.
- Changing embedding models can make existing memories unavailable to search until manually re-embedded.
- Search scores stored embeddings in application code; there is no external vector database or approximate-nearest-neighbor index.
- The SQLite database is local and unencrypted.
- Memory retrieval is not integrated into task routing, agents, prompts, or tools.
- Gmail and Calendar integrations remain disabled.
- Research data remains sample data; there is no scraping or external research provider.

## Roadmap

### v0.6 Safety & Reliability

**Completed:**
- Research lead duplicate protection
- Approval state safety and conflict handling
- API input validation and validation tests
- Research persistence and error-handling tests
- Database transaction rollback when research persistence fails
- Generic API error responses for database failures during lead creation
- Server-side exception logging for lead creation failures

**Remaining:**
- Alembic database migrations
- Secure configuration and secrets management
- Review error handling across the remaining database-writing operations

Database error-handling implementation commit: `c0feb81`.

### Next expansion

- React dashboard
- Real research sources
- Gmail integration
- Calendar integration
- Eventual v1.0 deployable Digital Office

External integrations must remain disabled until security, approval safeguards, and validation are ready.
