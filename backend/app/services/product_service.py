import os
import re
import pandas as pd
from functools import lru_cache
from typing import Any

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'data')


def _parse_capacities(tags: str) -> str:
    """Extract and sort capacity values from Shopify tags. e.g. 'Capacity_50ml, Capacity_15ML' → '15ml, 50ml'"""
    if not tags:
        return ''
    hits = re.findall(r'Capacity_(\d+\s*m[lL])', str(tags))
    normalized = sorted(
        set(h.lower().replace(' ', '') for h in hits),
        key=lambda x: int(re.search(r'\d+', x).group()),
    )
    return ', '.join(normalized)


@lru_cache(maxsize=1)
def _load_products() -> pd.DataFrame:
    shopify = pd.read_excel(os.path.join(DATA_DIR, 'shopify.xlsx'))
    fishbowl = pd.read_excel(os.path.join(DATA_DIR, 'fishbowl.xlsx'))

    shopify = shopify[shopify['Status'].isin(['active', 'archived']) | shopify['Status'].isna()].copy()

    sh_cols = {
        'Variant SKU': 'sku',
        'Title': 'title',
        'Type': 'type',
        'Variant Price': 'price',
        'MOQ (product.metafields.sf_product_tabs.tab_1_moq)': 'moq',
        'Materials (product.metafields.sf_product_tabs.tab_1_materials)': 'materials',
        'Tags': 'tags',
    }
    shopify = shopify.rename(columns=sh_cols)[list(sh_cols.values())].dropna(subset=['sku'])

    fb_cols = {
        'PartNumber': 'sku',
        'PartDescription': 'description',
        'CF-MOQ': 'fb_moq',
        'CF-Tier Cost 10k': 'price_10k',
        'CF-Tier Cost 25k': 'price_25k',
        'CF-Tier Cost 50k': 'price_50k',
        'CF-Tier Cost 100k': 'price_100k',
    }
    fishbowl = fishbowl[fishbowl['Active'] == True].rename(columns=fb_cols)[list(fb_cols.values())]  # noqa: E712

    merged = shopify.merge(fishbowl, on='sku', how='outer')
    merged['sku'] = merged['sku'].astype(str)
    merged = merged[merged['sku'].str.startswith('APG', na=False) | merged['sku'].str.match(r'^[A-Za-z]', na=False)]
    merged['search_text'] = (
        merged[['sku', 'title', 'type', 'materials', 'tags', 'description']]
        .fillna('')
        .astype(str)
        .agg(' '.join, axis=1)
        .str.lower()
    )
    merged['title'] = merged['title'].fillna('').astype(str).replace('nan', '')
    merged['title'] = merged.apply(
        lambda r: r['description'] if not r['title'] and r.get('description') else r['title'], axis=1
    )
    merged['capacities'] = merged['tags'].fillna('').apply(_parse_capacities)
    merged['in_stock'] = merged['title'].str.contains(r'in stock', case=False, na=False)
    return merged


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
            'moq': row.get('moq') or row.get('fb_moq', ''),
            'capacities': row.get('capacities', ''),
            'in_stock': bool(row.get('in_stock', False)),
            'price_base': row.get('price', ''),
            'price_10k': row.get('price_10k', ''),
            'price_25k': row.get('price_25k', ''),
            'price_50k': row.get('price_50k', ''),
            'price_100k': row.get('price_100k', ''),
        })
    return results
