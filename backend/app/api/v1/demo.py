import json
import pathlib
import random
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr

from fastapi import APIRouter, HTTPException
from app.core.config import settings

router = APIRouter()

_DATASET_PATH = pathlib.Path(__file__).resolve().parent.parent.parent.parent / 'data' / 'eval_dataset.json'
_DEMO_CASES = {'case_01', 'case_02', 'case_03', 'case_06', 'case_08', 'case_10', 'case_11'}

_ADJ  = ['swift', 'bright', 'calm', 'bold', 'crisp', 'fresh', 'keen', 'warm', 'clear', 'sharp']
_NOUN = ['maple', 'river', 'stone', 'cloud', 'petal', 'grove', 'ember', 'crest', 'meadow', 'tide']

def _run_tag() -> str:
    return f"{random.choice(_ADJ)}-{random.choice(_NOUN)}"

SMTP_HOST = 'smtp.gmail.com'
SMTP_PORT = 587


def _load_cases() -> list[dict]:
    all_cases = json.loads(_DATASET_PATH.read_text())
    return [c for c in all_cases if c['id'] in _DEMO_CASES]


@router.get('/cases')
async def list_cases():
    return _load_cases()


@router.post('/cases/{case_id}/send')
async def send_case_email(case_id: str):
    cases = _load_cases()
    case = next((c for c in cases if c['id'] == case_id), None)
    if case is None:
        raise HTTPException(status_code=404, detail='Case not found')

    if not settings.smtp_user or not settings.smtp_password:
        raise HTTPException(status_code=503, detail='SMTP_USER / SMTP_PASSWORD not configured')

    smtp_user = settings.smtp_user.strip()
    smtp_password = settings.smtp_password.strip()

    mime = MIMEMultipart('alternative')
    mime['From'] = formataddr((f'{case["contact"]} - {case["customer"]}', smtp_user))
    mime['To'] = settings.demo_target_email
    mime['Subject'] = f"{case['email_subject']} [{_run_tag()}]"
    mime['X-Eval-Case-Id'] = case_id
    mime.attach(MIMEText(case['email_body'], 'plain'))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.send_message(mime)
    except smtplib.SMTPException as e:
        raise HTTPException(status_code=502, detail=f'SMTP error: {e}')

    return {'sent': True, 'case_id': case_id, 'to': settings.demo_target_email, 'subject': case['email_subject']}
