import uuid
import datetime
from fastapi import APIRouter, HTTPException
from sqlalchemy import select, func
from app.core.deps import DB
from app.db.models.email import Email
from app.db.models.draft import Draft
from app.db.models.product_match import ProductMatch
from app.db.models.audit_log import AuditLog
from app.schemas.email import EmailRead, EmailListResponse

router = APIRouter()


@router.get('/', response_model=EmailListResponse)
async def list_emails(db: DB, status: str | None = None, page: int = 1, size: int = 20):
    q = select(Email).order_by(Email.received_at.desc())
    if status:
        q = q.where(Email.status == status)
    count_q = select(func.count()).select_from(Email)
    if status:
        count_q = count_q.where(Email.status == status)
    total = await db.scalar(count_q)
    result = await db.execute(q.offset((page - 1) * size).limit(size))
    emails = result.scalars().all()
    return {'items': emails, 'total': total or 0, 'page': page, 'size': size}


@router.post('/sync')
async def sync_emails(db: DB):
    """Pull unread Gmail messages and save new ones to DB."""
    from app.services.gmail_service import list_unread_messages, get_message, parse_message, get_token
    from sqlalchemy.exc import IntegrityError

    token_data = await get_token(db)
    messages = list_unread_messages(token_data, max_results=50)
    imported = 0
    skipped = 0

    for stub in messages:
        msg = get_message(token_data, stub['id'])
        parsed = parse_message(msg)

        # Skip if already in DB
        existing = await db.scalar(select(Email).where(Email.gmail_id == parsed['gmail_id']))
        if existing:
            skipped += 1
            continue

        email = Email(
            id=str(uuid.uuid4()),
            status='pending',
            **parsed,
        )
        db.add(email)
        try:
            await db.flush()
            imported += 1
        except IntegrityError:
            await db.rollback()
            skipped += 1

    await db.commit()
    return {'imported': imported, 'skipped': skipped, 'total_found': len(messages)}


@router.get('/{email_id}', response_model=EmailRead)
async def get_email(email_id: str, db: DB):
    email = await db.get(Email, email_id)
    if not email:
        raise HTTPException(status_code=404, detail='Email not found')
    return email


@router.post('/{email_id}/generate')
async def generate_draft_for_email(email_id: str, db: DB):
    """Trigger or re-generate an AI draft for this email."""
    from app.services.embedding_service import search_products
    from app.services.claude_service import generate_draft as ai_generate

    email = await db.get(Email, email_id)
    if not email:
        raise HTTPException(status_code=404, detail='Email not found')

    query = f"{email.subject or ''} {email.body_text or ''}".strip()
    products = await search_products(query, db, top_k=8)

    draft_body, confidence_score = ai_generate(email.subject or '', email.body_text or '', products)

    result = await db.execute(select(Draft).where(Draft.email_id == email_id))
    existing = result.scalar_one_or_none()

    draft = existing or Draft(id=str(uuid.uuid4()), email_id=email_id)
    draft.body = draft_body
    draft.edited_body = None
    draft.confidence_score = confidence_score
    db.add(draft)

    for p in products:
        db.add(ProductMatch(
            id=str(uuid.uuid4()),
            email_id=email_id,
            sku=p['sku'],
            title=p['title'],
            score=None,
        ))

    email.status = 'draft_ready'
    db.add(AuditLog(
        id=str(uuid.uuid4()),
        email_id=email_id,
        action='generated',
        created_at=datetime.datetime.now(datetime.timezone.utc),
    ))
    await db.commit()
    return {'status': 'ok', 'draft_preview': draft_body[:200]}
