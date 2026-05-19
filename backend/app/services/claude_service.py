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
- If the customer specifies an exact SKU, explicitly call it out by name first before suggesting alternatives.
- If the customer expresses general interest in a category or ongoing/inventory needs, present all relevant size variants and compatible accessories from the context.
- Name SKUs with material and size only — never include marketing or product line names (e.g. "Ageless Magic", "PurePulse", "Misty Glow"). Use SKU + specs only.
- If the same SKU appears in multiple size groups, list it only once in the most relevant group and note all its available sizes inline (e.g. "30ml & 50ml"). Do not omit other SKUs that belong to a size group just because another SKU covers that size.
- For dual/multi-chamber products: always read capacity as per-chamber. If the customer asks for "15ml x 2", they want 15ml per chamber (30ml total). A product listed as "15ml (7.5ml*2)" is NOT a match — it's 7.5ml per chamber. Prefer products where the per-chamber capacity matches the customer's stated per-chamber size. If no exact match exists, present the closest available and note the difference explicitly. Important: "Dual" in a product name means dual-chamber, not dual-actuator. Never infer actuator count from "Dual" alone — only exclude a dual-chamber product for actuator mismatch when the product explicitly states "dual actuator".
- Include ALL products from the context that are plausibly relevant — do not silently drop products. If a spec (neck size, actuator type) is not explicitly in the context but the product type clearly matches the customer request, include it. Only omit a product if it clearly contradicts the customer's stated requirement (e.g. wrong chamber count, wrong capacity range).
- If a product does not meet the customer's stated spec (actuator type, chamber count, capacity), omit it entirely — do not mention it even to explain why it was excluded. Applicator and closure type are hard requirements: a product listed with a dropper is never a valid match when the customer asked for a pump or sprayer, and vice versa. Do not include it even if the material, color, or capacity match perfectly. Exception: fine mist sprayers, crimpless sprayers, and perfume atomizers are valid pump equivalents — treat them as "pump" when the customer is sourcing a fragrance, essential oil, or perfume bottle.
- For capacity: if no exact match exists for a requested size, include the closest available size from the context and note the difference inline (e.g. "closest available: 60ml").
- Never add caveats like "neck finish not confirmed" or "needs verification" — include the product with the specs you have, or omit it entirely.
- Always use the full SKU exactly as it appears in the context. Never abbreviate or truncate SKU codes (e.g. APG-200493 must never appear as APG-493).
- **CRITICAL — Do not repeat already-suggested SKUs:** When the thread context lists "Already suggested SKUs", those products have ALREADY been recommended in a previous message in this thread. NEVER include them again. Only recommend NEW products from the context that were not previously suggested. If ALL relevant products were already suggested, do not repeat any — instead acknowledge the prior recommendations and advance to next steps (MOQ, shipping, samples, or ask for target quantity).

## Lead qualification
- If the customer mentions a quantity or desired MOQ, always compare it to the product MOQ in the context.
- If the customer's quantity is below the product MOQ, state the actual MOQ in one declarative sentence BEFORE listing products (e.g. "Our MOQ on this line is 10,000 units — above the range you mentioned."). This is a statement only — no question here.
- The single follow-up question at the end of the email handles MOQ confirmation (e.g. "Are you able to work with a 10,000-unit MOQ?"). Never ask a question in the MOQ statement and again at the end.
- If quantity is at or above MOQ, skip this and go straight to products.
- If product MOQ is not in the context but the customer mentions a quantity concern, acknowledge it briefly and note that MOQ will be confirmed with the team.

## Follow-up questions
- Exactly one, at the end. If multiple questions exist, pick the single most actionable one.
- Priority: (1) MOQ confirmation if gap is unaddressed AND not already asked above, (2) target annual quantity and target price if customer is ready to move forward or requesting samples, (3) ship-to destination.
- Never ask for product detail clarification — if a product isn't in the catalog, note it briefly and move on.
- Never make promises the agent cannot keep (e.g. "I'll follow up shortly") — only state what is confirmed.

## Thread awareness
- Read the full thread history before responding. Identify the latest message from the customer — that's the one you're replying to.
- If the thread already contains product recommendations, do NOT repeat them. Instead: answer follow-up questions (pricing, sampling, timeline), confirm details, or ask for target quantity/annual volume.
- If the customer is following up on a previous recommendation (e.g., "I'd like to order the ones you sent"), acknowledge the prior context and advance to next steps (MOQ, shipping, samples).
- Never reply to an old message in the thread — always address the most recent customer message.

## Formatting
- Use markdown: **bold** for SKUs, bullet lists (`-`) for product options grouped by size when listing multiple items.
- Each product on its own line. Never run products together in a single paragraph.

## General rules
- If no clear product match, acknowledge briefly and ask for more details.
- Write in the same language as the customer (English or Spanish).
- Never invent products or specs not in the context.
- Never include prices or pricing information in your response — pricing is shared separately by the sales team.
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


_CAP_RE = re.compile(r'\b\d+\s*(?:ml|oz|cc|g|l)\b', re.IGNORECASE)
_NECK_RE = re.compile(r'\b\d{2}/\d{3}\b')


def _has_confirmed_specs(p: dict) -> bool:
    """Skip products whose key specs (capacity) cannot be confirmed from the data.
    Accepts if capacities field is populated OR capacity is readable from the title.
    Manually-added products (flagged with _manual) are always included regardless of specs."""
    if p.get('_manual'):
        return True
    cap = str(p.get('capacities') or '').strip()
    if cap and cap not in ('nan', 'None', '-'):
        return True
    return bool(_CAP_RE.search(p.get('title') or ''))


def _extract_neck_sizes(p: dict) -> str:
    """Extract neck finish sizes from title or search_text (e.g. 20/410, 24/410)."""
    sources = [p.get('title') or '', p.get('search_text') or '']
    found = []
    seen = set()
    for src in sources:
        for m in _NECK_RE.finditer(src):
            v = m.group()
            if v not in seen:
                seen.add(v)
                found.append(v)
    return ', '.join(found)


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
        if p.get('type'):
            lines.append(f"Type: {p['type']}")
        if p.get('materials'):
            lines.append(f"Material: {p['materials']}")
        neck = _extract_neck_sizes(p)
        if neck:
            lines.append(f"Neck finish: {neck}")
        if p.get('capacities'):
            lines.append(f"Available sizes: {p['capacities']}")
        st = (p.get('search_text') or '').lower()
        if 'single actuator' in st:
            lines.append('Actuator: single actuator')
        elif 'dual actuator' in st:
            lines.append('Actuator: dual actuator')
        moq = p.get('moq') or ''
        lines.append(f"MOQ: {moq}")
        if p.get('image_url'):
            lines.append(f"Image URL: {p['image_url']}")

        blocks.append('\n'.join(lines))

    return "Relevant APG products:\n\n" + "\n\n".join(blocks)


def _build_thread_context(thread_history: list) -> str:
    if not thread_history:
        return ''
    lines = [f'Thread history ({len(thread_history)} message(s), oldest first):']
    for i, msg in enumerate(thread_history, start=1):
        sender = msg.from_name or msg.from_email
        lines.append(f"\n--- Message {i} of {len(thread_history)} ---")
        lines.append(f"From: {sender} <{msg.from_email}>")
        lines.append(f"Date: {msg.received_at}")
        lines.append(msg.body_text or '(no body)')
    return '\n'.join(lines)


def _extract_suggested_skus(thread_history: list) -> list[str]:
    """Extract SKU codes that appear in the thread body text (products already recommended)."""
    if not thread_history:
        return []
    sku_pattern = re.compile(r'\b(APG-\d{2,6}(?:/[A-Z0-9]+)?|[A-Z]{2,4}-\d{3,6})\b')
    suggested: set[str] = set()
    for msg in thread_history:
        body = msg.body_text or ''
        for sku in sku_pattern.findall(body):
            # Only include SKUs that look like APG product codes (2-6 digits after APG-)
            if '-APG-' in sku or sku.startswith('APG-') or sku.startswith('APG'):
                suggested.add(sku)
    return list(suggested)


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
    # Filter out products without confirmed specs, but keep manually-added ones
    confirmed = [p for p in products if _has_confirmed_specs(p)]
    # Strip internal _manual flag before building context
    confirmed = [{k: v for k, v in p.items() if k != '_manual'} for p in confirmed]
    product_context = _build_product_context(confirmed)
    thread_context = _build_thread_context(thread_history or [])
    suggested_skus = _extract_suggested_skus(thread_history or [])

    thread_section = f"\n\n{thread_context}\n" if thread_context else ''
    skus_section = '\n'.join(f'- {sku}' for sku in suggested_skus)
    skus_block = f'\n\n=== ALREADY SUGGESTED SKUs ===\n{skus_section}\n' if suggested_skus else ''

    user_message = f"""You are replying to a customer email within an existing conversation thread.

=== CURRENT EMAIL TO REPLY TO ===
Subject: {email_subject}
From the latest message in this thread:
---
{email_body}

=== PREVIOUS THREAD HISTORY ==={thread_section}{skus_block}
=== RELEVANT PRODUCTS ===
{product_context}

Write a professional reply email body (no subject line). Base it on the current email, considering the full thread context above. Do NOT repeat any of the already suggested SKUs listed above."""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        temperature=0,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    draft, score = _parse_response(response.content[0].text)
    return _inject_images(draft, confirmed), score


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
