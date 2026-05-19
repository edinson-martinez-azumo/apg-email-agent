import uuid
import datetime
import json
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func
from app.core.deps import DB
from app.db.models.email import Email
from app.db.models.draft import Draft
from app.db.models.product_match import ProductMatch
from app.db.models.audit_log import AuditLog
from app.schemas.email import EmailRead, EmailListResponse

router = APIRouter()


# ─── Pydantic schemas ──────────────────────────────────────────────────────────


class ProductValidationResponse(BaseModel):
    suggested: list[dict]
    confirmed: list[dict]
    rejected: list[dict]

    model_config = {'from_attributes': True}


class ValidateProductsRequest(BaseModel):
    confirmed: list[str]
    rejected: list[str]


class AddProductRequest(BaseModel):
    sku: str


class GenerateWithProductsRequest(BaseModel):
    products: list[str] = []


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
    emails = list(result.scalars().all())

    # Include thread siblings so the UI can render full thread context
    if status and emails:
        thread_ids = {e.thread_id for e in emails if e.thread_id}
        if thread_ids:
            seen_ids = {e.id for e in emails}
            siblings = await db.execute(
                select(Email).where(
                    Email.thread_id.in_(thread_ids),
                    Email.id.not_in(seen_ids),
                )
            )
            emails = emails + list(siblings.scalars().all())

    return {'items': emails, 'total': total or 0, 'page': page, 'size': size}


@router.post('/sync')
async def sync_emails(db: DB):
    """Pull unread Gmail messages and save new ones to DB."""
    from app.services.gmail_service import list_unread_messages, get_message, parse_message, get_token
    from sqlalchemy.exc import IntegrityError

    try:
        token_data = await get_token(db)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    messages = list_unread_messages(token_data, max_results=50)
    imported = 0
    skipped = 0

    for stub in messages:
        msg = get_message(token_data, stub['id'])
        parsed = parse_message(msg)

        existing = await db.scalar(select(Email).where(Email.gmail_id == parsed['gmail_id']))
        if existing:
            skipped += 1
            continue

        email = Email(id=str(uuid.uuid4()), status='pending', **parsed)
        db.add(email)
        try:
            await db.flush()
            imported += 1
        except IntegrityError:
            await db.rollback()
            skipped += 1

    await db.commit()
    return {'imported': imported, 'skipped': skipped, 'total_found': len(messages)}


async def _get_thread(email: Email, db: DB) -> list[Email]:
    """Return all emails in the same thread ordered oldest-first, excluding current email."""
    if not email.thread_id:
        return []
    result = await db.execute(
        select(Email)
        .where(Email.thread_id == email.thread_id, Email.id != email.id)
        .order_by(Email.received_at.asc())
    )
    return result.scalars().all()


@router.get('/{email_id}', response_model=EmailRead)
async def get_email(email_id: str, db: DB):
    email = await db.get(Email, email_id)
    if not email:
        raise HTTPException(status_code=404, detail='Email not found')
    thread = await _get_thread(email, db)
    data = EmailRead.model_validate(email)
    data.thread = thread
    return data


@router.post('/{email_id}/generate')
async def generate_draft_for_email(email_id: str, db: DB):
    """Trigger or re-generate an AI draft for this email."""
    from app.services.embedding_service import search_products
    from app.services.claude_service import generate_draft as ai_generate

    email = await db.get(Email, email_id)
    if not email:
        raise HTTPException(status_code=404, detail='Email not found')

    thread = await _get_thread(email, db)

    # Check for existing confirmed products
    existing_validation = await db.execute(
        select(ProductMatch).where(
            ProductMatch.email_id == email_id,
            ProductMatch.status == 'confirmed',
        )
    )
    confirmed_matches = existing_validation.scalars().all()

    if confirmed_matches:
        # Use only confirmed products
        query = f"{email.subject or ''} {email.body_text or ''}".strip()
        all_products = await search_products(query, db, top_k=12)
        confirmed_skus = {m.sku for m in confirmed_matches}
        products = [p for p in all_products if p['sku'] in confirmed_skus]
    else:
        products = []

    if not products:
        try:
            query = f"{email.subject or ''} {email.body_text or ''}".strip()
            products = await search_products(query, db, top_k=12)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f'search_products error: {type(e).__name__}: {e}')

    try:
        draft_body, confidence_score = ai_generate(
        email.subject or '',
        email.body_text or '',
        products,
        thread_history=thread,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'generate_draft error: {type(e).__name__}: {e}')

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


@router.get('/{email_id}/intent')
async def get_email_intent(email_id: str, db: DB):
    """Extract what the customer is asking for as bullet points (Haiku, fast)."""
    import anthropic
    from app.core.config import settings

    email = await db.get(Email, email_id)
    if not email:
        raise HTTPException(status_code=404, detail='Email not found')

    # Check if we already extracted intent for this email
    existing = await db.execute(
        select(AuditLog).where(
            AuditLog.email_id == email_id,
            AuditLog.action == 'intent_extracted',
        ).order_by(AuditLog.created_at.desc()).limit(1)
    )
    cached = existing.scalar_one_or_none()
    if cached and cached.detail:
        detail_data = cached.detail
        if isinstance(detail_data, list):
            return {'bullets': detail_data}
        elif isinstance(detail_data, str):
            try:
                parsed = json.loads(detail_data)
                return {'bullets': parsed if isinstance(parsed, list) else parsed.get('bullets', [])}
            except (json.JSONDecodeError, TypeError):
                return {'bullets': []}
        return {'bullets': []}

    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    prompt = (
        "Extract what the customer is asking for in 3–5 bullet points.\n"
        "Focus on: product type, capacity/size, material, quantity, special requirements.\n"
        "Return ONLY bullet points, one per line, starting with '- '.\n"
        "Be specific and concise. No explanation. No intro line.\n\n"
        f"Subject: {email.subject or ''}\n\n{email.body_text or ''}"
    )
    response = await client.messages.create(
        model='claude-haiku-4-5-20251001',
        max_tokens=200,
        messages=[{'role': 'user', 'content': prompt}],
    )
    text = response.content[0].text.strip()
    bullets = [l[2:].strip() for l in text.splitlines() if l.strip().startswith('- ')]

    # Cache the result
    db.add(AuditLog(
        id=str(uuid.uuid4()),
        email_id=email_id,
        action='intent_extracted',
        detail=json.dumps(bullets),
        created_at=datetime.datetime.now(datetime.timezone.utc),
    ))
    await db.commit()

    return {'bullets': bullets}


@router.post('/{email_id}/discard')
async def discard_email(email_id: str, db: DB):
    email = await db.get(Email, email_id)
    if not email:
        raise HTTPException(status_code=404, detail='Email not found')
    email.status = 'discarded'
    db.add(AuditLog(
        id=str(uuid.uuid4()),
        email_id=email_id,
        action='discarded',
        created_at=datetime.datetime.now(datetime.timezone.utc),
    ))
    await db.commit()
    return {'status': 'discarded'}


# ─── Detected products (shown in draft editor) ─────────────────────────────────


class DetectedProductItem(BaseModel):
    sku: str
    title: str | None
    score: float | None
    status: str | None


class CustomerIntentItem(BaseModel):
    text: str


class DetectedProductsResponse(BaseModel):
    intent: list[CustomerIntentItem]
    products: list[DetectedProductItem]
    model_config = {'from_attributes': True}


@router.get('/{email_id}/detected-products', response_model=DetectedProductsResponse)
async def get_detected_products(email_id: str, db: DB):
    """Get AI-detected products and customer intent bullets for the draft editor."""
    email = await db.get(Email, email_id)
    if not email:
        raise HTTPException(status_code=404, detail='Email not found')

    # Get detected products (suggested = None status)
    result = await db.execute(
        select(ProductMatch).where(ProductMatch.email_id == email_id)
    )
    all_matches = result.scalars().all()

    products = []
    for match in all_matches:
        products.append(DetectedProductItem(
            sku=match.sku,
            title=match.title,
            score=match.score,
            status=match.status,
        ))

    # Get customer intent bullets (cached if available)
    intent_result = await db.execute(
        select(AuditLog).where(
            AuditLog.email_id == email_id,
            AuditLog.action == 'intent_extracted',
        ).order_by(AuditLog.created_at.desc()).limit(1)
    )
    intent_entry = intent_result.scalar_one_or_none()

    intent = []
    if intent_entry and intent_entry.detail:
        intent_data = intent_entry.detail
        if isinstance(intent_data, str):
            try:
                import json
                parsed = json.loads(intent_data)
                if isinstance(parsed, list):
                    intent = [CustomerIntentItem(text=str(b)) for b in parsed]
                elif isinstance(parsed, dict) and 'bullets' in parsed:
                    intent = [CustomerIntentItem(text=str(b)) for b in parsed['bullets']]
            except (json.JSONDecodeError, TypeError):
                pass
        elif isinstance(intent_data, list):
            intent = [CustomerIntentItem(text=str(b)) for b in intent_data]

    return DetectedProductsResponse(intent=intent, products=products)


def _serialize_product_match(match: ProductMatch) -> dict:
    """Convert a ProductMatch ORM object to a plain dict for API responses."""
    return {
        'id': match.id,
        'sku': match.sku,
        'title': match.title,
        'score': match.score,
        'status': match.status,
    }


# ─── Product validation endpoints ─────────────────────────────────────────────


@router.get('/{email_id}/products/validation', response_model=ProductValidationResponse)
async def get_product_validation(email_id: str, db: DB):
    """Get product validation state for an email."""
    email = await db.get(Email, email_id)
    if not email:
        raise HTTPException(status_code=404, detail='Email not found')

    result = await db.execute(
        select(ProductMatch).where(ProductMatch.email_id == email_id)
    )
    all_matches = result.scalars().all()

    suggested = []
    confirmed = []
    rejected = []

    for match in all_matches:
        data = _serialize_product_match(match)
        if match.status == 'confirmed':
            confirmed.append(data)
        elif match.status == 'rejected':
            rejected.append(data)
        else:
            suggested.append(data)

    return ProductValidationResponse(
        suggested=suggested,
        confirmed=confirmed,
        rejected=rejected,
    )


@router.post('/{email_id}/products/validate')
async def validate_products(email_id: str, body: ValidateProductsRequest, db: DB):
    """Update product validation state for an email."""
    email = await db.get(Email, email_id)
    if not email:
        raise HTTPException(status_code=404, detail='Email not found')

    for sku in body.confirmed:
        result = await db.execute(
            select(ProductMatch).where(
                ProductMatch.email_id == email_id,
                ProductMatch.sku == sku,
            )
        )
        match = result.scalar_one_or_none()
        if match:
            match.status = 'confirmed'

    for sku in body.rejected:
        result = await db.execute(
            select(ProductMatch).where(
                ProductMatch.email_id == email_id,
                ProductMatch.sku == sku,
            )
        )
        match = result.scalar_one_or_none()
        if match:
            match.status = 'rejected'

    await db.commit()

    # Return updated state
    result = await db.execute(
        select(ProductMatch).where(ProductMatch.email_id == email_id)
    )
    all_matches = result.scalars().all()

    suggested = []
    confirmed = []
    rejected = []
    for match in all_matches:
        data = _serialize_product_match(match)
        if match.status == 'confirmed':
            confirmed.append(data)
        elif match.status == 'rejected':
            rejected.append(data)
        else:
            suggested.append(data)

    return ProductValidationResponse(
        suggested=suggested,
        confirmed=confirmed,
        rejected=rejected,
    )


@router.post('/{email_id}/products/add')
async def add_product(email_id: str, body: AddProductRequest, db: DB):
    """Add a new product to the email's product list (auto-confirmed)."""
    email = await db.get(Email, email_id)
    if not email:
        raise HTTPException(status_code=404, detail='Email not found')

    # Check product exists in products table
    from app.db.models.product import Product
    product_result = await db.execute(
        select(Product).where(Product.sku == body.sku)
    )
    product = product_result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail=f'Product {body.sku} not found')

    # Check if already exists
    existing = await db.execute(
        select(ProductMatch).where(
            ProductMatch.email_id == email_id,
            ProductMatch.sku == body.sku,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail='Product already added')

    db.add(ProductMatch(
        id=str(uuid.uuid4()),
        email_id=email_id,
        sku=body.sku,
        title=product.title,
        score=None,
        status='confirmed',
    ))

    await db.commit()

    return {'status': 'ok', 'sku': body.sku}


@router.post('/{email_id}/generate-with-products')
async def generate_with_products(email_id: str, body: GenerateWithProductsRequest, db: DB):
    """Generate draft using only confirmed products (and optionally user-added ones)."""
    email = await db.get(Email, email_id)
    if not email:
        raise HTTPException(status_code=404, detail='Email not found')

    thread = await _get_thread(email, db)

    # Get confirmed products from validation
    result = await db.execute(
        select(ProductMatch).where(
            ProductMatch.email_id == email_id,
            ProductMatch.status == 'confirmed',
        )
    )
    confirmed_matches = result.scalars().all()

    # Add any extra products from request
    extra_skus = set(body.products)
    for match in confirmed_matches:
        extra_skus.add(match.sku)

    # Search for product details
    from app.services.embedding_service import search_products
    try:
        query = f"{email.subject or ''} {email.body_text or ''}".strip()
        all_products = await search_products(query, db, top_k=12)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'search_products error: {type(e).__name__}: {e}')

    # Filter to only confirmed/user-added SKUs
    confirmed_products = [p for p in all_products if p['sku'] in extra_skus]

    if not confirmed_products:
        raise HTTPException(status_code=400, detail='No confirmed products selected')

    try:
        from app.services.claude_service import generate_draft as ai_generate
        draft_body, confidence_score = ai_generate(
            email.subject or '',
            email.body_text or '',
            confirmed_products,
            thread_history=thread,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'generate_draft error: {type(e).__name__}: {e}')

    # Save draft
    existing = await db.execute(select(Draft).where(Draft.email_id == email_id))
    draft = existing.scalar_one_or_none()
    if draft:
        draft.body = draft_body
        draft.edited_body = None
        draft.confidence_score = confidence_score
    else:
        draft = Draft(
            id=str(uuid.uuid4()),
            email_id=email_id,
            body=draft_body,
            edited_body=None,
            confidence_score=confidence_score,
        )
        db.add(draft)

    # Update product match statuses
    confirmed_skus = set(body.products)
    for match in confirmed_matches:
        match.status = 'confirmed'
        confirmed_skus.add(match.sku)

    # Mark unmatched suggested products as rejected
    for match in confirmed_matches:
        if match.sku not in confirmed_skus:
            match.status = 'rejected'

    email.status = 'draft_ready'
    db.add(AuditLog(
        id=str(uuid.uuid4()),
        email_id=email_id,
        action='generated',
        created_at=datetime.datetime.now(datetime.timezone.utc),
    ))
    await db.commit()

    return {'status': 'ok', 'draft_preview': draft_body[:200]}
