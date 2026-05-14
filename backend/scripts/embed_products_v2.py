"""
Embed products from products_unified.xlsx into product_embeddings_v2 (1024-dim).

Usage (from backend/):
    uv run python scripts/embed_products_v2.py           # only new SKUs
    uv run python scripts/embed_products_v2.py --all     # truncate + re-embed all
    uv run python scripts/embed_products_v2.py --resume-batch=N
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

from app.services.product_service import _load_products
from app.db.models.product_embedding_v2 import ProductEmbeddingV2

EMBED_MODEL = 'embed-english-v3.0'
EMBED_DIMS = 1024
BATCH_SIZE = 96
SLEEP_S = 8.0


def _clean(val) -> str:
    if val is None:
        return ''
    s = str(val).strip()
    return '' if s.lower() in ('nan', 'none', '') else s


async def run(force_all: bool = False, resume_batch: int = 0) -> None:
    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        from app.core.config import settings
        db_url = settings.database_url

    engine = create_async_engine(db_url, poolclass=NullPool)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    cohere_key = os.environ.get('COHERE_API_KEY')
    if not cohere_key:
        from app.core.config import settings
        cohere_key = settings.cohere_api_key
    client = cohere.AsyncClientV2(api_key=cohere_key.strip())

    df = _load_products()
    df = df.drop_duplicates('sku')
    records = df.to_dict('records')
    print(f"Source rows: {len(records)}")

    if force_all:
        async with async_session() as session:
            await session.execute(text('TRUNCATE TABLE product_embeddings_v2'))
            await session.commit()
        print("Table truncated.")
        pending = records
    else:
        async with async_session() as session:
            done_result = await session.execute(text('SELECT sku FROM product_embeddings_v2'))
            done = {row[0] for row in done_result.fetchall()}
        pending = [r for r in records if _clean(r.get('sku')) not in done]

    if resume_batch:
        pending = pending[resume_batch * BATCH_SIZE:]
        print(f"Resuming from batch {resume_batch} (skipping {resume_batch * BATCH_SIZE} records)")

    n_batches = (len(pending) + BATCH_SIZE - 1) // BATCH_SIZE
    print(f"Pending: {len(pending)} → {n_batches} batches  |  model: {EMBED_MODEL} ({EMBED_DIMS}d)")

    if not pending:
        print("All products up to date.")
        await engine.dispose()
        return

    total_done = len(records) - len(pending)

    for i in range(0, len(pending), BATCH_SIZE):
        batch = pending[i:i + BATCH_SIZE]
        texts = [_clean(r.get('search_text')) or _clean(r.get('title')) or _clean(r.get('sku')) for r in batch]

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
                search_text = _clean(rec.get('search_text')) or _clean(rec.get('title'))
                stmt = pg_insert(ProductEmbeddingV2).values(
                    sku=_clean(rec['sku']),
                    title=_clean(rec.get('title')) or None,
                    search_text=search_text or None,
                    embedding=embedding,
                    type=_clean(rec.get('type')) or None,
                    materials=_clean(rec.get('materials')) or None,
                    moq=_clean(rec.get('moq')) or None,
                    capacities=_clean(rec.get('capacities')) or None,
                    price_base=_clean(rec.get('price_base')) or None,
                    price_10k=_clean(rec.get('price_10k')) or None,
                    price_25k=_clean(rec.get('price_25k')) or None,
                    price_50k=_clean(rec.get('price_50k')) or None,
                    price_100k=_clean(rec.get('price_100k')) or None,
                    in_stock=bool(rec.get('in_stock', False)),
                    image_url=_clean(rec.get('image_url')) or None,
                    dimensions=_clean(rec.get('dimensions')) or None,
                    search_vector=search_text or None,
                ).on_conflict_do_update(
                    index_elements=['sku'],
                    set_=dict(
                        title=_clean(rec.get('title')) or None,
                        search_text=search_text or None,
                        embedding=embedding,
                        type=_clean(rec.get('type')) or None,
                        materials=_clean(rec.get('materials')) or None,
                        moq=_clean(rec.get('moq')) or None,
                        capacities=_clean(rec.get('capacities')) or None,
                        price_base=_clean(rec.get('price_base')) or None,
                        price_10k=_clean(rec.get('price_10k')) or None,
                        price_25k=_clean(rec.get('price_25k')) or None,
                        price_50k=_clean(rec.get('price_50k')) or None,
                        price_100k=_clean(rec.get('price_100k')) or None,
                        in_stock=bool(rec.get('in_stock', False)),
                        image_url=_clean(rec.get('image_url')) or None,
                        dimensions=_clean(rec.get('dimensions')) or None,
                        search_vector=search_text or None,
                    ),
                )
                await session.execute(stmt)
            await session.commit()

        total_done += len(batch)
        batch_num = i // BATCH_SIZE + 1
        print(f"  batch {batch_num}/{n_batches}  |  upserted {total_done}/{len(records)}", end='\r')

        if i + BATCH_SIZE < len(pending):
            await asyncio.sleep(SLEEP_S)

    print(f"\nDone. {total_done} products in product_embeddings_v2.")
    await engine.dispose()


if __name__ == '__main__':
    force_all = '--all' in sys.argv
    resume_batch = 0
    for arg in sys.argv:
        if arg.startswith('--resume-batch='):
            resume_batch = int(arg.split('=', 1)[1])
    asyncio.run(run(force_all=force_all, resume_batch=resume_batch))
