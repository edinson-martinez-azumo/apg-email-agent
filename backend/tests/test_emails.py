import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health(client: AsyncClient):
    response = await client.get('/api/health')
    assert response.status_code == 200
    data = response.json()
    assert data['status'] == 'ok'
    assert data['db'] == 'connected'


@pytest.mark.asyncio
async def test_list_emails_empty(client: AsyncClient):
    response = await client.get('/api/v1/emails/')
    assert response.status_code == 200
    data = response.json()
    assert data['items'] == []
    assert data['total'] == 0


@pytest.mark.asyncio
async def test_get_email_not_found(client: AsyncClient):
    response = await client.get('/api/v1/emails/nonexistent-id')
    assert response.status_code == 404
