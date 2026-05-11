"""
One-shot enrichment of search_text for Fishbowl-only products using Claude Haiku.

Fishbowl products land with ~66 chars of search_text (just the title), no materials,
no price tiers. The short text produces poor embeddings and degrades hybrid search.

This script expands search_text strictly from data already in the record —
no invented specs — so the embedding space is more discriminative.

After running this, re-run embed_products.py --all to regenerate embeddings.

Usage (from backend/):
    uv run python scripts/enrich_fishbowl.py            # enrich all Fishbowl-only rows
    uv run python scripts/enrich_fishbowl.py --dry-run  # print enriched text, no writes
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import anthropic
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from sqlalchemy import text

from app.core.config import settings

HAIKU_MODEL = 'claude-haiku-4-5-20251001'
BATCH_SIZE = 20        # Haiku calls per concurrent wave
SLEEP_BETWEEN = 1.0    # seconds between waves (rate limit buffer)

ENRICH_PROMPT = """You are a packaging product catalog normalizer.

Given the raw product data below, output a single line of space-separated terms that expands
abbreviations and adds synonyms strictly for what is EXPLICITLY stated. Never infer or add
any term not grounded in the input.

Expansion rules (apply ONLY if the abbreviated form is present):
- PP → polypropylene
- HDPE → high-density polyethylene
- PET → polyethylene terephthalate
- ABS → acrylonitrile butadiene styrene
- PE → polyethylene
- AS → acrylonitrile styrene
- 1 Actuator / single actuator → single-actuator
- 2 Actuator / dual actuator → dual-actuator
- 1 Chamber / single chamber → single-chamber
- 2 Chamber / dual chamber → dual-chamber two-chamber
- oz → ounce (keep original ml/oz values as-is)
- Airless → airless-pump airless-dispenser (ONLY if "airless" is in the title)
- Lotion pump → lotion-pump pump-dispenser (ONLY if "lotion pump" is in the title)
- Sprayer / mist → sprayer fine-mist (ONLY if in the title)

Hard rules:
- Do NOT add end-use terms (serum, lotion, skincare) unless they appear in the title
- Do NOT infer container category from material (HDPE bottle ≠ airless pump)
- Do NOT infer material from container type (airless bottle ≠ ABS/PP unless stated)
- Do NOT add color, finish, or decoration terms not in the input
- At most 20 terms. No punctuation beyond hyphens, no labels, no explanation.

Product data:
"""


async def _enrich_one(client: anthropic.AsyncAnthropic, row: dict) -> str:
    raw = f"SKU: {row['sku']}\nTitle: {row['title'] or ''}"
    if row.get('dimensions'):
        raw += f"\nDimensions: {row['dimensions']}"
    if row.get('type'):
        raw += f"\nType: {row['type']}"

    resp = await client.messages.create(
        model=HAIKU_MODEL,
        max_tokens=120,
        messages=[{'role': 'user', 'content': f'{ENRICH_PROMPT}{raw}'}],
    )
    return resp.content[0].text.strip()


async def run(dry_run: bool = False, resume_from: str = '') -> None:
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        result = await session.execute(text("""
            SELECT sku, title, type, dimensions, search_text
            FROM product_embeddings
            WHERE materials IS NULL AND price_10k IS NULL AND sku LIKE 'APG-%'
              AND sku >= :resume_from
            ORDER BY sku
        """), {'resume_from': resume_from})
        rows = [dict(r._mapping) for r in result.fetchall()]

    print(f"Fishbowl-only products to enrich: {len(rows)}")
    if not rows:
        print("Nothing to do.")
        await engine.dispose()
        return

    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    # Skip rows with no meaningful title (can't enrich without source data)
    rows = [r for r in rows if len((r.get('title') or '').strip()) > 5]
    print(f"  (after filtering blank titles: {len(rows)} to process)")

    total_written = 0
    for i in range(0, len(rows), BATCH_SIZE):
        wave = rows[i:i + BATCH_SIZE]
        results = await asyncio.gather(*[_enrich_one(client, r) for r in wave])

        batch_updates = []
        for row, new_text in zip(wave, results):
            combined = f"{row['title'] or ''} {new_text}".strip()
            batch_updates.append((row['sku'], combined))
            if dry_run:
                print(f"\n[{row['sku']}]")
                print(f"  before: {row['search_text'] or '(empty)'}")
                print(f"  after:  {combined}")

        if not dry_run:
            async with async_session() as session:
                for sku, new_text in batch_updates:
                    await session.execute(
                        text("UPDATE product_embeddings SET search_text = :t, search_vector = :t WHERE sku = :s"),
                        {'t': new_text, 's': sku},
                    )
                await session.commit()
            total_written += len(batch_updates)

        print(f"  processed {min(i + BATCH_SIZE, len(rows))}/{len(rows)}", end='\r')
        if i + BATCH_SIZE < len(rows):
            await asyncio.sleep(SLEEP_BETWEEN)

    if dry_run:
        print("\nDry run — no writes.")
    else:
        print(f"\nDone. {total_written} products updated.")
        print("Now run: uv run python scripts/embed_products.py --all")

    await engine.dispose()


if __name__ == '__main__':
    dry_run = '--dry-run' in sys.argv
    resume_from = ''
    for arg in sys.argv:
        if arg.startswith('--resume-from='):
            resume_from = arg.split('=', 1)[1]
    asyncio.run(run(dry_run=dry_run, resume_from=resume_from))
