# APG Email Agent

## Project

APG Email Agent — reads customer emails, generates AI draft replies using APG's product catalog (Shopify + Fishbowl XLSXs), presents drafts to sales reps for review/approval before sending via Gmail API.

## Stack

- Python 3.12 / FastAPI 0.115+ / SQLAlchemy 2.x async / Alembic / Pydantic v2
- React 19 / TypeScript / Vite / TanStack Query v5 / React Router v7 / Tailwind v3 / shadcn/ui
- Vercel (deploy) / Neon Postgres (production DB) / Docker (local DB only)

## Vercel constraint

10s function timeout on free tier. Claude API call + product search must finish in <7s. Cap product context at 8 SKUs max.

## Database rules

- `base_class.py` → DeclarativeBase only
- `base.py` → re-exports Base + imports all models (Alembic env only)
- Never use sync SQLAlchemy API
- No raw SQL in application code — SQLAlchemy ORM only
- Alembic only for schema changes — never `Base.metadata.create_all` in app code
- `pool_size=1, max_overflow=0` required for Vercel serverless

## Email states

`pending → draft_ready → approved → sent` (also `discarded`)

## Product search — read before touching product_service.py or claude_service.py

Current implementation uses keyword matching over in-memory DataFrame. Intentionally temporary.

**Phase 1 — demo (current):** keyword search in `product_service.py`. Do not invest in improving keyword logic.

**Phase 1.5 — quick win:** Replace single Claude call with two-step in `claude_service.py`:
1. First call: extract structured search terms from customer email (product type, material, capacity, end use)
2. Use extracted terms for keyword search (bridges vocabulary gap)
3. Second call: generate full draft with matched products
Change to `claude_service.py` only. No DB changes.

**Phase 2 — production:** pgvector on Neon. Embeddings for every product, cosine similarity query. Requires: pgvector extension, one Alembic migration, embedding generation script.

## Neon / SSL

`ssl=require` — never `sslmode=require` (asyncpg-specific)

## Frontend

- APG emerald green `#2D6A4F` as primary color throughout UI
- React Query for all server state — never `useEffect` + fetch
- shadcn/ui components in `frontend/src/components/ui/`

## What NOT to add

No Auth0, no Celery, no Redux/Zustand, no GraphQL, no E2E tests, no monorepo tooling, no JWT auth (internal tool — simple API key or session cookie sufficient for demo).

## Key commands

```bash
# Backend
cd backend && uv sync && uv run fastapi dev app/main.py
cd backend && make migrate
cd backend && make export-reqs

# Frontend
cd frontend && pnpm install && pnpm dev
```
