import base64
import datetime
import json
import os
import re
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

TOKEN_FILE = os.path.join(os.path.dirname(__file__), '..', '..', 'gmail_token.json')

APG_BLUE = '#00A3E7'
APG_BLUE_DARK = '#1276BD'
APG_BLACK = '#333333'
APG_OFFWHITE = '#F5F9FC'
APG_GRAY = '#666666'

APG_GREEN = APG_BLUE  # alias kept for template compatibility

HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background-color:#f4f4f2;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f4f4f2;padding:32px 16px;">
    <tr><td align="center">
      <table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 1px 4px rgba(0,0,0,0.08);">

        <!-- Header -->
        <tr>
          <td style="background-color:{green};padding:24px 32px;">
            <table width="100%" cellpadding="0" cellspacing="0">
              <tr>
                <td>
                  <span style="font-size:20px;font-weight:700;color:#ffffff;letter-spacing:-0.3px;">APackaging Group</span>
                  <br>
                  <span style="font-size:12px;color:rgba(255,255,255,0.75);letter-spacing:0.5px;">PACKAGING SOLUTIONS</span>
                </td>
                <td align="right">
                  <span style="font-size:11px;color:rgba(255,255,255,0.6);">apackaginggroup.com</span>
                </td>
              </tr>
            </table>
          </td>
        </tr>

        <!-- Body -->
        <tr>
          <td style="padding:32px;">
            <div style="font-size:15px;line-height:1.7;color:{black};">
              {body_html}
            </div>
          </td>
        </tr>

        <!-- Divider -->
        <tr>
          <td style="padding:0 32px;">
            <hr style="border:none;border-top:1px solid #e5e7eb;margin:0;">
          </td>
        </tr>

        <!-- Footer / Signature -->
        <tr>
          <td style="padding:24px 32px;">
            <table cellpadding="0" cellspacing="0">
              <tr>
                <td style="border-left:3px solid {green};padding-left:12px;">
                  <p style="margin:0;font-size:14px;font-weight:600;color:{black};">APG Sales Team</p>
                  <p style="margin:4px 0 0;font-size:13px;color:{gray};">APackaging Group</p>
                  <p style="margin:4px 0 0;font-size:13px;">
                    <a href="https://apackaginggroup.com" style="color:{green};text-decoration:none;">apackaginggroup.com</a>
                  </p>
                  <p style="margin:4px 0 0;font-size:12px;color:{gray};">Azusa, California</p>
                </td>
              </tr>
            </table>
          </td>
        </tr>

        <!-- Bottom bar -->
        <tr>
          <td style="background-color:{offwhite};padding:14px 32px;border-top:1px solid #e5e7eb;">
            <p style="margin:0;font-size:11px;color:{gray};text-align:center;">
              This email was sent by APackaging Group ·
              <a href="https://apackaginggroup.com" style="color:{green};text-decoration:none;">apackaginggroup.com</a>
            </p>
          </td>
        </tr>

      </table>
    </td></tr>
  </table>
</body>
</html>
""".replace('{green}', APG_BLUE).replace('{black}', APG_BLACK).replace('{gray}', APG_GRAY).replace('{offwhite}', APG_OFFWHITE)


def _text_to_html(text: str) -> str:
    """Convert plain text draft (with basic markdown) to HTML for email."""
    lines = text.split('\n')
    html_lines = []
    in_list = False

    for line in lines:
        # Table rows (| col | col |) — render as simple styled divs
        if line.strip().startswith('|') and line.strip().endswith('|'):
            if in_list:
                html_lines.append('</ul>')
                in_list = False
            cells = [c.strip() for c in line.strip().strip('|').split('|')]
            if all(set(c) <= set('- ') for c in cells):
                continue  # skip separator row
            row_html = ''.join(f'<td style="padding:6px 12px;border:1px solid #e5e7eb;font-size:13px;">{_inline_md(c)}</td>' for c in cells)
            html_lines.append(f'<table style="border-collapse:collapse;width:100%;margin:8px 0;"><tr>{row_html}</tr></table>')
            continue

        # Headings
        if line.startswith('### '):
            if in_list: html_lines.append('</ul>'); in_list = False
            html_lines.append(f'<h3 style="margin:16px 0 6px;font-size:15px;font-weight:600;color:{APG_BLUE_DARK};">{_inline_md(line[4:])}</h3>')
        elif line.startswith('## '):
            if in_list: html_lines.append('</ul>'); in_list = False
            html_lines.append(f'<h2 style="margin:20px 0 8px;font-size:17px;font-weight:600;color:{APG_BLUE_DARK};">{_inline_md(line[3:])}</h2>')
        elif line.startswith('# '):
            if in_list: html_lines.append('</ul>'); in_list = False
            html_lines.append(f'<h1 style="margin:20px 0 8px;font-size:19px;font-weight:700;color:{APG_BLUE_DARK};">{_inline_md(line[2:])}</h1>')
        # List items
        elif re.match(r'^[-*]\s', line):
            if not in_list:
                html_lines.append('<ul style="margin:8px 0;padding-left:20px;">')
                in_list = True
            html_lines.append(f'<li style="margin:4px 0;font-size:15px;">{_inline_md(line[2:])}</li>')
        # Empty line
        elif line.strip() == '':
            if in_list:
                html_lines.append('</ul>')
                in_list = False
            html_lines.append('<br>')
        # Normal paragraph
        else:
            if in_list:
                html_lines.append('</ul>')
                in_list = False
            html_lines.append(f'<p style="margin:0 0 12px;">{_inline_md(line)}</p>')

    if in_list:
        html_lines.append('</ul>')

    return '\n'.join(html_lines)


def _inline_md(text: str) -> str:
    """Convert inline markdown (**bold**, *italic*) to HTML."""
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
    return text


def _get_service() -> Any:
    if not os.path.exists(TOKEN_FILE):
        raise RuntimeError('Gmail token not found. Complete OAuth flow at /api/v1/auth/gmail')
    with open(TOKEN_FILE) as f:
        token_data = json.load(f)
    creds = Credentials.from_authorized_user_info(token_data)
    return build('gmail', 'v1', credentials=creds)


def list_unread_messages(max_results: int = 20) -> list[dict[str, Any]]:
    service = _get_service()
    result = service.users().messages().list(
        userId='me',
        q='is:unread in:inbox',
        maxResults=max_results,
    ).execute()
    return result.get('messages', [])


def get_message(message_id: str) -> dict[str, Any]:
    service = _get_service()
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


async def send_reply(
    original_gmail_id: str,
    to_email: str,
    subject: str,
    body: str,
) -> None:
    service = _get_service()
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

    # Build multipart email with plain text + HTML
    mime = MIMEMultipart('alternative')
    mime['to'] = to_email
    mime['subject'] = reply_subject
    if message_id_header:
        mime['In-Reply-To'] = message_id_header
        mime['References'] = message_id_header

    # Remove Claude's own signature line if present (we add our own)
    clean_body = re.sub(
        r'\n?APG Sales Team\s*\|.*?apackaginggroup\.com.*$',
        '',
        body,
        flags=re.IGNORECASE | re.DOTALL,
    ).strip()

    mime.attach(MIMEText(clean_body, 'plain'))
    html_body = HTML_TEMPLATE.replace('{body_html}', _text_to_html(clean_body))
    mime.attach(MIMEText(html_body, 'html'))

    raw = base64.urlsafe_b64encode(mime.as_bytes()).decode()
    service.users().messages().send(
        userId='me',
        body={'raw': raw, 'threadId': thread_id},
    ).execute()
