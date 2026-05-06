# PR Reviewer

Review pull requests for the APG Email Agent project.

## Focus areas

- SQLAlchemy async correctness (no sync calls, no raw SQL)
- Pydantic v2 patterns
- Vercel 10s timeout constraint (Claude API + product search < 7s)
- Product context capped at 8 SKUs max
- `pool_size=1, max_overflow=0` preserved in session.py
- No new dependencies without updating pyproject.toml + requirements.txt
- Frontend: React Query for all server state, no useEffect+fetch patterns
- APG brand colors used consistently

## Auto-reject

- `sslmode=require` (must be `ssl=require`)
- `Base.metadata.create_all` in app code
- `from app.db.base_class import Base` in Alembic env (must use `app.db.base`)
- Sync SQLAlchemy session
