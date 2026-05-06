"""
One-time script: generate Cohere embeddings for all active products and upsert into product_embeddings.

Usage (from backend/):
    uv run python scripts/embed_products.py

Requirements:
    - COHERE_API_KEY set in .env.local  (free at dashboard.cohere.com)
    - Neon/local DB reachable (DATABASE_URL in .env.local)
    - Migrations up to 0006 applied (make migrate)
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cohere
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy import text

from app.core.config import settings
from app.services.product_service import _load_products
from app.db.models.product_embedding import ProductEmbedding

EMBED_MODEL = 'embed-english-light-v3.0'
BATCH_SIZE = 96   # Cohere max per request
SLEEP_S = 8.0     # ~7.5 batches/min → ~94K tokens/min < 100K TPM trial limit


async def run() -> None:
    df = _load_products()
    df['title'] = df['title'].fillna('').astype(str).replace('nan', '')
    df['search_text'] = df['search_text'].fillna('').astype(str)
    records = df[['sku', 'title', 'search_text']].drop_duplicates('sku').to_dict('records')

    engine = create_async_engine(settings.database_url, pool_size=1, max_overflow=0)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # Skip already-embedded SKUs so reruns don't waste API calls
    async with async_session() as session:
        result = await session.execute(text('SELECT sku FROM product_embeddings'))
        done = {row[0] for row in result.fetchall()}

    pending = [r for r in records if r['sku'] not in done]
    n_batches = (len(pending) + BATCH_SIZE - 1) // BATCH_SIZE
    print(f"Total: {len(records)}  Already done: {len(done)}  Pending: {len(pending)} → {n_batches} batches")

    if not pending:
        print("All products already embedded.")
        await engine.dispose()
        return

    client = cohere.AsyncClientV2(api_key=settings.cohere_api_key)
    total = len(done)

    for i in range(0, len(pending), BATCH_SIZE):
        batch = pending[i:i + BATCH_SIZE]
        texts = [r['search_text'] or r['title'] or r['sku'] for r in batch]

        resp = await client.embed(
            texts=texts,
            model=EMBED_MODEL,
            input_type='search_document',
            embedding_types=['float'],
        )

        async with async_session() as session:
            for rec, embedding in zip(batch, resp.embeddings.float_):
                stmt = pg_insert(ProductEmbedding).values(
                    sku=rec['sku'],
                    title=rec['title'],
                    search_text=rec['search_text'],
                    embedding=embedding,
                ).on_conflict_do_update(
                    index_elements=['sku'],
                    set_=dict(
                        title=rec['title'],
                        search_text=rec['search_text'],
                        embedding=embedding,
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
    asyncio.run(run())
