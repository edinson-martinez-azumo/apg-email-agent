import os
import pandas as pd
from functools import lru_cache
from typing import Any

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'data')
UNIFIED_FILE = os.path.join(DATA_DIR, 'products_unified.xlsx')


@lru_cache(maxsize=1)
def _load_products() -> pd.DataFrame:
    df = pd.read_excel(UNIFIED_FILE)
    df.columns = df.columns.str.lower()
    df['in_stock'] = df['in_stock'].fillna(False).astype(bool)
    df['title'] = df['title'].fillna('').astype(str)
    df['search_text'] = df['search_text'].fillna('').astype(str)
    return df


def search(query: str, top_k: int = 8) -> list[dict[str, Any]]:
    """Keyword search over the product catalog. Returns top_k matches."""
    df = _load_products()
    q = query.lower()
    terms = q.split()
    scores = df['search_text'].apply(
        lambda text: sum(1 for t in terms if t in text)
    )
    top = df[scores > 0].copy()
    top['_score'] = scores[scores > 0]
    top = top.nlargest(top_k, '_score')

    results = []
    for _, row in top.iterrows():
        results.append({
            'sku': row.get('sku', ''),
            'title': row.get('title', ''),
            'type': row.get('type', ''),
            'materials': row.get('materials', ''),
            'moq': row.get('moq', ''),
            'capacities': row.get('capacities', ''),
            'in_stock': bool(row.get('in_stock', False)),
            'price_base': row.get('price_base', ''),
            'price_10k': row.get('price_10k', ''),
            'price_25k': row.get('price_25k', ''),
            'price_50k': row.get('price_50k', ''),
            'price_100k': row.get('price_100k', ''),
        })
    return results
