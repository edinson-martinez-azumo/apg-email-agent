"""
Generate Cohere embeddings for all products and upsert into product_embeddings with full metadata.

Usage (from backend/):
    uv run python scripts/embed_products.py           # only new SKUs
    uv run python scripts/embed_products.py --all     # re-embed + update metadata for all

Requirements:
    - COHERE_API_KEY and DATABASE_URL set in .env.local
    - Migration 0010 applied
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cohere
import httpx
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy import text

from app.core.config import settings
from app.services.product_service import _load_products
from app.db.models.product_embedding import ProductEmbedding

EMBED_MODEL = 'embed-english-light-v3.0'
BATCH_SIZE = 96
SLEEP_S = 8.0

STR_COLS = ['sku', 'title', 'search_text', 'type', 'materials', 'moq', 'fb_moq',
            'capacities', 'price_base', 'price_10k', 'price_25k', 'price_50k', 'price_100k',
            'image_url', 'dimensions']


def _clean(val) -> str:
    if val is None:
        return ''
    s = str(val).strip()
    return '' if s.lower() == 'nan' else s


async def run(force_all: bool = False, resume_batch: int = 0) -> None:
    df = _load_products()
    for col in STR_COLS:
        if col not in df.columns:
            df[col] = ''
        df[col] = df[col].apply(_clean)
    df['in_stock'] = df.get('in_stock', False).fillna(False).astype(bool)

    records = df[STR_COLS + ['in_stock']].drop_duplicates('sku').to_dict('records')

    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # Pull enriched search_text from DB (written by enrich_fishbowl.py) and
    # overlay it on the Excel records so embeddings use the richer text.
    async with async_session() as session:
        db_result = await session.execute(
            text('SELECT sku, search_text FROM product_embeddings WHERE search_text IS NOT NULL')
        )
        db_search_text = {row[0]: row[1] for row in db_result.fetchall()}

    sku_to_record = {r['sku']: r for r in records}
    for sku, db_text in db_search_text.items():
        if sku in sku_to_record and db_text:
            sku_to_record[sku]['search_text'] = db_text
    records = list(sku_to_record.values())

    if force_all:
        pending = records
    else:
        async with async_session() as session:
            result = await session.execute(text('SELECT sku FROM product_embeddings WHERE price_10k IS NOT NULL'))
            done = {row[0] for row in result.fetchall()}
        pending = [r for r in records if r['sku'] not in done]

    if resume_batch:
        pending = pending[resume_batch * BATCH_SIZE:]
        print(f"Resuming from batch {resume_batch} (skipping {resume_batch * BATCH_SIZE} records)")

    n_batches = (len(pending) + BATCH_SIZE - 1) // BATCH_SIZE
    print(f"Total: {len(records)}  Pending: {len(pending)} → {n_batches} batches")

    if not pending:
        print("All products up to date.")
        await engine.dispose()
        return

    client = cohere.AsyncClientV2(api_key=settings.cohere_api_key)
    total = len(records) - len(pending)

    for i in range(0, len(pending), BATCH_SIZE):
        batch = pending[i:i + BATCH_SIZE]
        texts = [r['search_text'] or r['title'] or r['sku'] for r in batch]

        for attempt in range(5):
            try:
                resp = await client.embed(
                    texts=texts,
                    model=EMBED_MODEL,
                    input_type='search_document',
                    embedding_types=['float'],
                )
                break
            except (httpx.ReadTimeout, cohere.errors.too_many_requests_error.TooManyRequestsError) as e:
                wait = 15 * (2 ** attempt)
                print(f"\n  [{type(e).__name__}] retry {attempt + 1}/5 in {wait}s…")
                await asyncio.sleep(wait)
        else:
            print(f"\nFailed batch {i // BATCH_SIZE + 1} after 5 retries. Aborting.")
            await engine.dispose()
            sys.exit(1)

        async with async_session() as session:
            for rec, embedding in zip(batch, resp.embeddings.float_):
                stmt = pg_insert(ProductEmbedding).values(
                    sku=rec['sku'],
                    title=rec['title'],
                    search_text=rec['search_text'],
                    embedding=embedding,
                    type=rec['type'] or None,
                    materials=rec['materials'] or None,
                    moq=rec['moq'] or rec['fb_moq'] or None,
                    capacities=rec['capacities'] or None,
                    price_base=rec['price_base'] or None,
                    price_10k=rec['price_10k'] or None,
                    price_25k=rec['price_25k'] or None,
                    price_50k=rec['price_50k'] or None,
                    price_100k=rec['price_100k'] or None,
                    in_stock=rec['in_stock'],
                    image_url=rec['image_url'] or None,
                    dimensions=rec['dimensions'] or None,
                    search_vector=rec['search_text'],
                ).on_conflict_do_update(
                    index_elements=['sku'],
                    set_=dict(
                        title=rec['title'],
                        search_text=rec['search_text'],
                        embedding=embedding,
                        type=rec['type'] or None,
                        materials=rec['materials'] or None,
                        moq=rec['moq'] or rec['fb_moq'] or None,
                        capacities=rec['capacities'] or None,
                        price_base=rec['price_base'] or None,
                        price_10k=rec['price_10k'] or None,
                        price_25k=rec['price_25k'] or None,
                        price_100k=rec['price_100k'] or None,
                        in_stock=rec['in_stock'],
                        image_url=rec['image_url'] or None,
                        dimensions=rec['dimensions'] or None,
                        search_vector=rec['search_text'],
                    ),
                )
                await session.execute(stmt)
            await session.commit()

        total += len(batch)
        print(f"  upserted {total}/{len(records)}", end='\r')

        if i + BATCH_SIZE < len(pending):
            await asyncio.sleep(SLEEP_S)

    print(f"\nDone. {total} embeddings in DB.")
    await engine.dispose()


if __name__ == '__main__':
    force_all = '--all' in sys.argv
    resume_batch = 0
    for arg in sys.argv:
        if arg.startswith('--resume-batch='):
            resume_batch = int(arg.split('=', 1)[1])
    asyncio.run(run(force_all=force_all, resume_batch=resume_batch))
