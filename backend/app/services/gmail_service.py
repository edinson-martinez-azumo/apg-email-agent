import base64
import datetime
import json
import re
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.models.app_setting import AppSetting


async def get_token(db: AsyncSession) -> dict:
    result = await db.execute(select(AppSetting).where(AppSetting.key == 'gmail_token'))
    row = result.scalar_one_or_none()
    if row is None:
        raise RuntimeError('Gmail not connected. Complete OAuth flow at /api/v1/auth/gmail')
    return json.loads(row.value)


def _get_service(token_data: dict) -> Any:
    creds = Credentials.from_authorized_user_info(token_data)
    return build('gmail', 'v1', credentials=creds)


def list_unread_messages(token_data: dict, max_results: int = 20) -> list[dict[str, Any]]:
    service = _get_service(token_data)
    result = service.users().messages().list(
        userId='me',
        q='is:unread in:inbox',
        maxResults=max_results,
    ).execute()
    return result.get('messages', [])


def get_message(token_data: dict, message_id: str) -> dict[str, Any]:
    service = _get_service(token_data)
    return service.users().messages().get(
        userId='me',
        id=message_id,
        format='full',
    ).execute()


def parse_message(msg: dict[str, Any]) -> dict[str, Any]:
    headers = {h['name'].lower(): h['value'] for h in msg.get('payload', {}).get('headers', [])}

    raw_from = headers.get('from', '')
    if '<' in raw_from:
        from_name = raw_from.split('<')[0].strip().strip('"')
        from_email = raw_from.split('<')[1].rstrip('>')
    else:
        from_name = None
        from_email = raw_from.strip()

    subject = headers.get('subject')
    ts_ms = int(msg.get('internalDate', 0))
    received_at = datetime.datetime.fromtimestamp(ts_ms / 1000, tz=datetime.timezone.utc)
    body_text = _extract_body(msg.get('payload', {}))

    return {
        'gmail_id': msg['id'],
        'thread_id': msg.get('threadId'),
        'from_email': from_email,
        'from_name': from_name,
        'subject': subject,
        'body_text': body_text,
        'received_at': received_at,
    }


def _extract_body(payload: dict[str, Any]) -> str | None:
    mime_type = payload.get('mimeType', '')
    if mime_type == 'text/plain':
        data = payload.get('body', {}).get('data', '')
        return base64.urlsafe_b64decode(data + '==').decode('utf-8', errors='replace') if data else None
    parts = payload.get('parts', [])
    for part in parts:
        result = _extract_body(part)
        if result:
            return result
    return None


def _inline_md(text: str) -> str:
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
    return text


def _text_to_html(text: str) -> str:
    lines = text.split('\n')
    html_lines = []
    in_list = False

    for line in lines:
        if line.strip().startswith('|') and line.strip().endswith('|'):
            if in_list:
                html_lines.append('</ul>')
                in_list = False
            cells = [c.strip() for c in line.strip().strip('|').split('|')]
            if all(set(c) <= set('- ') for c in cells):
                continue
            row_html = ''.join(f'<td style="padding:6px 12px;border:1px solid #e5e7eb;font-size:13px;">{_inline_md(c)}</td>' for c in cells)
            html_lines.append(f'<table style="border-collapse:collapse;width:100%;margin:8px 0;"><tr>{row_html}</tr></table>')
            continue

        img_match = re.match(r'^!\[([^\]]*)\]\(([^)]+)\)\s*$', line.strip())
        if img_match:
            if in_list:
                html_lines.append('</ul>')
                in_list = False
            alt, src = img_match.group(1), img_match.group(2)
            html_lines.append(f'<img src="{src}" alt="{alt}" style="display:block;max-width:200px;height:auto;margin:6px 0 10px;border-radius:6px;">')
            continue

        if line.startswith('### '):
            if in_list: html_lines.append('</ul>'); in_list = False
            html_lines.append(f'<h3 style="margin:16px 0 6px;font-size:15px;font-weight:600;">{_inline_md(line[4:])}</h3>')
        elif line.startswith('## '):
            if in_list: html_lines.append('</ul>'); in_list = False
            html_lines.append(f'<h2 style="margin:20px 0 8px;font-size:17px;font-weight:600;">{_inline_md(line[3:])}</h2>')
        elif line.startswith('# '):
            if in_list: html_lines.append('</ul>'); in_list = False
            html_lines.append(f'<h1 style="margin:20px 0 8px;font-size:19px;font-weight:700;">{_inline_md(line[2:])}</h1>')
        elif re.match(r'^[-*]\s', line):
            if not in_list:
                html_lines.append('<ul style="margin:8px 0;padding-left:20px;">')
                in_list = True
            html_lines.append(f'<li style="margin:4px 0;font-size:15px;">{_inline_md(line[2:])}</li>')
        elif line.strip() == '':
            if in_list:
                html_lines.append('</ul>')
                in_list = False
            html_lines.append('<br>')
        else:
            if in_list:
                html_lines.append('</ul>')
                in_list = False
            html_lines.append(f'<p style="margin:0 0 12px;">{_inline_md(line)}</p>')

    if in_list:
        html_lines.append('</ul>')

    return '\n'.join(html_lines)


def _html_to_text(html: str) -> str:
    text = re.sub(r'<br\s*/?>', '\n', html, flags=re.IGNORECASE)
    text = re.sub(r'</p>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<li[^>]*>', '- ', text, flags=re.IGNORECASE)
    text = re.sub(r'</li>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</(ul|ol|h[1-6]|div|tr|table)>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<img[^>]*>', '', text, flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


async def send_reply(
    token_data: dict,
    original_gmail_id: str,
    to_email: str,
    subject: str,
    body: str,
) -> None:
    service = _get_service(token_data)
    original = service.users().messages().get(
        userId='me',
        id=original_gmail_id,
        format='metadata',
        metadataHeaders=['Message-ID', 'References'],
    ).execute()

    headers = {h['name']: h['value'] for h in original.get('payload', {}).get('headers', [])}
    message_id_header = headers.get('Message-ID', '')
    thread_id = original.get('threadId', '')
    reply_subject = f"Re: {subject}" if not subject.startswith('Re:') else subject

    clean_body = re.sub(
        r'\n?APG Sales Team\s*\|.*?apackaginggroup\.com.*$',
        '',
        body,
        flags=re.IGNORECASE | re.DOTALL,
    ).strip()

    if clean_body.strip().startswith('<'):
        inner_html = clean_body
        plain_text = _html_to_text(clean_body)
    else:
        inner_html = _text_to_html(clean_body)
        plain_text = clean_body

    html_body = (
        '<!DOCTYPE html><html><head><meta charset="UTF-8"></head>'
        '<body style="font-family:-apple-system,BlinkMacSystemFont,\'Segoe UI\',Roboto,sans-serif;'
        'font-size:15px;line-height:1.7;color:#333333;max-width:600px;">'
        f'{inner_html}'
        '</body></html>'
    )

    mime = MIMEMultipart('alternative')
    mime['to'] = to_email
    mime['subject'] = reply_subject
    if message_id_header:
        mime['In-Reply-To'] = message_id_header
        mime['References'] = message_id_header
    mime.attach(MIMEText(plain_text, 'plain'))
    mime.attach(MIMEText(html_body, 'html'))

    raw = base64.urlsafe_b64encode(mime.as_bytes()).decode()
    service.users().messages().send(
        userId='me',
        body={'raw': raw, 'threadId': thread_id},
    ).execute()
