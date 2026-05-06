# APG Email Agent

Internal sales tool for APackaging Group. Reads customer emails, generates AI-powered draft replies using APG's product catalog, and lets sales reps review/approve before sending.

## Quick Start

```bash
# 1. Clone
git clone https://github.com/apg/email-agent && cd email-agent

# 2. Env vars
cp .env.example backend/.env.local   # fill in ANTHROPIC_API_KEY, Gmail OAuth creds
echo "VITE_API_URL=http://localhost:8000" > frontend/.env.local

# 3. Local Postgres
docker compose up -d

# 4. Backend
cd backend
uv sync
uv run alembic upgrade head
uv run fastapi dev app/main.py        # → http://localhost:8000/api/docs

# 5. Frontend (new terminal)
cd frontend
pnpm install
pnpm dlx shadcn@2 init --yes --defaults
pnpm dlx shadcn@2 add button card badge input label textarea table separator --yes
pnpm dev                               # → http://localhost:5173
```

## Deploy to Vercel

```bash
# 1. Generate requirements.txt
cd backend && make export-reqs
git add requirements.txt && git commit -m "chore: requirements.txt"

# 2. Apply migrations to Neon
# Replace sslmode=require with ssl=require in your Neon connection string
DATABASE_URL=postgresql+asyncpg://...?ssl=require uv run alembic upgrade head

# 3. Set Vercel env vars
vercel env add DATABASE_URL production       # ...?ssl=require
vercel env add ANTHROPIC_API_KEY production
vercel env add GMAIL_CLIENT_ID production
vercel env add GMAIL_CLIENT_SECRET production
vercel env add GMAIL_REDIRECT_URI production # https://your-app.vercel.app/api/v1/auth/callback
vercel env add VITE_API_URL production       # https://your-app.vercel.app
vercel env add FRONTEND_URL production       # https://your-app.vercel.app

# 4. Deploy
git push origin main
```

**Neon setup:** Create project at neon.tech → copy connection string → replace `sslmode=require` with `ssl=require` → set as `DATABASE_URL`.

## Architecture

- **Backend:** FastAPI + SQLAlchemy async + Alembic on Python 3.12
- **Frontend:** React 19 + TypeScript + Vite + TanStack Query + shadcn/ui
- **AI:** Anthropic claude-sonnet-4-6 for draft generation
- **Email:** Gmail API via OAuth2
- **DB:** PostgreSQL (Docker locally, Neon in production)
- **Deploy:** Vercel (frontend static + backend Python serverless)

## Gmail OAuth Setup

1. Create project at console.cloud.google.com
2. Enable Gmail API
3. Create OAuth2 credentials (Web application)
4. Add `http://localhost:8000/api/v1/auth/callback` as redirect URI
5. Set `GMAIL_CLIENT_ID` and `GMAIL_CLIENT_SECRET` in `.env.local`
6. Visit `http://localhost:8000/api/v1/auth/gmail` to authenticate
