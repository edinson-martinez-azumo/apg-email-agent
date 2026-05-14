"""
Send eval dataset cases as emails to a target address for end-to-end testing.

Usage (from backend/):
    uv run python scripts/send_eval_emails.py --to edinson.martinez@azumo.co           # all cases
    uv run python scripts/send_eval_emails.py --to edinson.martinez@azumo.co 1 3 5     # cases by number
    uv run python scripts/send_eval_emails.py --to edinson.martinez@azumo.co case_01 case_03
    uv run python scripts/send_eval_emails.py --to edinson.martinez@azumo.co --cases case_01,case_03
    uv run python scripts/send_eval_emails.py --to edinson.martinez@azumo.co --dry-run

Requires env vars (add to .env.local):
    SMTP_USER=your@gmail.com
    SMTP_PASSWORD=your-app-password   # Gmail app password (not account password)
    SMTP_FROM=Sender Name <your@gmail.com>  # optional
"""
import argparse
import json
import os
import smtplib
import sys
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env.local'))

EVAL_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'eval_dataset.json')
SMTP_HOST = 'smtp.gmail.com'
SMTP_PORT = 587
DELAY_SECONDS = 2  # between emails to avoid spam filters


def _load_cases(filter_ids: list[str] | None) -> list[dict]:
    with open(EVAL_PATH) as f:
        cases = json.load(f)
    cases = [c for c in cases if c.get('expected_skus')]  # skip cases with no ground truth
    if filter_ids:
        cases = [c for c in cases if c['id'] in filter_ids]
    return cases


def _build_message(case: dict, from_addr: str, to_addr: str) -> MIMEMultipart:
    msg = MIMEMultipart('alternative')
    msg['Subject'] = f"[{case['id']}] {case['email_subject']}"
    msg['From'] = from_addr
    msg['To'] = to_addr
    msg['X-Eval-Case-Id'] = case['id']
    msg['X-Eval-Customer'] = case['customer']

    body = case['email_body']
    msg.attach(MIMEText(body, 'plain'))
    return msg


def send(to: str, cases: list[str] | None, dry_run: bool) -> None:
    smtp_user = os.environ.get('SMTP_USER', '').strip()
    smtp_password = os.environ.get('SMTP_PASSWORD', '').strip()
    smtp_from = os.environ.get('SMTP_FROM', smtp_user).strip() or smtp_user

    if not smtp_user or not smtp_password:
        print('ERROR: SMTP_USER and SMTP_PASSWORD must be set in .env.local')
        sys.exit(1)

    all_cases = _load_cases(cases)
    if not all_cases:
        print('No cases matched.')
        return

    print(f'{"[DRY RUN] " if dry_run else ""}Sending {len(all_cases)} emails to {to}')
    print(f'From: {smtp_from}\n')

    if dry_run:
        for c in all_cases:
            print(f'  [{c["id"]}] {c["customer"]} — "{c["email_subject"]}" ({len(c["email_body"])} chars)')
        return

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.ehlo()
        server.starttls()
        server.login(smtp_user, smtp_password)

        for i, c in enumerate(all_cases):
            msg = _build_message(c, smtp_from, to)
            server.sendmail(smtp_from, [to], msg.as_string())
            print(f'  ✓ [{c["id"]}] {c["customer"]} — "{c["email_subject"]}"')
            if i < len(all_cases) - 1:
                time.sleep(DELAY_SECONDS)

    print(f'\nDone. {len(all_cases)} emails sent.')


def _normalize_case_id(s: str) -> str:
    """'1' → 'case_01', '03' → 'case_03', 'case_01' → 'case_01'."""
    s = s.strip()
    if s.startswith('case_'):
        return s
    return f'case_{int(s):02d}'


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--to', required=True, help='Target email address')
    parser.add_argument('--cases', help='Comma-separated case IDs (e.g. case_01,case_03). Default: all.')
    parser.add_argument('--dry-run', action='store_true', help='Print what would be sent without sending')
    parser.add_argument('cases_pos', nargs='*', metavar='CASE', help='Cases by number or ID (e.g. 1 3 case_05). Default: all.')
    args = parser.parse_args()

    case_ids: list[str] | None = None
    if args.cases:
        case_ids = [_normalize_case_id(c) for c in args.cases.split(',')]
    elif args.cases_pos:
        case_ids = [_normalize_case_id(c) for c in args.cases_pos]

    send(to=args.to, cases=case_ids, dry_run=args.dry_run)
