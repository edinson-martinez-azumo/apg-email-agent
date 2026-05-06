import json
import os
from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse
from google_auth_oauthlib.flow import Flow
from app.core.config import settings

router = APIRouter()

TOKEN_FILE = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'gmail_token.json')

# Store flow between /gmail and /callback requests (keyed by OAuth state param)
_pending_flows: dict[str, Flow] = {}

CLIENT_CONFIG = {
    'web': {
        'client_id': settings.gmail_client_id,
        'client_secret': settings.gmail_client_secret,
        'redirect_uris': [settings.gmail_redirect_uri],
        'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
        'token_uri': 'https://oauth2.googleapis.com/token',
    }
}


@router.get('/gmail')
async def gmail_auth():
    flow = Flow.from_client_config(
        CLIENT_CONFIG,
        scopes=settings.gmail_scopes.split(','),
        redirect_uri=settings.gmail_redirect_uri,
    )
    auth_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent',
    )
    _pending_flows[state] = flow
    return RedirectResponse(auth_url)


@router.get('/callback')
async def gmail_callback(code: str, state: str):
    flow = _pending_flows.pop(state, None)
    if flow is None:
        raise HTTPException(status_code=400, detail='Invalid or expired OAuth state. Restart auth flow.')

    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
    flow.fetch_token(code=code)

    creds = flow.credentials
    token_data = {
        'token': creds.token,
        'refresh_token': creds.refresh_token,
        'token_uri': creds.token_uri,
        'client_id': creds.client_id,
        'client_secret': creds.client_secret,
        'scopes': list(creds.scopes or []),
    }
    with open(TOKEN_FILE, 'w') as f:
        json.dump(token_data, f)
    return {'status': 'authenticated', 'message': 'Gmail connected successfully'}
