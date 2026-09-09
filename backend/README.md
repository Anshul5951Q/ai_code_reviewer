# Backend — AI Code Reviewer

FastAPI backend for the AI Code Reviewer platform.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

## API Endpoints (Phase 1)

| Method | Path | Description |
|---|---|---|
| GET | `/api/health` | Service health check |
| GET | `/api/repositories` | List repositories (empty in Phase 1) |
| GET | `/api/repositories/{id}` | Get single repository |
| GET | `/api/reviews` | List reviews (empty in Phase 1) |
| GET | `/api/reviews/{id}` | Get single review |
| GET | `/api/security/summary` | Security overview (zeroed in Phase 1) |
| GET | `/api/security/findings` | List findings (empty in Phase 1) |
| GET | `/api/docs` | Interactive API documentation |

## Running Tests

```bash
pytest tests/ -v
```

## Database Migrations

Requires PostgreSQL running:

```bash
alembic revision --autogenerate -m "initial schema"
alembic upgrade head
```

## Models

- **Repository**: GitHub repository connected to the platform
- **Review**: Code review analysis run on a repository commit
- **Finding**: Individual security or quality finding from a review

## Project Structure

```
app/
├── main.py          # FastAPI application entry point
├── api/             # Route handlers
│   ├── health.py
│   ├── repositories.py
│   ├── reviews.py
│   └── security.py
├── core/            # Configuration and logging
│   ├── config.py
│   └── logging.py
├── models/          # SQLAlchemy ORM models
│   ├── repository.py
│   ├── review.py
│   └── finding.py
├── schemas/         # Pydantic request/response schemas
│   ├── repository.py
│   ├── review.py
│   └── finding.py
└── services/        # Business logic (future phases)
migrations/          # Alembic migration scripts
tests/               # pytest test suite
```
