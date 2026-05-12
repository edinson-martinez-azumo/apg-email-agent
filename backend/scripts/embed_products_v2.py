"""
Populate product_embeddings_v2 using embed-english-v3.0 (1024 dims).

Copies APG-* rows with length(search_text) >= 150 from product_embeddings,
generates 1024-dim embeddings, and upserts into product_embeddings_v2.

Does NOT touch product_embeddings (v1).

Usage (from backend/):
    DATABASE_URL=postgresql+asyncpg://... uv run python scripts/embed_products_v2.py
    DATABASE_URL=... uv run python scripts/embed_products_v2.py --all   # re-embed existing
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cohere
import httpx
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy import text

from app.db.models.product_embedding_v2 import ProductEmbeddingV2

EMBED_MODEL = 'embed-english-v3.0'
EMBED_DIMS = 1024
MIN_SEARCH_TEXT_LEN = 150
BATCH_SIZE = 96
SLEEP_S = 8.0


async def run(force_all: bool = False) -> None:
    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        from app.core.config import settings
        db_url = settings.database_url

    engine = create_async_engine(db_url, poolclass=NullPool)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # Fetch qualifying rows from v1
    async with async_session() as session:
        result = await session.execute(text(f"""
            SELECT sku, title, search_text, type, materials, moq, capacities,
                   price_base, price_10k, price_25k, price_50k, price_100k,
                   in_stock, image_url, dimensions
            FROM product_embeddings
            WHERE sku ILIKE 'APG-%'
              AND length(search_text) >= {MIN_SEARCH_TEXT_LEN}
            ORDER BY sku
        """))
        all_rows = [dict(r._mapping) for r in result.fetchall()]

    print(f"Qualifying rows from v1 (APG-*, search_text >= {MIN_SEARCH_TEXT_LEN} chars): {len(all_rows)}")

    if not force_all:
        async with async_session() as session:
            done_result = await session.execute(text("SELECT sku FROM product_embeddings_v2"))
            done = {row[0] for row in done_result.fetchall()}
        pending = [r for r in all_rows if r['sku'] not in done]
    else:
        pending = all_rows

    n_batches = (len(pending) + BATCH_SIZE - 1) // BATCH_SIZE
    print(f"Pending: {len(pending)} → {n_batches} batches  |  model: {EMBED_MODEL} ({EMBED_DIMS} dims)")

    if not pending:
        print("All up to date.")
        await engine.dispose()
        return

    cohere_key = os.environ.get('COHERE_API_KEY')
    if not cohere_key:
        from app.core.config import settings
        cohere_key = settings.cohere_api_key
    client = cohere.AsyncClientV2(api_key=cohere_key)

    total = len(all_rows) - len(pending)

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
                print(f"\n  [{type(e).__name__}] retry {attempt+1}/5 in {wait}s…")
                await asyncio.sleep(wait)
        else:
            print(f"\nFailed batch {i // BATCH_SIZE + 1} after 5 retries. Aborting.")
            await engine.dispose()
            sys.exit(1)

        async with async_session() as session:
            for rec, embedding in zip(batch, resp.embeddings.float_):
                stmt = pg_insert(ProductEmbeddingV2).values(
                    sku=rec['sku'],
                    title=rec['title'],
                    search_text=rec['search_text'],
                    embedding=embedding,
                    type=rec['type'] or None,
                    materials=rec['materials'] or None,
                    moq=rec['moq'] or None,
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
                        moq=rec['moq'] or None,
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
                    ),
                )
                await session.execute(stmt)
            await session.commit()

        total += len(batch)
        print(f"  upserted {total}/{len(all_rows)}", end='\r')

        if i + BATCH_SIZE < len(pending):
            await asyncio.sleep(SLEEP_S)

    print(f"\nDone. {total} embeddings in product_embeddings_v2.")
    await engine.dispose()


if __name__ == '__main__':
    force_all = '--all' in sys.argv
    asyncio.run(run(force_all=force_all))
