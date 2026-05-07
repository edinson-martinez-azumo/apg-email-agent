import anthropic
import cohere
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.core.config import settings

EMBED_MODEL = 'embed-english-light-v3.0'
EMBED_DIMS = 384

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


def _get_cohere() -> cohere.AsyncClientV2:
    global _cohere
    if _cohere is None:
        _cohere = cohere.AsyncClientV2(api_key=settings.cohere_api_key)
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


async def embed(text_input: str) -> list[float]:
    resp = await _get_cohere().embed(
        texts=[text_input],
        model=EMBED_MODEL,
        input_type='search_query',
        embedding_types=['float'],
    )
    return resp.embeddings.float_[0]


async def search_products(query: str, db: AsyncSession, top_k: int = 8) -> list[dict]:
    """
    Hybrid search: cosine similarity (0.7) + full-text ts_rank (0.3).
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

    enriched = await _enrich_query(query)
    query_embedding = await embed(enriched)

    if has_metadata:
        sql = text("""
            SELECT
                sku, title, type, materials, moq, capacities,
                price_base, price_10k, price_25k, price_50k, price_100k, in_stock,
                (0.7 * (1 - (embedding <=> CAST(:vec AS vector))) +
                 0.3 * ts_rank(search_vector_ts, plainto_tsquery('english', :q))) AS score
            FROM product_embeddings
            ORDER BY score DESC
            LIMIT :k
        """)
        result = await db.execute(sql, {'vec': str(query_embedding), 'q': query, 'k': top_k})
        rows = result.mappings().all()
        return [
            {
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
            }
            for r in rows
        ]
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
