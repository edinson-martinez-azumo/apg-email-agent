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
- Name SKUs with material and size only — never include marketing or product line names (e.g. "Ageless Magic", "PurePulse", "Misty Glow"). Use SKU + specs only.
- If the same SKU appears in multiple size groups, list it only once in the most relevant group and note all its available sizes inline (e.g. "30ml & 50ml"). Do not omit other SKUs that belong to a size group just because another SKU covers that size.

## Lead qualification
- If the customer's stated quantity is clearly below the product MOQ (e.g. they say 1,000 and MOQ is 10,000), address the MOQ gap first in one short sentence before listing products. Ask if they're comfortable with the minimum.
- If quantity is at or above MOQ, skip this and go straight to products.

## Follow-up questions
- Exactly one, at the end. If multiple questions exist, pick the single most actionable one.
- Priority: (1) MOQ confirmation if gap is unaddressed, (2) target annual quantity and target price if customer is ready to move forward or requesting samples, (3) ship-to destination.
- Never ask for product detail clarification — if a product isn't in the catalog, note it briefly and move on.
- Never make promises the agent cannot keep (e.g. "I'll follow up shortly") — only state what is confirmed.

## Thread context
- If the thread history already contains product recommendations, do not repeat them. Focus on advancing the conversation: answer pricing questions, confirm sampling options, or ask for target quantity/annual volume to work toward competitive pricing.

## Formatting
- Use markdown: **bold** for SKUs, bullet lists (`-`) for product options grouped by size when listing multiple items.
- Each product on its own line. Never run products together in a single paragraph.

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
        if p.get('image_url'):
            lines.append(f"Image URL: {p['image_url']}")

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


def _inject_images(draft: str, products: list[dict]) -> str:
    """Insert image markdown below each SKU mention line; deduplicate repeated SKU bullets."""
    image_map = {p['sku']: p['image_url'] for p in products if p.get('image_url')}
    all_skus = {p['sku'] for p in products}

    lines = draft.split('\n')
    result = []
    seen_skus: set[str] = set()

    for line in lines:
        # Detect bullet lines that mention a known SKU
        matched_sku = next((s for s in all_skus if s in line), None)

        if matched_sku:
            if matched_sku in seen_skus:
                # Skip this bullet and any immediately following image line
                continue
            seen_skus.add(matched_sku)

        result.append(line)

        if matched_sku and image_map.get(matched_sku) and f'![{matched_sku}]' not in line:
            result.append(f'![{matched_sku}]({image_map[matched_sku]})')

    return _remove_empty_headings('\n'.join(result))


def _remove_empty_headings(text: str) -> str:
    """Remove markdown headings (## or **bold:**) that have no product bullets below them."""
    lines = text.split('\n')
    result = []
    i = 0
    while i < len(lines):
        line = lines[i]
        is_heading = re.match(r'^#{1,3} |^\*\*[^*]+\*\*\s*$', line)
        if is_heading:
            # Look ahead: is the next non-empty line another heading or end of text?
            j = i + 1
            while j < len(lines) and lines[j].strip() == '':
                j += 1
            next_is_heading_or_end = j >= len(lines) or bool(re.match(r'^#{1,3} |\*\*[^*]+\*\*\s*$', lines[j]))
            if next_is_heading_or_end:
                i = j  # skip this heading and its trailing blanks
                continue
        result.append(line)
        i += 1
    return '\n'.join(result)


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

    draft, score = _parse_response(response.content[0].text)
    return _inject_images(draft, products), score


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
