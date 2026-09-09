# AI Code Reviewer

An AI-powered code review and security analysis platform built for engineering teams.

---

## Architecture

```
ai-code-reviewer/
├── frontend/     # Next.js 14 + TypeScript + Tailwind CSS + shadcn/ui
└── backend/      # Python + FastAPI + SQLAlchemy + Alembic + Pydantic
```

---

## Frontend Setup

### Requirements
- Node.js 18+
- npm 9+

### Getting Started

```bash
cd frontend
npm install
cp .env.local.example .env.local   # or edit .env.local directly
npm run dev
```

The frontend will start at http://localhost:3000

### Environment Variables

| Variable | Default | Description |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000/api` | Backend API base URL |

### Scripts

```bash
npm run dev       # Development server
npm run build     # Production build
npm run lint      # ESLint check
npm run start     # Start production server (after build)
```

---

## Backend Setup

### Requirements
- Python 3.11+
- pip

### Getting Started

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

The API will start at http://localhost:8000

Interactive API docs: http://localhost:8000/api/docs

### Environment Variables

See [`backend/.env.example`](backend/.env.example) for all available settings.

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql://...` | PostgreSQL connection string |
| `CORS_ORIGINS` | `http://localhost:3000` | Allowed frontend origins |
| `APP_ENV` | `development` | Environment (development/production) |

### Running Tests

```bash
cd backend
pytest tests/ -v
```

### Database Migrations (once PostgreSQL is available)

```bash
cd backend
alembic revision --autogenerate -m "initial schema"
alembic upgrade head
```

---

## Phase Roadmap

| Phase | Scope | Status |
|---|---|---|
| **Phase 1** | Foundation + UI Shell | ✅ Complete |
| **Phase 2** | Real Data Layer + GitHub Integration | ✅ Complete |
| **Phase 3** | Repository Ingestion + Analysis Engine Foundation | ✅ Complete |
| **Phase 4** | GitHub OAuth + Secure Repository Connection | ✅ Complete |
| Phase 5 | Multi-Agent Security & Code Analysis | 🔜 Planned |
| Phase 6 | Remediation + Verification | 🔜 Planned |
| Phase 7 | Authentication & Production Hardening | 🔜 Planned |

---

## GitHub OAuth Setup

To enable connecting real GitHub accounts and importing accessible repositories:

### 1. Create a GitHub OAuth Application
1. Go to your GitHub account **Settings** → **Developer Settings** → **OAuth Apps** → **New OAuth App** (or visit [https://github.com/settings/applications/new](https://github.com/settings/applications/new)).
2. Set **Application Name**: `AI Code Reviewer (Local Dev)`
3. Set **Homepage URL**: `http://localhost:3000`
4. Set **Authorization callback URL**: `http://localhost:8000/api/github/callback`
5. Click **Register application**.

### 2. Configure Credentials in Backend
Copy `.env.example` to `.env` in `backend/` and configure:

```bash
# GitHub OAuth
GITHUB_CLIENT_ID=your_client_id_from_github
GITHUB_CLIENT_SECRET=your_client_secret_from_github
GITHUB_REDIRECT_URI=http://localhost:8000/api/github/callback
GITHUB_API_BASE_URL=https://api.github.com
FRONTEND_URL=http://localhost:3000

# Server-Side Token Encryption Key (generate via: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
GITHUB_TOKEN_ENCRYPTION_KEY=your_fernet_encryption_key_here
```

> **Security Note**: The `GITHUB_CLIENT_SECRET` and access tokens are strictly server-side and never exposed to the frontend or saved as plaintext. Tokens are encrypted at rest using AES-128-CBC/HMAC via Fernet. OAuth `state` is validated single-use with cryptographic randomness and short expiration.

### 3. Start Backend
```bash
cd backend
# Run database migrations
alembic upgrade head

# Start API server
uvicorn app.main:app --reload --port 8000
```

### 4. Start Frontend
```bash
cd frontend
npm run dev
```

### 5. Connect GitHub & Import Repositories
1. Navigate to `http://localhost:3000/dashboard/repositories`.
2. Click **Connect GitHub** in the top banner.
3. Review the permission scope in the modal (`repo` read access) and authorize the application on GitHub.
4. Upon redirection, browse your accessible public and private repositories, search, filter by ownership/visibility, and click **Import** or multi-select repositories for batch import.
5. Navigate to **Reviewer** to analyze branches and commits from imported repositories.

---

## Design System

- **Background**: `#08090B`
- **Surface**: `#0F1115`
- **Primary**: Indigo 500 (`#6366F1`)
- **Critical**: Red 500 (`#EF4444`)
- **Typography**: Inter (sans-serif), JetBrains Mono (code/hashes)
