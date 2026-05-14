import base64
import json
import pathlib
import re
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from fastapi import APIRouter, HTTPException
from googleapiclient.errors import HttpError
from app.core.deps import DB
from app.services.gmail_service import get_token, _get_service

router = APIRouter()

_DATASET_PATH = pathlib.Path(__file__).resolve().parent.parent.parent.parent / 'data' / 'eval_dataset.json'

_DEMO_CASES = {'case_01', 'case_02', 'case_03', 'case_06', 'case_08', 'case_10', 'case_11'}


def _load_cases() -> list[dict]:
    all_cases = json.loads(_DATASET_PATH.read_text())
    return [c for c in all_cases if c['id'] in _DEMO_CASES]


def _fake_email(contact: str, customer: str) -> str:
    parts = contact.lower().split()
    local = '.'.join(parts) if len(parts) >= 2 else parts[0]
    domain = re.sub(r'[^a-z0-9]', '', customer.lower()) + '.com'
    return f'{local}@{domain}'


@router.get('/cases')
async def list_cases():
    return _load_cases()


@router.post('/cases/{case_id}/send')
async def send_case_email(case_id: str, db: DB):
    cases = _load_cases()
    case = next((c for c in cases if c['id'] == case_id), None)
    if case is None:
        raise HTTPException(status_code=404, detail='Case not found')

    try:
        token_data = await get_token(db)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

    try:
        service = _get_service(token_data)
        profile = service.users().getProfile(userId='me').execute()
        gmail_address = profile['emailAddress']

        from_email = _fake_email(case['contact'], case['customer'])
        mime = MIMEMultipart('alternative')
        mime['From'] = f'"{case["contact"]}" <{from_email}>'
        mime['To'] = gmail_address
        mime['Subject'] = case['email_subject']
        mime.attach(MIMEText(case['email_body'], 'plain'))

        raw = base64.urlsafe_b64encode(mime.as_bytes()).decode()
        service.users().messages().insert(
            userId='me',
            body={'raw': raw, 'labelIds': ['INBOX', 'UNREAD']},
        ).execute()
    except HttpError as e:
        raise HTTPException(status_code=502, detail=f'Gmail API error: {e.reason}')
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {'sent': True, 'case_id': case_id, 'subject': case['email_subject']}
