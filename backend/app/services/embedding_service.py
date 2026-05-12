import re
import anthropic
import cohere
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.core.config import settings

_SKU_RE = re.compile(r'\bAPG-[\w/\-]+', re.IGNORECASE)

EMBED_MODEL = 'embed-english-light-v3.0'
EMBED_DIMS = 384
RERANK_MODEL = 'rerank-english-v3.0'
CANDIDATES_MULTIPLIER = 3  # fetch 3x candidates then rerank down to top_k

_cohere: cohere.AsyncClientV2 | None = None
_anthropic: anthropic.Anthropic | None = None

ENRICH_PROMPT = """Extract packaging product search terms from the customer email below.

Return ONLY a space-separated list of technical catalog terms covering:
container type, closure type, material, capacity/size, application, end use.

Rules:
- Translate intent to catalog terms: "single-handed in shower" → "flip-top cap", "TSA rules" → "100ml travel size", "squeeze" → "tottle squeeze"
- Include both the inferred closure AND the container type
- At most 15 terms. No explanation, no punctuation beyond spaces.

Customer email:
"""

SEGMENT_PROMPT = """Extract all distinct product types being requested in this customer email.
Return ONLY valid JSON — a list of objects, one per product type.

Each object:
- "description": concise phrase describing what the customer wants (used as search query)
- "type": container/closure category (e.g. "fine mist sprayer", "lotion pump", "glass bottle", "airless pump")
- "capacity": capacity in ml as string (e.g. "30ml", "473ml"). Convert oz: 1oz=30ml, 2oz=60ml, 8oz=237ml, 16oz=473ml. null if not mentioned.
- "neck_sizes": list of neck sizes in XX/YYY format (e.g. ["20/410","24/410"]). null if none mentioned.
- "material": primary material if explicitly stated (e.g. "PCR", "PET", "glass", "aluminum"). null if not stated.

Rules:
- One object per distinct product category
- Do NOT split by size variants (30ml + 50ml same product type = one object)
- Maximum 4 objects. If single product type, return list with one object.

Examples:
Input: "fine mist sprayers 20/410 and 24/410, also lotion pump PCR 20/410"
Output: [{"description":"fine mist sprayer 20/410 24/410","type":"fine mist sprayer","capacity":null,"neck_sizes":["20/410","24/410"],"material":null},{"description":"lotion pump PCR 20/410","type":"lotion pump","capacity":null,"neck_sizes":["20/410"],"material":"PCR"}]

Input: "square glass bottles amber 30ml 50ml, compatible pumps 18/400 and 20/400"
Output: [{"description":"square glass bottle amber 30ml 50ml","type":"glass bottle","capacity":null,"neck_sizes":null,"material":"glass"},{"description":"lotion pump 18/400 20/400","type":"lotion pump","capacity":null,"neck_sizes":["18/400","20/400"],"material":null}]

Input: "2oz aluminum screw-top jar"
Output: [{"description":"aluminum screw-top jar 2oz 60ml","type":"jar","capacity":"60ml","neck_sizes":null,"material":"aluminum"}]

Customer email:
"""


def _get_cohere() -> cohere.AsyncClientV2:
    global _cohere
    if _cohere is None:
        _cohere = cohere.AsyncClientV2(api_key=settings.cohere_api_key.strip())
    return _cohere


def _get_anthropic() -> anthropic.Anthropic:
    global _anthropic
    if _anthropic is None:
        _anthropic = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    return _anthropic


async def _enrich_query(raw_query: str) -> str:
    async_client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    response = await async_client.messages.create(
        model='claude-haiku-4-5-20251001',
        max_tokens=80,
        messages=[{'role': 'user', 'content': f'{ENRICH_PROMPT}{raw_query}'}],
    )
    terms = response.content[0].text.strip()
    return f'{raw_query} {terms}'


async def _segment_products(raw_query: str) -> list[dict]:
    """Segment customer email into distinct product requests, each with its own attributes."""
    import json
    async_client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    response = await async_client.messages.create(
        model='claude-haiku-4-5-20251001',
        max_tokens=300,
        messages=[{'role': 'user', 'content': f'{SEGMENT_PROMPT}{raw_query}'}],
    )
    try:
        raw = response.content[0].text.strip()
        # Strip markdown code fences if present
        if raw.startswith('```'):
            raw = raw.split('```', 2)[1]
            if raw.startswith('json'):
                raw = raw[4:]
        result = json.loads(raw.strip())
        if isinstance(result, list) and result:
            return result
        return [{'description': raw_query, 'capacity': None, 'neck_sizes': None, 'material': None}]
    except Exception:
        return [{'description': raw_query, 'capacity': None, 'neck_sizes': None, 'material': None}]


def _build_attr_filter(attrs: dict, exclude_skus: set[str]) -> tuple[str, dict]:
    """Build SQL WHERE fragment and params from extracted attrs. Returns ('', {}) if no attrs."""
    parts = []
    params: dict = {}

    neck_sizes = attrs.get('neck_sizes') or []
    if neck_sizes:
        ns_parts = []
        for i, ns in enumerate(neck_sizes[:4]):
            key = f'ns_{i}'
            ns_parts.append(f'search_text ILIKE :{key}')
            params[key] = f'%{ns}%'
        parts.append(f'({" OR ".join(ns_parts)})')

    material = attrs.get('material')
    if material and material.upper() not in ('NULL', 'NONE'):
        parts.append('(materials ILIKE :mat OR search_text ILIKE :mat)')
        params['mat'] = f'%{material}%'

    capacity = attrs.get('capacity')
    if capacity and capacity.upper() not in ('NULL', 'NONE'):
        parts.append('(capacities ILIKE :cap OR search_text ILIKE :cap)')
        params['cap'] = f'%{capacity}%'

    if not parts:
        return '', {}
    return ' AND '.join(parts), params


async def _expand_variants(candidates: list[dict], db: AsyncSession, already_seen: set[str]) -> list[dict]:
    """For top candidates, fetch SKU variants not already in results.
    Expands both children (sku LIKE 'BASE-%') and siblings (strip one suffix level)."""
    if not candidates:
        return []

    prefixes: set[str] = set()
    for c in candidates[:12]:
        sku = c['sku']
        prefixes.add(sku)  # direct children: APG-XXX → APG-XXX-*
        # Sibling expansion: strip last segment if short (variant indicator)
        parts = sku.rsplit('-', 1)
        if len(parts) == 2 and len(parts[1]) <= 3 and parts[1].replace('/', '').isalnum():
            prefixes.add(parts[0])  # base → APG-XXX-* (all siblings)

    like_clauses = [f'sku LIKE :p{i}' for i in range(len(prefixes))]
    params = {f'p{i}': f'{prefix}-%' for i, prefix in enumerate(sorted(prefixes))}

    result = await db.execute(text(f"""
        SELECT sku, title, type, materials, moq, capacities,
               price_base, price_10k, price_25k, price_50k, price_100k, in_stock, image_url
        FROM product_embeddings
        WHERE ({' OR '.join(like_clauses)})
        LIMIT 40
    """), params)
    rows = result.mappings().all()
    return [_row_to_dict(r) for r in rows if r['sku'] not in already_seen]


async def _rerank(query: str, candidates: list[dict], top_k: int) -> list[dict]:
    """Rerank candidates using Cohere reranker. Returns top_k best matches."""
    if len(candidates) <= top_k:
        return candidates
    documents = [
        f"SKU: {c['sku']}. {c['title']}. Capacity: {c['capacities']}. Materials: {c['materials']}. Type: {c['type']}. MOQ: {c['moq']}."
        for c in candidates
    ]
    response = await _get_cohere().rerank(
        query=query,
        documents=documents,
        model=RERANK_MODEL,
        top_n=top_k,
    )
    return [candidates[r.index] for r in response.results]


async def embed(text_input: str) -> list[float]:
    resp = await _get_cohere().embed(
        texts=[text_input],
        model=EMBED_MODEL,
        input_type='search_query',
        embedding_types=['float'],
    )
    return resp.embeddings.float_[0]


def _row_to_dict(r) -> dict:
    return {
        'sku': r['sku'],
        'title': r['title'] or '',
        'type': r['type'] or '',
        'materials': r['materials'] or '',
        'moq': r['moq'] or '',
        'capacities': r['capacities'] or '',
        'in_stock': bool(r['in_stock']),
        'price_base': r['price_base'] or '',
        'price_10k': r['price_10k'] or '',
        'price_25k': r['price_25k'] or '',
        'price_50k': r['price_50k'] or '',
        'price_100k': r['price_100k'] or '',
        'image_url': r['image_url'] or '',
    }


async def _fetch_exact_skus(query: str, db: AsyncSession) -> list[dict]:
    """Fetch any APG-* SKUs explicitly mentioned in the query text."""
    mentioned = list(dict.fromkeys(m.upper() for m in _SKU_RE.findall(query)))
    if not mentioned:
        return []
    placeholders = ', '.join(f"'{s}'" for s in mentioned)
    result = await db.execute(text(f"""
        SELECT sku, title, type, materials, moq, capacities,
               price_base, price_10k, price_25k, price_50k, price_100k, in_stock, image_url
        FROM product_embeddings
        WHERE sku IN ({placeholders})
    """))
    rows = result.mappings().all()
    sku_order = {s: i for i, s in enumerate(mentioned)}
    return sorted([_row_to_dict(r) for r in rows], key=lambda r: sku_order.get(r['sku'], 999))


async def search_products(query: str, db: AsyncSession, top_k: int = 8) -> list[dict]:
    """
    Hybrid search: cosine similarity (0.7) + full-text ts_rank (0.3).
    SKUs explicitly named in the query are injected at the top of results.
    Falls back to keyword search if product_embeddings is empty.
    """
    count = await db.scalar(text('SELECT COUNT(*) FROM product_embeddings'))
    if not count:
        from app.services.product_service import search as keyword_search
        return keyword_search(query, top_k=top_k)

    # Check if metadata columns are populated (post-migration 0010)
    has_metadata = await db.scalar(
        text("SELECT COUNT(*) FROM product_embeddings WHERE price_10k IS NOT NULL LIMIT 1")
    )

    import asyncio as _asyncio

    exact_hits, segments = await _asyncio.gather(
        _fetch_exact_skus(query, db),
        _segment_products(query),
    )
    exact_skus = {p['sku'] for p in exact_hits}
    candidates_k = top_k * CANDIDATES_MULTIPLIER

    if has_metadata:
        base_sql = """
            SELECT
                sku, title, type, materials, moq, capacities,
                price_base, price_10k, price_25k, price_50k, price_100k, in_stock,
                image_url,
                (0.7 * (1 - (embedding <=> CAST(:vec AS vector))) +
                 0.3 * ts_rank(search_vector_ts, plainto_tsquery('english', :q))) AS score
            FROM product_embeddings
            {where}
            ORDER BY score DESC
            LIMIT :k
        """

        async def _search_segment(seg: dict) -> list:
            enriched = await _enrich_query(seg.get('description') or query)
            seg_embedding = await embed(enriched)
            base_params = {'vec': str(seg_embedding), 'q': seg.get('description') or query, 'k': candidates_k}
            attrs = {k: seg.get(k) for k in ('capacity', 'neck_sizes', 'material')}
            attr_filter, attr_params = _build_attr_filter(attrs, exact_skus)
            if attr_filter:
                filtered_result = await db.execute(
                    text(base_sql.format(where=f'WHERE {attr_filter}')),
                    {**base_params, **attr_params},
                )
                filtered_rows = filtered_result.mappings().all()
            else:
                filtered_rows = []
            if len(filtered_rows) >= top_k:
                return list(filtered_rows)
            unfiltered_result = await db.execute(text(base_sql.format(where='')), base_params)
            return list(unfiltered_result.mappings().all())

        # AsyncSession is not safe for concurrent use — run segments sequentially
        segment_rows = []
        for seg in segments:
            segment_rows.append(await _search_segment(seg))

        # Merge and dedup across segments, preserving order (first segment wins on ties)
        seen = set(exact_skus)
        candidates = []
        for rows in segment_rows:
            for r in rows:
                d = _row_to_dict(r)
                if d['sku'] not in seen:
                    seen.add(d['sku'])
                    candidates.append(d)

        variants = await _expand_variants(candidates, db, seen)
        merged = exact_hits + candidates + variants
        return await _rerank(query, merged, top_k)
    else:
        # Pre-migration fallback: cosine only + DataFrame merge
        from sqlalchemy import select as sa_select
        from app.db.models.product_embedding import ProductEmbedding
        from app.services.product_service import _load_products

        result = await db.execute(
            sa_select(ProductEmbedding)
            .order_by(ProductEmbedding.embedding.cosine_distance(query_embedding))
            .limit(top_k)
        )
        rows = result.scalars().all()
        df = _load_products()
        out = []
        for row in rows:
            match = df[df['sku'] == row.sku]
            if match.empty:
                continue
            r = match.iloc[0]
            out.append({
                'sku': row.sku,
                'title': row.title or '',
                'type': str(r.get('type', '')),
                'materials': str(r.get('materials', '')),
                'moq': r.get('moq') or r.get('fb_moq', ''),
                'capacities': r.get('capacities', ''),
                'in_stock': bool(r.get('in_stock', False)),
                'price_base': r.get('price', ''),
                'price_10k': r.get('price_10k', ''),
                'price_25k': r.get('price_25k', ''),
                'price_50k': r.get('price_50k', ''),
                'price_100k': r.get('price_100k', ''),
            })
        return out
