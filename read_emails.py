"""Milestone 1: print your 10 newest inbox emails.

Usage:  python read_emails.py personal
"""
import sys

from gmail_client import get_email, get_service, list_message_ids

account = sys.argv[1] if len(sys.argv) > 1 else "personal"
service = get_service(account)

for i, msg_id in enumerate(list_message_ids(service, "in:inbox", 10), 1):
    mail = get_email(service, msg_id)
    print(f"{i}. From:    {mail['from']}")
    print(f"   Subject: {mail['subject']}")
    print(f"   Text:    {mail['text'][:120]!r}\n")
