"""Poll task endpoint for automated email processing."""

import logging
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func
from app.core.deps import DB
from app.db.models.email import Email
from app.db.models.draft import Draft
from app.db.models.audit_log import AuditLog
from app.db.models.app_setting import AppSetting
from app.db.models.product_match import ProductMatch
from app.services.claude_service import generate_draft as ai_generate
from app.services.gmail_service import send_reply, get_token

logger = logging.getLogger(__name__)

router = APIRouter()


class PollResponse(BaseModel):
    new_emails: int
    processed_count: int
    status: str
    message: str


class PollStatusResponse(BaseModel):
    auto_sync: bool
    auto_generate: bool
    auto_send: bool
    polling_interval_seconds: int
    last_poll_at: datetime | None
    pending_count: int


@router.get('/poll/status', response_model=PollStatusResponse)
async def get_poll_status(db: DB):
    """Get current polling status and configuration."""
    # Get settings
    result = await db.execute(
        select(AppSetting).where(AppSetting.key.in_(['auto_sync', 'auto_generate', 'auto_send', 'polling_interval_seconds']))
    )
    rows = result.scalars().all()
    settings_dict = {row.key: row.value for row in rows}

    auto_sync = settings_dict.get('auto_sync', 'true').lower() == 'true'
    auto_generate = settings_dict.get('auto_generate', 'false').lower() == 'true'
    auto_send = settings_dict.get('auto_send', 'false').lower() == 'true'
    poll_interval = int(settings_dict.get('polling_interval_seconds', '60'))

    # Get last poll time (from audit log)
    last_result = await db.execute(
        select(AuditLog)
        .where(AuditLog.action == 'auto_poll')
        .order_by(AuditLog.created_at.desc())
        .limit(1)
    )
    last_poll = last_result.scalar_one_or_none()
    last_poll_at = last_poll.created_at if last_poll else None

    # Get pending count
    pending_result = await db.execute(
        select(func.count()).select_from(Email).where(Email.status == 'pending')
    )
    pending_count = pending_result.scalar() or 0

    return PollStatusResponse(
        auto_sync=auto_sync,
        auto_generate=auto_generate,
        auto_send=auto_send,
        polling_interval_seconds=poll_interval,
        last_poll_at=last_poll_at,
        pending_count=pending_count,
    )


@router.post('/poll', response_model=PollResponse)
async def poll_emails(db: DB):
    """Poll for new emails and process them based on auto_* settings."""
    # Check settings
    result = await db.execute(
        select(AppSetting).where(AppSetting.key.in_(['auto_sync', 'auto_generate', 'auto_send']))
    )
    rows = result.scalars().all()
    settings_dict = {row.key: row.value for row in rows}

    auto_sync = settings_dict.get('auto_sync', 'true').lower() == 'true'
    auto_generate = settings_dict.get('auto_generate', 'false').lower() == 'true'
    auto_send = settings_dict.get('auto_send', 'false').lower() == 'true'

    # Log the poll
    db.add(AuditLog(
        id=str(uuid.uuid4()),
        email_id=None,
        action='auto_poll',
        created_at=datetime.now(timezone.utc),
    ))

    # Step 1: Always sync (unless disabled)
    sync_count = 0
    if auto_sync:
        from app.services.gmail_service import sync_emails
        try:
            await sync_emails(db)
            await db.commit()
            sync_count = 1
        except Exception as e:
            logger.error(f'Sync failed: {e}')
            await db.rollback()
            return PollResponse(
                new_emails=0,
                processed_count=0,
                status='error',
                message=f'Sync failed: {str(e)}',
            )

    # Get pending emails
    pending_result = await db.execute(
        select(Email).where(Email.status == 'pending').order_by(Email.received_at.asc())
    )
    pending_emails = pending_result.scalars().all()

    if not pending_emails:
        status = 'clean' if sync_count == 0 else 'synced'
        return PollResponse(
            new_emails=len(pending_emails),
            processed_count=0,
            status=status,
            message='No pending emails found.' if sync_count == 0 else f'Synced {sync_count} batch(es). No pending emails.',
        )

    # Step 2: Generate drafts for pending emails (if auto_generate is ON)
    generated_count = 0
    if auto_generate:
        generated_count, errors = await _generate_drafts(db, pending_emails)
        await db.commit()
    else:
        await db.commit()
        return PollResponse(
            new_emails=len(pending_emails),
            processed_count=0,
            status='synced' if sync_count else 'clean',
            message=f'Synced. {len(pending_emails)} pending email(s) awaiting manual generation.',
        )

    # Step 3: Send generated drafts (if auto_send is ON)
    sent_count = 0
    if auto_send:
        # Get emails that now have drafts with approved_at (auto-generated drafts are auto-approved)
        auto_approved_result = await db.execute(
            select(Draft).where(
                Draft.email_id.in_([e.id for e in pending_emails]),
                Draft.approved_at.isnot(None),
                Draft.sent_at.is_(None),
            )
        )
        drafts_to_send = auto_approved_result.scalars().all()

        if drafts_to_send:
            sent_count, send_errors = await _send_drafts(db, drafts_to_send)
            await db.commit()

    return PollResponse(
        new_emails=len(pending_emails),
        processed_count=generated_count + sent_count,
        status='completed',
        message=f'Synced: {sync_count}, Generated: {generated_count}, Sent: {sent_count}',
    )


async def _get_thread_history(db: DB, email: Email) -> list:
    """Get thread history for a given email."""
    if not email.thread_id:
        return []

    result = await db.execute(
        select(Email)
        .where(
            (Email.thread_id == email.thread_id) &
            (Email.received_at < email.received_at) &
            (Email.status != 'discarded')
        )
        .order_by(Email.received_at.asc())
    )
    return result.scalars().all()


async def _generate_drafts(db: DB, pending_emails: list) -> tuple[int, list[str]]:
    """Generate AI drafts for pending emails. Returns (count, errors)."""
    generated = 0
    errors = []

    for email in pending_emails:
        email_id = email.id
        email_subject = email.subject or ''
        email_body = email.body_text or ''
        email_gmail_id = email.gmail_id
        email_from_email = email.from_email

        try:
            # Get existing draft if any
            existing_draft_result = await db.execute(
                select(Draft).where(Draft.email_id == email_id)
            )
            existing_draft = existing_draft_result.scalar_one_or_none()
            if existing_draft and existing_draft.sent_at:
                email.status = 'sent'
                continue

            # Search products
            try:
                from app.services.embedding_service import search_products
                query = f"{email_subject} {email_body}".strip()
                products = await search_products(query, db, top_k=12)
            except Exception as e:
                logger.warning(f'Product search failed for {email_id}: {e}')
                products = []

            # Generate draft
            thread_history = await _get_thread_history(db, email)

            try:
                draft_body, confidence_score = ai_generate(
                    email_subject,
                    email_body,
                    products,
                    thread_history=thread_history,
                )
            except Exception as e:
                raise RuntimeError(f'generate_draft error: {type(e).__name__}: {e}')

            # Save draft
            if existing_draft:
                existing_draft.body = draft_body
                existing_draft.edited_body = None
                existing_draft.confidence_score = confidence_score
                existing_draft.approved_at = None
                existing_draft.approved_by = None
            else:
                existing_draft = Draft(
                    id=str(uuid.uuid4()),
                    email_id=email_id,
                    body=draft_body,
                    edited_body=None,
                    confidence_score=confidence_score,
                    approved_at=datetime.now(timezone.utc),
                    approved_by='auto',
                )
                db.add(existing_draft)

            # Save product matches
            for p in products:
                db.add(ProductMatch(
                    id=str(uuid.uuid4()),
                    email_id=email_id,
                    sku=p['sku'],
                    title=p['title'],
                    score=None,
                ))

            generated += 1
            logger.info(f'Auto-generated draft for email {email_id}: {email_subject}')

        except Exception as e:
            error_msg = str(e)
            errors.append(f'Email {email_id}: {error_msg}')
            logger.error(f'Failed to generate draft for {email_id}: {error_msg}')

    return generated, errors


async def _send_drafts(db: DB, drafts: list) -> tuple[int, list[str]]:
    """Send approved drafts. Returns (count, errors)."""
    sent = 0
    errors = []

    for draft in drafts:
        email_id = draft.email_id
        draft_id = draft.id

        try:
            # Get original email
            email_result = await db.execute(select(Email).where(Email.id == email_id))
            email = email_result.scalar_one_or_none()
            if not email:
                raise RuntimeError(f'Email {email_id} not found')

            # Get token and send
            token_data = await get_token(db)
            await send_reply(
                token_data,
                email.gmail_id,
                email.from_email,
                email.subject or '',
                draft.body or (draft.edited_body or ''),
            )

            # Update status
            draft.sent_at = datetime.now(timezone.utc)
            email.status = 'sent'

            # Log auto-send
            db.add(AuditLog(
                id=str(uuid.uuid4()),
                email_id=email_id,
                action='auto_sent',
                created_at=datetime.now(timezone.utc),
            ))

            sent += 1
            logger.info(f'Auto-sent draft {draft_id} for email {email_id}')

        except Exception as e:
            error_msg = str(e)
            errors.append(f'Draft {draft_id}: {error_msg}')
            logger.error(f'Failed to send draft {draft_id}: {error_msg}')

    return sent, errors
