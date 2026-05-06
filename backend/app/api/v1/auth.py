import json
import secrets
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from google_auth_oauthlib.flow import Flow
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from app.core.config import settings
from app.core.deps import get_db
from app.db.models.app_setting import AppSetting

router = APIRouter()

CLIENT_CONFIG = {
    'web': {
        'client_id': settings.gmail_client_id,
        'client_secret': settings.gmail_client_secret,
        'redirect_uris': [settings.gmail_redirect_uri],
        'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
        'token_uri': 'https://oauth2.googleapis.com/token',
    }
}


def _make_flow() -> Flow:
    return Flow.from_client_config(
        CLIENT_CONFIG,
        scopes=settings.gmail_scopes.split(','),
        redirect_uri=settings.gmail_redirect_uri,
    )


@router.get('/gmail')
async def gmail_auth(db: AsyncSession = Depends(get_db)):
    state = secrets.token_urlsafe(32)

    flow = _make_flow()
    auth_url, _ = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent',
        state=state,
    )

    # Persist code_verifier so PKCE survives across serverless instances
    code_verifier = getattr(flow.oauth2session, '_code_verifier', '') or ''
    await db.merge(AppSetting(key=f'oauth_state:{state}', value=code_verifier))
    await db.commit()

    return RedirectResponse(auth_url)


@router.get('/callback')
async def gmail_callback(code: str, state: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(AppSetting).where(AppSetting.key == f'oauth_state:{state}')
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=400, detail='Invalid or expired OAuth state. Restart auth flow.')

    code_verifier = row.value
    await db.execute(delete(AppSetting).where(AppSetting.key == f'oauth_state:{state}'))

    flow = _make_flow()
    try:
        fetch_kwargs = {'code': code}
        if code_verifier:
            fetch_kwargs['code_verifier'] = code_verifier
        flow.fetch_token(**fetch_kwargs)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f'fetch_token failed: {exc}')

    creds = flow.credentials
    token_data = {
        'token': creds.token,
        'refresh_token': creds.refresh_token,
        'token_uri': creds.token_uri,
        'client_id': creds.client_id,
        'client_secret': creds.client_secret,
        'scopes': list(creds.scopes or []),
    }
    await db.merge(AppSetting(key='gmail_token', value=json.dumps(token_data)))
    await db.commit()

    return {'status': 'authenticated', 'message': 'Gmail connected successfully'}


@router.get('/status')
async def auth_status(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(AppSetting).where(AppSetting.key == 'gmail_token')
    )
    row = result.scalar_one_or_none()
    return {'connected': row is not None}
