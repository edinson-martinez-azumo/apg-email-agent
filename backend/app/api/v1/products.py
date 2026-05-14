from fastapi import APIRouter, Query
from app.services import product_service

router = APIRouter()


@router.get('/search')
async def search_products(
    q: str = Query(..., min_length=1),
    limit: int = Query(12, le=24),
):
    return product_service.search(q, top_k=limit)
