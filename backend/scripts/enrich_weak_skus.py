"""
Enrich search_text for all product_embeddings rows where search_text < 200 chars.

Unlike enrich_fishbowl.py (which targets Fishbowl-only rows and only expands
abbreviations), this script targets any weak SKU and generates richer catalog
terms from all available metadata in the DB (title, type, materials, capacities).

After running, re-run embed_products.py --all to regenerate embeddings.

Usage (from backend/):
    uv run python scripts/enrich_weak_skus.py                      # enrich all weak
    uv run python scripts/enrich_weak_skus.py --dry-run            # preview, no writes
    uv run python scripts/enrich_weak_skus.py --min-len=100        # only < 100 chars
    uv run python scripts/enrich_weak_skus.py --resume-from=APG-5  # skip already done

Override DB:
    DATABASE_URL=postgresql+asyncpg://... uv run python scripts/enrich_weak_skus.py
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import anthropic
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from sqlalchemy import text

HAIKU_MODEL = 'claude-haiku-4-5-20251001'
BATCH_SIZE = 25
SLEEP_BETWEEN = 1.0
DEFAULT_MIN_LEN = 200

ENRICH_PROMPT = """You are a packaging product catalog search specialist.

Given the product data below, output a single dense line of space-separated search terms
that will help customers find this product. Include: container type, closure/actuator type,
material(s), capacity/size, shape descriptors, application, and common synonym terms.

Rules:
- Use ONLY information present in the product data — never invent specs
- Include shape words explicitly: square, round, oval, cylinder, tube, flat, rectangular
- Expand material abbreviations: PET → PET polyethylene terephthalate, PP → PP polypropylene,
  PCR → PCR post-consumer recycled, HDPE → HDPE high-density polyethylene
- Include capacity in both ml and oz if both present
- Include neck size if present (e.g. 20/410 24/410)
- Add functional synonyms: lotion pump → pump dispenser actuator, sprayer → mist atomizer,
  airless → airless-pump vacuum-dispenser, dropper → dropper pipette
- At most 30 terms. No punctuation beyond hyphens, no explanation, no labels.

Product data:
"""


def _build_input(row: dict) -> str:
    parts = [f"SKU: {row['sku']}"]
    if row.get('title'):
        parts.append(f"Title: {row['title']}")
    if row.get('type'):
        parts.append(f"Type: {row['type']}")
    if row.get('materials'):
        parts.append(f"Materials: {row['materials']}")
    if row.get('capacities'):
        parts.append(f"Capacities: {row['capacities']}")
    if row.get('moq'):
        parts.append(f"MOQ: {row['moq']}")
    return '\n'.join(parts)


async def _enrich_one(client: anthropic.AsyncAnthropic, row: dict) -> str:
    product_input = _build_input(row)
    resp = await client.messages.create(
        model=HAIKU_MODEL,
        max_tokens=150,
        messages=[{'role': 'user', 'content': f'{ENRICH_PROMPT}{product_input}'}],
    )
    expanded = resp.content[0].text.strip()
    # Reject if Haiku returned explanation instead of terms
    if len(expanded) > 350 or any(phrase in expanded for phrase in ('I cannot', 'I don\'t', 'cannot generate', 'not a packaging')):
        return (row.get('title') or row['sku']).strip()
    # Prepend original title so it's always present in search_text
    title = (row.get('title') or '').strip()
    if title and title.lower() not in expanded.lower():
        return f"{title} {expanded}"
    return expanded


def _parse_args():
    dry_run = '--dry-run' in sys.argv
    min_len = DEFAULT_MIN_LEN
    resume_from = ''
    for arg in sys.argv[1:]:
        if arg.startswith('--min-len='):
            min_len = int(arg.split('=', 1)[1])
        elif arg.startswith('--resume-from='):
            resume_from = arg.split('=', 1)[1]
    return dry_run, min_len, resume_from


async def run(dry_run: bool = False, min_len: int = DEFAULT_MIN_LEN, resume_from: str = '') -> None:
    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        from app.core.config import settings
        db_url = settings.database_url

    engine = create_async_engine(db_url, poolclass=NullPool)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        result = await session.execute(text("""
            SELECT sku, title, type, materials, capacities, moq, search_text
            FROM product_embeddings
            WHERE (search_text IS NULL OR length(search_text) < :min_len)
              AND sku ILIKE 'APG-%'
              AND sku >= :resume_from
            ORDER BY sku
        """), {'min_len': min_len, 'resume_from': resume_from or ''})
        rows = [dict(r._mapping) for r in result.fetchall()]

    # Skip rows with no title at all — nothing to work with
    rows = [r for r in rows if (r.get('title') or '').strip()]

    print(f"Weak SKUs to enrich (search_text < {min_len} chars): {len(rows)}")
    if not rows:
        print("Nothing to do.")
        await engine.dispose()
        return

    if dry_run:
        print("DRY RUN — no writes\n")

    client = anthropic.AsyncAnthropic(api_key=os.environ.get('ANTHROPIC_API_KEY') or __import__('app.core.config', fromlist=['settings']).settings.anthropic_api_key)

    total_written = 0
    for i in range(0, len(rows), BATCH_SIZE):
        wave = rows[i:i + BATCH_SIZE]
        try:
            results = await asyncio.gather(*[_enrich_one(client, r) for r in wave])
        except Exception as e:
            print(f"\nError in wave {i // BATCH_SIZE + 1}: {e}")
            print(f"Resume with: --resume-from={wave[0]['sku']}")
            await engine.dispose()
            sys.exit(1)

        if dry_run:
            for row, new_text in zip(wave, results):
                print(f"[{row['sku']}]")
                print(f"  before ({len(row['search_text'] or '')} chars): {(row['search_text'] or '')[:80]}")
                print(f"  after  ({len(new_text)} chars): {new_text[:120]}")
                print()
        else:
            async with async_session() as session:
                for row, new_text in zip(wave, results):
                    await session.execute(
                        text("UPDATE product_embeddings SET search_text = :t, search_vector = :t WHERE sku = :s"),
                        {'t': new_text, 's': row['sku']},
                    )
                await session.commit()
            total_written += len(wave)

        print(f"  processed {min(i + BATCH_SIZE, len(rows))}/{len(rows)}", end='\r')

        if i + BATCH_SIZE < len(rows) and not dry_run:
            await asyncio.sleep(SLEEP_BETWEEN)

    if dry_run:
        print("\nDry run complete — no writes.")
    else:
        print(f"\nDone. {total_written} SKUs updated.")
        print("Next: uv run python scripts/embed_products.py --all")

    await engine.dispose()


if __name__ == '__main__':
    dry_run, min_len, resume_from = _parse_args()
    asyncio.run(run(dry_run=dry_run, min_len=min_len, resume_from=resume_from))
