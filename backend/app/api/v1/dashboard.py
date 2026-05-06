from fastapi import APIRouter
from sqlalchemy import select, func
from app.core.deps import DB
from app.db.models.email import Email
from app.db.models.draft import Draft
from app.schemas.dashboard import DashboardResponse, DashboardStats, RecentSentEmail

router = APIRouter()


@router.get('/stats', response_model=DashboardResponse)
async def get_stats(db: DB):
    total = await db.scalar(select(func.count()).select_from(Email)) or 0
    pending = await db.scalar(
        select(func.count()).select_from(Email).where(Email.status == 'pending')
    ) or 0
    sent = await db.scalar(
        select(func.count()).select_from(Email).where(Email.status == 'sent')
    ) or 0

    result = await db.execute(
        select(Email)
        .where(Email.status == 'sent')
        .order_by(Email.received_at.desc())
        .limit(20)
    )
    sent_emails = result.scalars().all()

    recent_sent = []
    for email in sent_emails:
        draft_result = await db.execute(
            select(Draft).where(Draft.email_id == email.id)
        )
        draft = draft_result.scalar_one_or_none()
        recent_sent.append(RecentSentEmail(
            id=email.id,
            from_email=email.from_email,
            from_name=email.from_name,
            subject=email.subject,
            sent_at=draft.sent_at if draft else None,
        ))

    return DashboardResponse(
        stats=DashboardStats(
            total_emails=total,
            pending=pending,
            drafts_sent=sent,
            avg_response_time_hours=None,
        ),
        recent_sent=recent_sent,
    )
