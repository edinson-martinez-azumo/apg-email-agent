import re
import anthropic
import cohere
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.core.config import settings

_SKU_RE = re.compile(r'\bAPG-[\w/\-]+', re.IGNORECASE)

EMBED_MODEL = 'embed-english-v3.0'
EMBED_DIMS = 1024
PRODUCT_TABLE = 'product_embeddings_v2'
RERANK_MODEL = 'rerank-english-v3.0'
CANDIDATES_MULTIPLIER = 3  # fetch 3x candidates then rerank down to top_k

_cohere: cohere.AsyncClientV2 | None = None
_anthropic: anthropic.Anthropic | None = None

ENRICH_PROMPT = """Extract packaging product search terms from the customer email below.

Return ONLY a space-separated list of technical catalog terms covering:
container type, closure type, material, capacity/size, application, end use.

Rules:
- Translate intent to catalog terms: "single-handed in shower" → "flip-top cap", "TSA rules" → "100ml travel size", "squeeze" → "tottle squeeze"
- Vocabulary mappings: "foaming soap/hand soap" → "foamer pump bottle", "foam pump" → "foamer pump", "foaming dispenser" → "foamer pump bottle", "oil pump" → "treatment pump bottle lotion pump oil compatible", "serum pump" → "treatment pump bottle lotion pump"
- Include both the inferred closure AND the container type
- At most 15 terms. No explanation, no punctuation beyond spaces.

Customer email:
"""

SEGMENT_PROMPT = """Extract all distinct product types being requested in this customer email.
Return ONLY valid JSON — a list of objects, one per product type.

Each object:
- "description": concise phrase describing what the customer wants (used as search query)
- "type": container/closure category (e.g. "fine mist sprayer", "lotion pump", "glass bottle", "airless pump", "foamer pump bottle")
- "capacity": capacity in ml as string (e.g. "30ml", "473ml"). Convert oz: 1oz=30ml, 2oz=60ml, 8oz=237ml, 16oz=473ml. null if not mentioned.
- "neck_sizes": list of neck sizes in XX/YYY format (e.g. ["20/410","24/410"]). null if none mentioned.
- "material": primary material if explicitly stated (e.g. "PCR", "PET", "glass", "aluminum"). null if not stated.

Rules:
- One object per distinct product category
- Do NOT split by size variants (30ml + 50ml same product type = one object)
- Maximum 4 objects. If single product type, return list with one object.
- Vocabulary: "foaming soap bottle", "foaming hand soap bottle", "foam pump bottle" → type must be "foamer pump bottle". Never map these to generic bottle types.
- CRITICAL: neck_sizes, capacity, and material belong ONLY to the product they describe. Never copy attributes from one product type to another.
- CRITICAL: When the customer names a specific SKU with a material (e.g. "your ABS/PP bottle SKU APG-XXX"), that material describes ONLY that named SKU. The general request for "similar bottles" or "other options" has material=null.

Examples:
Input: "fine mist sprayers 20/410 and 24/410, also lotion pump PCR 20/410"
Output: [{"description":"fine mist sprayer 20/410 24/410","type":"fine mist sprayer","capacity":null,"neck_sizes":["20/410","24/410"],"material":null},{"description":"lotion pump PCR 20/410","type":"lotion pump","capacity":null,"neck_sizes":["20/410"],"material":"PCR"}]

Input: "square glass bottles amber 30ml 50ml, compatible pumps 18/400 and 20/400"
Output: [{"description":"square glass bottle amber 30ml 50ml","type":"glass bottle","capacity":null,"neck_sizes":null,"material":"glass"},{"description":"lotion pump 18/400 20/400","type":"lotion pump","capacity":null,"neck_sizes":["18/400","20/400"],"material":null}]

Input: "I want to review your ABS/PP airless pump bottle SKU APG-200547 and similar airless bottles 30ml, also airless jars 50ml"
Output: [{"description":"airless pump bottle 30ml","type":"airless pump","capacity":null,"neck_sizes":null,"material":null},{"description":"airless jar 50ml","type":"jar","capacity":"50ml","neck_sizes":null,"material":null}]

Input: "2oz aluminum screw-top jar"
Output: [{"description":"aluminum screw-top jar 2oz 60ml","type":"jar","capacity":"60ml","neck_sizes":null,"material":"aluminum"}]

Input: "16oz foaming hand soap bottle with pump quantity 10000"
Output: [{"description":"foamer pump bottle 473ml foaming soap dispenser","type":"foamer pump bottle","capacity":"473ml","neck_sizes":null,"material":null}]

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
        temperature=0,
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
        temperature=0,
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


_GENERIC_TYPE_WORDS = frozenset({
    'bottle', 'pump', 'jar', 'tube', 'cap', 'container', 'dispenser', 'pack', 'package',
})

# Materials too generic to filter on — catálog uses abbreviations (PP, ABS, PET) not these words
_GENERIC_MATERIALS = frozenset({'plastic', 'glass', 'metal', 'polymer', 'aluminum', 'aluminium', 'stainless', 'stainless steel', 'steel'})


def _type_keyword(product_type: str) -> str | None:
    """Extract the most distinctive word from a product type string."""
    for word in (product_type or '').lower().split():
        if word not in _GENERIC_TYPE_WORDS:
            return word
    return None


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
    if material and material.upper() not in ('NULL', 'NONE') and material.lower() not in _GENERIC_MATERIALS:
        parts.append('(materials ILIKE :mat OR search_text ILIKE :mat)')
        params['mat'] = f'%{material}%'

    capacity = attrs.get('capacity')
    if capacity and capacity.upper() not in ('NULL', 'NONE'):
        parts.append('(capacities ILIKE :cap OR search_text ILIKE :cap)')
        params['cap'] = f'%{capacity}%'

    if not parts:
        return '', {}
    return ' AND '.join(parts), params


def _build_type_filter(product_type: str) -> tuple[str, dict]:
    """Build a type-keyword-only filter for use as strict-filter fallback."""
    kw = _type_keyword(product_type)
    if not kw:
        return '', {}
    return '(search_text ILIKE :type_kw OR title ILIKE :type_kw)', {'type_kw': f'%{kw}%'}


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
               price_base, price_10k, price_25k, price_50k, price_100k, in_stock, image_url, search_text
        FROM product_embeddings_v2
        WHERE ({' OR '.join(like_clauses)})
        LIMIT 40
    """), params)
    rows = result.mappings().all()
    return [_row_to_dict(r) for r in rows if r['sku'] not in already_seen]


def _cap_with_oz(cap: str) -> str:
    if not cap:
        return cap
    ml_vals = re.findall(r'\b(\d+)ml\b', cap, re.IGNORECASE)
    if not ml_vals:
        return cap
    parts = [f'{int(m)}ml (≈{int(m)/29.574:.0f}oz)' for m in ml_vals]
    return cap + ' / ' + ', '.join(parts)


def _build_rerank_docs(candidates: list[dict]) -> list[str]:
    return [
        f"SKU: {c['sku']}. {c['title']}. Capacity: {_cap_with_oz(c['capacities'])}. Materials: {c['materials']}. Type: {c['type']}. MOQ: {c['moq']}. Tags: {(c.get('search_text') or '')[:600]}"
        for c in candidates
    ]


async def _cohere_rerank_scored(query: str, candidates: list[dict], top_n: int) -> list[tuple[dict, float]]:
    """Rerank candidates, return (candidate, relevance_score) pairs sorted by score desc."""
    import asyncio as _asyncio
    documents = _build_rerank_docs(candidates)
    for attempt in range(4):
        try:
            response = await _get_cohere().rerank(
                query=query,
                documents=documents,
                model=RERANK_MODEL,
                top_n=top_n,
            )
            return [(candidates[r.index], r.relevance_score) for r in response.results]
        except cohere.errors.too_many_requests_error.TooManyRequestsError:
            if attempt == 3:
                raise
            await _asyncio.sleep(15 * (2 ** attempt))


async def _rerank(query: str, candidates: list[dict], top_k: int) -> list[dict]:
    """Rerank candidates using Cohere reranker. Returns top_k best matches.

    Always fetches top_k*2 results from the reranker to have a wider view.
    When reranker scores are near-saturated (all within 0.01 of each other), the
    tiny differences are noise — blend in embedding rank (35%) to stabilize ordering
    across the wider pool before taking top_k.
    For normal score spreads, trust the reranker directly (first top_k of the pool).
    """
    if len(candidates) <= top_k:
        return candidates
    top_n = min(len(candidates), top_k * 2)
    scored = await _cohere_rerank_scored(query, candidates, top_n=top_n)
    scores = [s for _, s in scored]
    if scores and (max(scores) - min(scores)) < 0.01:
        # Near-saturated: blend wider pool then take top_k
        n = len(candidates)
        embed_rank = {c['sku']: i for i, c in enumerate(candidates)}
        blended = [
            (c, 0.65 * score + 0.35 * (1.0 - embed_rank.get(c['sku'], n) / n))
            for c, score in scored
        ]
        blended.sort(key=lambda x: x[1], reverse=True)
        return [c for c, _ in blended[:top_k]]
    return [c for c, _ in scored[:top_k]]


def _split_or_queries(description: str) -> list[str]:
    """Split 'X or Y ...' on ' or ' boundaries. Returns [description] if no ' or ' found."""
    parts = re.split(r'\s+or\s+', description, flags=re.IGNORECASE)
    return parts if len(parts) > 1 else [description]


async def _rerank_or_queries(description: str, candidates: list[dict], top_k: int) -> list[dict]:
    """Per-segment rerank that handles OR alternatives.

    For descriptions without 'or', identical to _rerank.
    For OR descriptions (e.g. 'amber or square black bottle 30ml 50ml'), the enriched
    embedding query already covers both alternatives well — the reranker would instead
    collapse them into a conjunction. Skip reranking and trust embedding order.
    """
    if len(candidates) <= top_k:
        return candidates
    sub_queries = _split_or_queries(description)
    if len(sub_queries) == 1:
        return await _rerank(description, candidates, top_k)
    # OR-description: candidates already ordered by hybrid embedding score covering
    # both alternatives — returning top_k directly preserves that coverage.
    return candidates[:top_k]


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
        'search_text': (r['search_text'] or '') if 'search_text' in r else '',
        'score': float(r['score']) if 'score' in r else None,
    }


async def _fetch_exact_skus(query: str, db: AsyncSession) -> list[dict]:
    """Fetch any APG-* SKUs explicitly mentioned in the query text."""
    mentioned = list(dict.fromkeys(m.upper() for m in _SKU_RE.findall(query)))
    if not mentioned:
        return []
    placeholders = ', '.join(f"'{s}'" for s in mentioned)
    result = await db.execute(text(f"""
        SELECT sku, title, type, materials, moq, capacities,
               price_base, price_10k, price_25k, price_50k, price_100k, in_stock, image_url, search_text
        FROM product_embeddings_v2
        WHERE sku IN ({placeholders})
    """))
    rows = result.mappings().all()
    sku_order = {s: i for i, s in enumerate(mentioned)}
    return sorted([_row_to_dict(r) for r in rows], key=lambda r: sku_order.get(r['sku'], 999))


async def search_products(query: str, db: AsyncSession, top_k: int = 12) -> list[dict]:
    """
    Hybrid search: cosine similarity (0.7) + full-text ts_rank (0.3).
    SKUs explicitly named in the query are injected at the top of results.
    Falls back to keyword search if product_embeddings is empty.
    """
    count = await db.scalar(text('SELECT COUNT(*) FROM product_embeddings_v2'))
    if not count:
        from app.services.product_service import search as keyword_search
        return keyword_search(query, top_k=top_k)

    # Check if metadata columns are populated (post-migration 0010)
    has_metadata = await db.scalar(
        text("SELECT COUNT(*) FROM product_embeddings_v2 WHERE price_10k IS NOT NULL LIMIT 1")
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
                image_url, search_text,
                (0.7 * (1 - (embedding <=> CAST(:vec AS vector))) +
                 0.3 * ts_rank(search_vector_ts, plainto_tsquery('english', :q))) AS score
            FROM product_embeddings_v2
            {where}
            ORDER BY score DESC
            LIMIT :k
        """

        async def _search_segment(seg: dict) -> list:
            desc = seg.get('description') or query
            # For OR-descriptions with no capacity filter, strip size numbers to avoid
            # embedding bias toward specific capacities when multiple sizes are requested.
            or_desc = re.search(r'\bor\b', desc, re.IGNORECASE) and not seg.get('capacity')
            if or_desc:
                desc = re.sub(r'\b\d+\s*ml\b', '', desc, flags=re.IGNORECASE)
                desc = re.sub(r'\b\d+\s*oz\b', '', desc, flags=re.IGNORECASE)
                desc = re.sub(r'\s{2,}', ' ', desc).strip()
            enriched = await _enrich_query(desc)
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
            # Strict filter was active but returned nothing — try type-keyword filter before going
            # fully unfiltered. Catches oz→ml rounding mismatches (e.g. 16oz=473ml vs 475ml).
            if attr_filter and len(filtered_rows) == 0 and seg.get('type'):
                type_f, type_p = _build_type_filter(seg['type'])
                if type_f:
                    type_result = await db.execute(
                        text(base_sql.format(where=f'WHERE {type_f}')),
                        {**base_params, **type_p, 'k': candidates_k * 4},
                    )
                    type_rows = type_result.mappings().all()
                    if len(type_rows) >= top_k:
                        return list(type_rows)
            unfiltered_result = await db.execute(text(base_sql.format(where='')), base_params)
            return list(unfiltered_result.mappings().all())

        # AsyncSession is not safe for concurrent use — run segments sequentially
        segment_rows = []
        for seg in segments:
            segment_rows.append(await _search_segment(seg))

        n_segs = len(segments)
        slots = (top_k + n_segs - 1) // n_segs  # ceil(top_k / n_segs) per segment

        # Rerank each segment independently against its own description query,
        # then take `slots` from each — prevents one dominant segment from flooding all slots.
        seen = set(exact_skus)
        per_seg_results: list[dict] = []
        all_seg_candidates: list[dict] = []

        for seg, rows in zip(segments, segment_rows):
            seg_candidates = []
            for r in rows:
                d = _row_to_dict(r)
                if d['sku'] not in seen:
                    seen.add(d['sku'])
                    seg_candidates.append(d)
            all_seg_candidates.extend(seg_candidates)
            seg_top = await _rerank_or_queries(seg.get('description') or query, seg_candidates, slots)
            per_seg_results.extend(seg_top)

        # Fill any remaining slots with a global rerank over leftover candidates
        top_skus = {p['sku'] for p in per_seg_results}
        extras = [c for c in all_seg_candidates if c['sku'] not in top_skus]
        remaining = top_k - len(exact_hits) - len(per_seg_results)
        extras_top = await _rerank(query, extras, remaining) if remaining > 0 and extras else []

        variants = await _expand_variants(all_seg_candidates, db, seen)

        merged = exact_hits + per_seg_results + extras_top + variants
        # Final dedup preserving order
        final_seen: set[str] = set()
        final: list[dict] = []
        for p in merged:
            if p['sku'] not in final_seen:
                final_seen.add(p['sku'])
                final.append(p)
        return final[:top_k]
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
