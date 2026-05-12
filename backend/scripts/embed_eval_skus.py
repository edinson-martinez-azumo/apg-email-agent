"""
Temporary script: re-embed only the SKUs present in eval_dataset.json.
Use this to quickly validate search improvement before running embed_products.py --all.

Usage (from backend/):
    DATABASE_URL=postgresql+asyncpg://... uv run python scripts/embed_eval_skus.py
"""
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cohere
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from sqlalchemy import text

EMBED_MODEL = 'embed-english-light-v3.0'
DATA_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'eval_dataset.json')


async def run() -> None:
    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        from app.core.config import settings
        db_url = settings.database_url

    with open(DATA_FILE) as f:
        cases = json.load(f)
    skus = sorted(set(s for c in cases for s in c.get('expected_skus', [])))
    print(f"Eval SKUs to re-embed: {len(skus)}")

    engine = create_async_engine(db_url, poolclass=NullPool)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        placeholders = ', '.join(f"'{s}'" for s in skus)
        result = await session.execute(text(f"""
            SELECT sku, search_text, title
            FROM product_embeddings
            WHERE sku IN ({placeholders})
        """))
        rows = [dict(r._mapping) for r in result.fetchall()]

    found = {r['sku'] for r in rows}
    missing = set(skus) - found
    if missing:
        print(f"  Not in DB: {sorted(missing)}")

    print(f"  Found in DB: {len(rows)}")
    for r in rows:
        st = r['search_text'] or ''
        print(f"  {r['sku']:<32} {len(st):>4} chars  |  {st[:80]}")

    texts = [r['search_text'] or r['title'] or r['sku'] for r in rows]

    client = cohere.AsyncClientV2(api_key=os.environ.get('COHERE_API_KEY') or __import__('app.core.config', fromlist=['settings']).settings.cohere_api_key)
    resp = await client.embed(
        texts=texts,
        model=EMBED_MODEL,
        input_type='search_document',
        embedding_types=['float'],
    )

    async with async_session() as session:
        for row, embedding in zip(rows, resp.embeddings.float_):
            await session.execute(text("""
                UPDATE product_embeddings
                SET embedding = CAST(:emb AS vector)
                WHERE sku = :sku
            """), {'emb': str(embedding), 'sku': row['sku']})
        await session.commit()

    print(f"\nDone. {len(rows)} embeddings updated.")
    print("Run eval: DATABASE_URL=... uv run python scripts/eval_search.py")

    await engine.dispose()


if __name__ == '__main__':
    asyncio.run(run())
