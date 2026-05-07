import re
import anthropic
from app.core.config import settings

client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

SYSTEM_PROMPT = """You are a sales assistant for APackaging Group (APG), a cosmetic and personal care packaging manufacturer based in Azusa, California.

## Tone
- Warm but brief. Match a human sales rep.
- 3–5 sentences max unless more is genuinely needed.

## Product recommendations
- Lead with options, not questions — offer first, ask second.
- If the customer specifies an exact SKU or size, confirm that item only and suggest 1–2 compatible accessories at most.
- If the customer expresses general interest in a category or ongoing/inventory needs, present all relevant size variants and compatible accessories from the context.
- Name SKUs with one key spec each; skip specs the customer didn't ask about.

## Lead qualification
- If the customer's stated quantity is clearly below the product MOQ (e.g. they say 1,000 and MOQ is 10,000), address the MOQ gap first in one short sentence before listing products. Ask if they're comfortable with the minimum.
- If quantity is at or above MOQ, skip this and go straight to products.

## Follow-up questions
- At most one, and only after presenting options or addressing MOQ.
- Focus on: target quantity or ship-to destination.

## General rules
- If no clear product match, acknowledge briefly and ask for more details.
- Write in the same language as the customer (English or Spanish).
- Never invent products, prices, or specs not in the context.
- Sign off as: APG Sales Team | APackaging Group | apackaginggroup.com

Output format — two parts, nothing else:
1. First line exactly: CONFIDENCE: <1-5>
   Score meaning (use one decimal, e.g. 4.2):
   5.0 = Products perfectly match the customer's exact need
   4.0 = Good match, minor gaps
   3.0 = Partial match, some relevant products found
   2.0 = Weak match, products are tangentially related
   1.0 = No match found, responding generally
2. The email body starting on the very next line — no blank line between score and body
"""


def _fmt_price(val: object) -> str:
    if val is None or str(val).strip() in ('', 'nan', 'None'):
        return ''
    try:
        return f'${float(val):.4g}'
    except (TypeError, ValueError):
        return ''


def _build_product_context(products: list[dict]) -> str:
    if not products:
        return "No specific product matches found — respond generally about APG's catalog."

    blocks = []
    for p in products:
        stock = ' [IN STOCK]' if p.get('in_stock') else ''
        lines = [
            f"SKU: {p['sku']}{stock}",
            f"Name: {p['title']}",
        ]
        if p.get('materials'):
            lines.append(f"Material: {p['materials']}")
        if p.get('capacities'):
            lines.append(f"Available sizes: {p['capacities']}")
        moq = p.get('moq') or ''
        lines.append(f"MOQ: {moq}")

        tiers = [
            ('10k', _fmt_price(p.get('price_10k'))),
            ('25k', _fmt_price(p.get('price_25k'))),
            ('50k', _fmt_price(p.get('price_50k'))),
            ('100k', _fmt_price(p.get('price_100k'))),
        ]
        tier_str = ' | '.join(f'@{qty} {price}' for qty, price in tiers if price)
        if tier_str:
            lines.append(f"Pricing: {tier_str}")
        else:
            lines.append("Pricing: available upon request")

        blocks.append('\n'.join(lines))

    return "Relevant APG products:\n\n" + "\n\n".join(blocks)


def _build_thread_context(thread_history: list) -> str:
    if not thread_history:
        return ''
    lines = ['Previous emails in this thread (oldest first):']
    for msg in thread_history:
        sender = msg.from_name or msg.from_email
        lines.append(f"\n--- From: {sender} <{msg.from_email}> ---")
        lines.append(msg.body_text or '(no body)')
    return '\n'.join(lines)


EXTRACT_PROMPT = """You are a search query builder for a packaging product catalog.

Given a customer email, extract the key product search terms in normalized form.
Convert any imperial measurements to metric (e.g. 16oz → 473ml, 8oz → 237ml, 1oz → 30ml).
Output a single line of space-separated search terms — no explanation, no punctuation, no labels.

Examples:
- "need 16oz foaming hand soap bottle" → foamer bottle 473ml PET
- "looking for 1oz airless pump for serum" → airless pump bottle 30ml serum
- "APG-40D-450-WT availability and pricing" → APG-40D-450-WT foamer bottle 450ml
"""


async def extract_search_terms(email_subject: str, email_body: str) -> str:
    """First Claude call: normalize customer email into catalog search terms."""
    async_client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    response = await async_client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=100,
        system=EXTRACT_PROMPT,
        messages=[{"role": "user", "content": f"Subject: {email_subject}\n\n{email_body}"}],
    )
    return response.content[0].text.strip()


def generate_draft(
    email_subject: str,
    email_body: str,
    products: list[dict],
    thread_history: list | None = None,
) -> tuple[str, float]:
    """
    Generate a reply draft given pre-fetched products and optional thread history.
    Returns (draft_body, confidence_score 1-5).
    """
    product_context = _build_product_context(products)
    thread_context = _build_thread_context(thread_history or [])

    thread_section = f"\n\n{thread_context}\n" if thread_context else ''

    user_message = f"""Customer email:
Subject: {email_subject}
---
{email_body}
{thread_section}
---
{product_context}

Please write a professional reply email body (no subject line needed)."""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    return _parse_response(response.content[0].text)


def _parse_response(text: str) -> tuple[str, float]:
    lines = text.strip().split('\n')
    score = 3.0
    if lines and lines[0].upper().startswith('CONFIDENCE:'):
        try:
            score = max(1.0, min(5.0, float(lines[0].split(':')[1].strip())))
            text = '\n'.join(lines[1:]).lstrip('\n')
        except (ValueError, IndexError):
            pass
    return _strip_preamble(text), score


def _strip_preamble(text: str) -> str:
    text = re.sub(r'^(?:here is [^\n]*[:]\s*\n+|---\s*\n+)+', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\n+---\s*$', '', text)
    return text.strip()
