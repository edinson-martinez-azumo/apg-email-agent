"""
Evaluate product search recall against ground-truth email→SKU pairs.

Metrics:
  recall@k   — fraction of expected SKUs that appear in top-k results
  precision@1 — is the #1 result one of the expected SKUs?

Modes:
  --mode keyword    use keyword search (product_service.search)
  --mode embedding  use hybrid embedding search (embedding_service.search_products)  [default]

Usage (from backend/):
    uv run python scripts/eval_search.py
    uv run python scripts/eval_search.py --mode keyword
    uv run python scripts/eval_search.py --k 5
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

DATA_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'eval_dataset.json')


def _parse_args():
    mode = 'embedding'
    top_k = 12
    for arg in sys.argv[1:]:
        if arg == '--mode' or arg.startswith('--mode='):
            if '=' in arg:
                mode = arg.split('=', 1)[1]
            else:
                idx = sys.argv.index(arg)
                if idx + 1 < len(sys.argv):
                    mode = sys.argv[idx + 1]
        elif arg.startswith('--k='):
            top_k = int(arg.split('=', 1)[1])
        elif arg == '--k':
            idx = sys.argv.index(arg)
            if idx + 1 < len(sys.argv):
                top_k = int(sys.argv[idx + 1])
    return mode, top_k


async def run() -> None:
    mode, top_k = _parse_args()
    if mode not in ('keyword', 'embedding'):
        print(f"Unknown mode '{mode}'. Use --mode keyword or --mode embedding.")
        sys.exit(1)

    with open(DATA_FILE) as f:
        cases = json.load(f)

    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    print(f"\nEval mode: {mode.upper()}  |  top_k={top_k}")
    print("=" * 70)

    recalls = []
    p1_hits = []
    skipped = 0

    for case in cases:
        expected = case.get('expected_skus', [])
        if not expected:
            skipped += 1
            print(f"[{case['id']}] SKIP — {case['customer']} (no expected SKUs)")
            continue

        query = f"Subject: {case['email_subject']}\n\n{case['email_body']}"

        if mode == 'keyword':
            from app.services.product_service import search as kw_search
            results = kw_search(query, top_k=top_k)
        else:
            from app.services.embedding_service import search_products
            async with async_session() as session:
                results = await search_products(query, session, top_k=top_k)

        result_skus = [r['sku'] for r in results]

        found = [sku for sku in expected if sku in result_skus]
        recall = len(found) / len(expected)
        p1 = 1 if result_skus and result_skus[0] in expected else 0

        recalls.append(recall)
        p1_hits.append(p1)

        status = 'OK' if recall == 1.0 else ('PARTIAL' if recall > 0 else 'MISS')
        print(f"[{case['id']}] {status}  {case['customer']}")
        print(f"         expected : {expected}")
        print(f"         got      : {result_skus}")
        print(f"         recall   : {recall:.2f}  precision@1: {p1}")
        print()

    n = len(recalls)
    if n == 0:
        print("No evaluatable cases.")
        await engine.dispose()
        return

    avg_recall = sum(recalls) / n
    avg_p1 = sum(p1_hits) / n
    full_recall = sum(1 for r in recalls if r == 1.0) / n

    print("=" * 70)
    print(f"Cases evaluated : {n}  (skipped: {skipped})")
    print(f"Recall@{top_k}       : {avg_recall:.3f}")
    print(f"Full recall@{top_k}  : {full_recall:.3f}  (fraction with all expected SKUs found)")
    print(f"Precision@1     : {avg_p1:.3f}")
    print("=" * 70)

    await engine.dispose()


if __name__ == '__main__':
    asyncio.run(run())
