from fastapi import APIRouter
from sqlalchemy import text
from app.core.deps import DB
from datetime import datetime, timezone

router = APIRouter()


@router.get('/health')
async def health_check(db: DB):
    try:
        await db.execute(text('SELECT 1'))
        db_status = 'connected'
    except Exception:
        db_status = 'unreachable'
    return {
        'status': 'ok' if db_status == 'connected' else 'error',
        'service': 'APG Email Agent',
        'db': db_status,
        'timestamp': datetime.now(timezone.utc).isoformat(),
    }
