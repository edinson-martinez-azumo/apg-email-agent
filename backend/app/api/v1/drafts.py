import uuid
import datetime
from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from app.core.deps import DB
from app.db.models.draft import Draft
from app.db.models.email import Email
from app.db.models.audit_log import AuditLog
from app.schemas.draft import DraftRead, DraftUpdate

router = APIRouter()


@router.get('/by-email/{email_id}', response_model=DraftRead)
async def get_draft_by_email(email_id: str, db: DB):
    result = await db.execute(select(Draft).where(Draft.email_id == email_id))
    draft = result.scalar_one_or_none()
    if not draft:
        raise HTTPException(status_code=404, detail='Draft not found')
    return draft


@router.get('/{draft_id}', response_model=DraftRead)
async def get_draft(draft_id: str, db: DB):
    draft = await db.get(Draft, draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail='Draft not found')
    return draft


@router.put('/{draft_id}', response_model=DraftRead)
async def update_draft(draft_id: str, body: DraftUpdate, db: DB):
    draft = await db.get(Draft, draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail='Draft not found')
    draft.edited_body = body.edited_body
    db.add(AuditLog(
        id=str(uuid.uuid4()),
        email_id=draft.email_id,
        action='edited',
        created_at=datetime.datetime.now(datetime.timezone.utc),
    ))
    await db.commit()
    await db.refresh(draft)
    return draft


@router.post('/{draft_id}/approve')
async def approve_draft(draft_id: str, db: DB):
    draft = await db.get(Draft, draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail='Draft not found')
    draft.approved_at = datetime.datetime.now(datetime.timezone.utc)
    email = await db.get(Email, draft.email_id)
    if email:
        email.status = 'approved'
    db.add(AuditLog(
        id=str(uuid.uuid4()),
        email_id=draft.email_id,
        action='approved',
        created_at=datetime.datetime.now(datetime.timezone.utc),
    ))
    await db.commit()
    return {'status': 'approved'}


@router.post('/{draft_id}/discard')
async def discard_draft(draft_id: str, db: DB):
    draft = await db.get(Draft, draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail='Draft not found')
    email = await db.get(Email, draft.email_id)
    if email:
        email.status = 'discarded'
    db.add(AuditLog(
        id=str(uuid.uuid4()),
        email_id=draft.email_id,
        action='discarded',
        created_at=datetime.datetime.now(datetime.timezone.utc),
    ))
    await db.commit()
    return {'status': 'discarded'}


@router.post('/{draft_id}/send')
async def send_draft(draft_id: str, db: DB):
    from app.services.gmail_service import send_reply

    draft = await db.get(Draft, draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail='Draft not found')
    body_to_send = draft.edited_body or draft.body
    email = await db.get(Email, draft.email_id)
    if not email:
        raise HTTPException(status_code=404, detail='Email not found')

    await send_reply(email.gmail_id, email.from_email, email.subject or '', body_to_send)

    draft.sent_at = datetime.datetime.now(datetime.timezone.utc)
    email.status = 'sent'
    db.add(AuditLog(
        id=str(uuid.uuid4()),
        email_id=email.id,
        action='sent',
        created_at=datetime.datetime.now(datetime.timezone.utc),
    ))
    await db.commit()
    return {'status': 'sent'}
