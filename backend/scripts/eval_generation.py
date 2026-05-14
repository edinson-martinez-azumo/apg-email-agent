"""
Evaluate end-to-end generation quality: search + Claude draft.

Measures which expected SKUs actually appear in the generated draft,
complementing eval_search.py (which only measures search recall).

Usage (from backend/):
    uv run python scripts/eval_generation.py
    uv run python scripts/eval_generation.py --case case_08
    uv run python scripts/eval_generation.py --runs 3   # run each case N times, report worst/best
"""
import argparse
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env.local'))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from app.core.config import settings

DATA_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'eval_dataset.json')


def _make_session():
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    return sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def _run_case(case: dict, Session) -> dict:
    from app.services.embedding_service import search_products
    from app.services.claude_service import generate_draft

    query = f"{case['email_subject']} {case['email_body']}"
    async with Session() as db:
        products = await search_products(query, db, top_k=12)
        draft, confidence = generate_draft(case['email_subject'], case['email_body'], products)

    expected = case['expected_skus']
    found = [s for s in expected if s in draft]
    missing = [s for s in expected if s not in draft]
    recall = len(found) / len(expected) if expected else 1.0

    return {
        'id': case['id'],
        'customer': case['customer'],
        'expected': expected,
        'found': found,
        'missing': missing,
        'recall': recall,
        'confidence': confidence,
        'draft': draft,
    }


async def main(filter_case: str | None, runs: int):
    with open(DATA_FILE) as f:
        cases = [c for c in json.load(f) if c.get('expected_skus')]

    if filter_case:
        cases = [c for c in cases if c['id'] == filter_case]
        if not cases:
            print(f'Case {filter_case!r} not found or has no expected SKUs.')
            return

    Session = _make_session()

    sep = '=' * 70
    print(sep)

    total_recall = 0.0
    total_full = 0
    results_per_case: dict[str, list[dict]] = {}

    for case in cases:
        results_per_case[case['id']] = []
        for _ in range(runs):
            r = await _run_case(case, Session)
            results_per_case[case['id']].append(r)

    for case in cases:
        runs_data = results_per_case[case['id']]
        recalls = [r['recall'] for r in runs_data]
        min_recall = min(recalls)
        max_recall = max(recalls)
        # use worst-case run for summary
        worst = min(runs_data, key=lambda r: r['recall'])

        status = 'OK' if min_recall == 1.0 else ('PARTIAL' if max_recall > 0 else 'FAIL')
        stability = '' if runs == 1 else f'  [min={min_recall:.2f} max={max_recall:.2f}]'

        print(f"[{case['id']}] {status}  {case['customer']}")
        print(f"         expected : {worst['expected']}")
        print(f"         found    : {worst['found']}")
        if worst['missing']:
            print(f"         missing  : {worst['missing']}")
        print(f"         recall   : {min_recall:.2f}  confidence: {worst['confidence']}{stability}")

        total_recall += min_recall
        if min_recall == 1.0:
            total_full += 1

    n = len(cases)
    print(sep)
    print(f'Cases evaluated : {n}')
    print(f'Recall@draft    : {total_recall / n:.3f}')
    print(f'Full recall     : {total_full / n:.3f}  (fraction with all expected SKUs in draft)')
    print(sep)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', help='Run only this case ID (e.g. case_08)')
    parser.add_argument('--runs', type=int, default=1, help='Runs per case (default: 1). Use >1 to detect non-determinism.')
    args = parser.parse_args()
    asyncio.run(main(args.case, args.runs))
