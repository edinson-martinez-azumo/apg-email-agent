"""
Run 5 test cases through the full agent pipeline (search + Claude draft) and show results.

Usage (from backend/):
    DATABASE_URL=... uv run python scripts/run_agent_test.py
    DATABASE_URL=... uv run python scripts/run_agent_test.py --id agent_02
"""
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from app.core.config import settings

DATA_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'agent_test_dataset.json')


def _parse_args():
    filter_id = None
    for i, arg in enumerate(sys.argv[1:], 1):
        if arg == '--id' and i < len(sys.argv):
            filter_id = sys.argv[i + 1]
        elif arg.startswith('--id='):
            filter_id = arg.split('=', 1)[1]
    return filter_id


async def run() -> None:
    filter_id = _parse_args()

    db_url = os.environ.get('DATABASE_URL') or settings.database_url
    engine = create_async_engine(db_url, poolclass=NullPool)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    with open(DATA_FILE) as f:
        cases = json.load(f)

    if filter_id:
        cases = [c for c in cases if c['id'] == filter_id]
        if not cases:
            print(f"No case with id '{filter_id}'")
            sys.exit(1)

    from app.services.embedding_service import search_products
    from app.services.claude_service import generate_draft  # noqa: E402

    for case in cases:
        print('=' * 70)
        print(f"[{case['id']}] {case['scenario']}")
        print(f"Customer: {case['customer']} / {case['contact']}")
        print(f"Expected SKUs: {case['expected_skus']}")
        print(f"Expected behavior: {case['expected_agent_behavior']}")
        print()

        query = f"Subject: {case['email_subject']}\n\n{case['email_body']}"

        async with async_session() as session:
            products = await search_products(query, session, top_k=12)

        found_skus = [p['sku'] for p in products]
        hits = [s for s in case['expected_skus'] if s in found_skus]
        recall = len(hits) / len(case['expected_skus']) if case['expected_skus'] else 0

        print(f"Search results ({len(products)} products):")
        for i, p in enumerate(products, 1):
            tag = ' ✓' if p['sku'] in case['expected_skus'] else ''
            print(f"  {i:2}. {p['sku']}{tag} — {p['title'][:55]}")
        print(f"\nSearch recall: {recall:.2f} ({len(hits)}/{len(case['expected_skus'])} expected SKUs found)")
        print()

        body, confidence = generate_draft(
            email_subject=case['email_subject'],
            email_body=case['email_body'],
            products=products,
            thread_history=[],
        )

        print('--- AGENT DRAFT ---')
        print(body)
        print(f'\n[Confidence: {confidence} | Products used: {len(products)}]')
        print()

    await engine.dispose()


if __name__ == '__main__':
    asyncio.run(run())
