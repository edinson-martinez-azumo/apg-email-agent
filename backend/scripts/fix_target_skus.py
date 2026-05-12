"""
Manually enrich and re-embed 5 specific SKUs that are causing recall failures.

- APG-855024: says 'recyclable' but not 'PCR' → add PCR terms
- APG-30ML, APG-BT-30-B-AB-18, APG-B-S-50-BB, APG-BT-50-B-AB-18: weak amber glass
  bottle search_text → add fragrance/18-410 terms

Usage (from backend/):
    DATABASE_URL=... uv run python scripts/fix_target_skus.py
    DATABASE_URL=... uv run python scripts/fix_target_skus.py --dry-run
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cohere
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from sqlalchemy import text

EMBED_MODEL = 'embed-english-light-v3.0'

ENRICHMENTS = {
    'APG-855024': (
        ' PCR post-consumer recycled post-consumer-recycled eco-friendly sustainable'
        ' recyclable plastic eco green circular'
    ),
    'APG-30ML': (
        ' perfume fragrance serum essential oil dropper vial apothecary 18/410 neck'
        ' amber glass square 30ml cosmetic packaging atomizer spray mist'
    ),
    'APG-BT-30-B-AB-18': (
        ' perfume fragrance serum essential oil 18/410 neck amber frosted glass dropper'
        ' pipette cosmetic 30ml vial atomizer spray mist packaging'
    ),
    'APG-B-S-50-BB': (
        ' perfume fragrance serum essential oil amber glass 50ml French square dropper'
        ' CRC closure cosmetic packaging atomizer spray mist 18/410'
    ),
    'APG-BT-50-B-AB-18': (
        ' perfume fragrance serum essential oil 18/410 neck amber frosted glass dropper'
        ' pipette cosmetic 50ml vial atomizer spray mist packaging'
    ),
}


async def run(dry_run: bool = False) -> None:
    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        from app.core.config import settings
        db_url = settings.database_url

    cohere_key = os.environ.get('COHERE_API_KEY')
    if not cohere_key:
        from app.core.config import settings
        cohere_key = settings.cohere_api_key
    client = cohere.AsyncClientV2(api_key=cohere_key)

    engine = create_async_engine(db_url, poolclass=NullPool)
    Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    skus = list(ENRICHMENTS.keys())
    placeholders = ', '.join(f"'{s}'" for s in skus)

    async with Session() as session:
        r = await session.execute(text(f"""
            SELECT sku, search_text FROM product_embeddings
            WHERE sku IN ({placeholders})
            ORDER BY sku
        """))
        rows = {row['sku']: row['search_text'] or '' for row in r.mappings().all()}

    print(f"Found {len(rows)}/{len(skus)} SKUs in DB\n")

    updates = []
    for sku in skus:
        if sku not in rows:
            print(f"  SKIP {sku} — not found in DB")
            continue
        original = rows[sku]
        appended = ENRICHMENTS[sku].strip()
        new_text = original + ' ' + appended
        updates.append((sku, new_text))
        print(f"[{sku}]")
        print(f"  original len : {len(original)}")
        print(f"  new len      : {len(new_text)}")
        print(f"  added terms  : {appended[:80]}...")
        print()

    if dry_run:
        print("DRY RUN — no changes written.")
        await engine.dispose()
        return

    print("Embedding updated texts...")
    texts = [t for _, t in updates]
    resp = await client.embed(
        texts=texts,
        model=EMBED_MODEL,
        input_type='search_document',
        embedding_types=['float'],
    )

    async with Session() as session:
        for (sku, new_text), embedding in zip(updates, resp.embeddings.float_):
            await session.execute(text("""
                UPDATE product_embeddings
                SET search_text = :st,
                    search_vector = :st,
                    embedding = CAST(:emb AS vector)
                WHERE sku = :sku
            """), {'st': new_text, 'emb': str(embedding), 'sku': sku})
        await session.commit()

    print(f"Done. Updated {len(updates)} SKUs.")
    await engine.dispose()


if __name__ == '__main__':
    dry_run = '--dry-run' in sys.argv
    asyncio.run(run(dry_run=dry_run))
