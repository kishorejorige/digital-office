# Digital Office

Digital Office is an AI-assisted personal operations system being built to help manage research, freelance opportunities, leads, proposals, approvals, and eventually email and calendar workflows.

Current version: v0.5.0

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
- Pytest test suite

This is currently an internal prototype. Real Gmail and Calendar integrations should not be enabled until security, approval safeguards, and validation are completed.

## Current architecture

```text
Task → Router → Agent → Tools → Database → Approval
```

The flow is intentionally simple:

1. A task is submitted to the API.
2. The router decides whether it is a research, email, or calendar task.
3. A matching agent processes the request.
4. Tools score opportunities and draft proposals.
5. Valid leads are saved to SQLite.
6. Proposals move into a human approval queue.

## Project structure

```text
.
├── app/
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── email.py
│   │   └── research.py
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
│   ├── test_approval_flow.py
│   ├── test_research_agent.py
│   ├── test_research_persistence.py
│   └── test_routing.py
├── .python-version
├── digital_office.db
├── main.py
├── pyproject.toml
├── README.md
├── uv.lock
└── .gitignore
```

## Local setup with uv

This project uses `uv` for dependency management.

### 1) Install dependencies

```bash
uv sync --group dev
```

### 2) Run tests

```bash
uv run pytest -q
```

Testing status: 8 tests passing.

### 3) Start the FastAPI app

```bash
uv run uvicorn app.main:app --host 0.0.0.0 --port 8585
```

### 4) Open Swagger docs

```text
http://localhost:8585/docs
```

## API endpoints

The application currently implements the following endpoints:

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
- session-based request handling

## Roadmap

### v0.6 Safety & Reliability

- stronger duplicate protection
- approval state safety
- validation and API tests
- Alembic migrations
- secure configuration

### Next expansion

- React dashboard
- real research sources
- Gmail integration
- Calendar integration
- eventual v1.0 deployable Digital Office

## Notes

This project is intentionally simple and designed as a prototype for experimentation and portfolio work. It is not yet a production-grade system for external integrations or real customer data.

The next major milestones are security, validation, and governance around approvals and external service access before Gmail, Calendar, or live research integrations are enabled.
