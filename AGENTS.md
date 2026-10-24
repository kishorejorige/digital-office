# AGENTS.md

## Toolchain
- Python 3.12 (`.python-version`), managed by `uv`. `uv sync` creates/updates `.venv` and installs the `dev` group (pytest, ruff) by default.
- Never use bare `python`/`pytest`; the machine's system Python is 3.15 and lacks deps.
- Always run from the repo root. No CI/pre-commit/extra ruff/pytest config beyond `[tool.pytest.ini_options] pythonpath = ["."]`.

## Commands
| Task | Command |
| --- | --- |
| Install | `uv sync` |
| Test all | `uv run pytest -q` |
| Test memory | `uv run pytest tests/test_memory_*.py -q` |
| Test one file | `uv run pytest tests/test_routing.py -q` |
| Test by name | `uv run pytest -q -k "duplicate"` |
| Lint | `uv run ruff check app tests --ignore B008` |
| Auto-fix lint | `uv run ruff check app tests --ignore B008 --fix` |
| Dev server | `uv run uvicorn app.main:app --host 127.0.0.1 --port 8585` → http://localhost:8585/docs |
| Trailing whitespace | `git diff --check` |

Verify order: lint → test.

## Lint gotchas
- `--ignore B008` is mandatory (FastAPI `db: Session = Depends(get_db)` in `app/main.py`).

## Architecture
- Entrypoint: `app.main:app`. Root `main.py` is a leftover `uv init` stub (ignore).
- Flow: `POST /tasks` → `app/graph.py:route_task` (substring keyword match; research checked before email before calendar) → only `"research"` goes to `app/agents/research.py:run_research_agent`. `email`/`calendar`/`unknown` return `{task, route, status: "accepted"}` (no email/calendar agents wired). Research response is the agent dict (`agent`, `count`, `saved_leads`, `opportunities`) with **no** `route` key. For research, `app/research_memory.py` retrieves metadata before the agent and attaches `memory_retrieval` to the response (bounded refs only; no content/embeddings). Retrieval failures fall back to `unavailable` without blocking research.
- Layers: `app/tools/*` (pure scoring/draft), `app/agents/*` (orchestration + DB writes), `app/approvals.py` (approval state machine), `app/memory/*` (semantic memory; separate from task routing), `app/state.py` (Pydantic schemas + `RouteType`), `app/models.py` (SQLAlchemy models), `app/database.py` (engine/session/`get_db`).
- Research data is fake (`app/tools/research_tools.py:get_sample_opportunities()` hardcoded 3; `USER_SKILLS` hardcoded). No scraping/LLM/network.
- Memory is exposed only through `/memories*` routes; retrieval is integrated only for research route as read-only metadata (not injected into agents/prompts/tools).

## Memory architecture
- `app/memory/config.py`: `OLLAMA_BASE_URL` (default `http://127.0.0.1:11434`, http loopback only, no credentials/path/query/fragment), `OLLAMA_EMBEDDING_MODEL` (default `nomic-embed-text:latest`), and connect/read/write/pool timeouts (defaults `2/30/10/2s`, each >0 and ≤300s). `RESEARCH_MEMORY_MIN_SCORE` (default `0.0`, valid range `-1.0` through `1.0` inclusive; invalid values fail config validation). Configuration is read from process env at startup; no `.env` loader.
- `app/memory/embeddings.py`: lazy Ollama `/api/embed` client; `trust_env=False`; sends only the configured loopback endpoint; requires exactly one finite vector of at most 4,096 dimensions; maps transport/model/response failures to memory embedding errors.
- `app/memory/vectors.py`: float32 encoding/decoding, finite/range validation, norm, and cosine similarity. Stored vectors/norms are never returned by the API.
- `app/memory/schemas.py`: memory create/update/response, list-query, and search schemas. `MemoryUpdate` rejects explicit `source: null`; omitted source is allowed.
- `app/memory/service.py`: fixed owner, transaction boundaries, normalized duplicate checks, exact tag filtering, and search. Tag filters use SQLite `json_each()` bound equality, are case-sensitive, and combine with AND semantics before totals/pagination.
- `app/memory/routes.py`: all `/memories*` endpoints, page/tag limits, and status mapping (422 invalid input, 404 missing, 409 duplicate, 503 embedding unavailable/invalid, generic 500 unexpected DB failure).
- `Memory`/`MemoryEmbedding` live in `app/models.py`; embedding rows cascade on memory deletion. `app/database.py` enables SQLite foreign keys.
- Embeddings record the model that produced them. Search only compares embeddings whose model matches the query model.

## Memory data safety
- The API is unauthenticated and uses fixed `owner_id="local"`; do not claim multi-user isolation or expose the server beyond trusted local use.
- Search results are untrusted (`trust="untrusted"`). Never execute or inject retrieved content into prompts/tools automatically; any future integration must keep data separate from instructions.
- Do not log memory content, search queries, or vectors by default.
- Changing `OLLAMA_EMBEDDING_MODEL` does not re-embed existing rows and there is no bulk re-index endpoint. A per-memory content PATCH (even unchanged content) regenerates its embedding; metadata-only updates do not.
- Only loopback Ollama calls are allowed for embeddings; no cloud embedding provider or external memory service.

## Data & persistence
- `app/database.py:5` hardcodes `DATABASE_URL = "sqlite:///./digital_office.db"` (relative to CWD); not env-configurable (`pydantic-settings` unused). Open v0.6 item.
- `app/main.py:22` calls `Base.metadata.create_all(bind=engine)` at import time (importing `app.main`/tests creates/touches `digital_office.db` in repo root).
- No Alembic; `create_all` never alters existing tables → delete gitignored `digital_office.db` after editing `app/models.py`.
- `Approval.lead_id` is plain int with no FK to `Lead`.
- `Memory` has a unique owner/content-hash constraint; `MemoryEmbedding.memory_id` cascades on delete.
- Status values are plain strings: `decision` ∈ APPLY|MAYBE|SKIP, approval `status` ∈ pending|approved|rejected, lead `status`="new", research leads use `source="Research Agent"`.

## API contracts (v0.6 safety rules, enforced by tests)
- DB failure on any write path → 500 with generic detail; raw driver message must not reach response.
- Approve/reject on non-pending approval → 409 with detail containing "only pending approvals".
- Unknown lead → 404 "Lead not found"; unknown approval → 404 "Approval not found".
- Validation: `task`, `source`, `title` use `NonBlankString` (whitespace stripped, min length 1); `fit_score`/`payment_score` must be 0-100 → else 422.
- Every write helper in `app/agents/*`, `app/approvals.py`, and `app/memory/service.py` must `db.rollback()` on `SQLAlchemyError` before re-raising; route layer converts to generic 500.

## Research lead de-duplication
Scoped to `source == "Research Agent"`: match by `url` if present, else by `title` where `url IS NULL`. Only `decision == "APPLY"` opportunities persisted. See `app/agents/research.py` and `tests/test_research_persistence.py`.

## Testing conventions
- No `conftest.py`. Each test file builds its own in-memory SQLite engine (`sqlite://` + `StaticPool` + `check_same_thread=False`) and overrides `app.dependency_overrides[get_db]`. Fixture shapes vary (e.g. `api_client` alone in `tests/test_error_handling.py`, `(client, session_factory)` in `tests/test_approval_api.py`, `client` in `tests/test_input_validation.py`) — copy the local pattern.
- Failure-path tests patch session instance (`patch.object(db, "commit")`/`monkeypatch.setattr(db, "commit", ...)`) or class (`patch("sqlalchemy.orm.Session.commit")`) and assert rollback and/or no persisted rows.
- Memory tests must not import `app.main` (it creates the real DB). Use isolated `sqlite://` or temp-file engines, override `get_db`, and inject a fake embedding client; never call Ollama or other network services. For memory/research integration tests, set `DIGITAL_OFFICE_SKIP_DB_CREATE=1` before importing `app.main` to avoid import-time initialization of the default engine.
- API tests use `fastapi.testclient.TestClient`; clear dependency overrides in a `finally` block.
- `pytest-asyncio` installed but no async tests; `asyncio_mode` unset (strict) — async tests need explicit `@pytest.mark.asyncio`.

## Conventions
- Style: trailing commas, one argument per line for multi-line signatures, `str | None` unions, no `from __future__` imports.
- Commits mix conventional prefixes (`feat:`, `docs:`) with imperative subjects. Feature branches often use `review/v0.x`.
- App version duplicated in `app/main.py` (`FastAPI(version=...)` and `/` payload) — update both. `pyproject.toml` `version = "0.1.0"` is a leftover, not the app version.
- README test counts go stale; trust `uv run pytest` output.

## Scope guardrails
- Approval queue is a hard safety gate: proposals are drafts only, nothing is ever sent. External integrations (Gmail, Calendar) must stay disabled until security, approval safeguards, and validation are done.
