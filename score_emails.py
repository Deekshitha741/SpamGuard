"""Milestone 2: score your emails with the model (read-only, moves nothing).

Usage:  python score_emails.py personal
        python score_emails.py personal "in:spam"             # Gmail's own spam
        python score_emails.py personal "category:promotions" # check false alarms
"""
import sys

from gmail_client import get_email, get_service, list_message_ids
from model import build_text, spam_scores

THRESHOLD = 0.90  # only call it spam when the model is very sure

account = sys.argv[1] if len(sys.argv) > 1 else "personal"
query = sys.argv[2] if len(sys.argv) > 2 else "in:inbox"

service = get_service(account)
mails = [get_email(service, i) for i in list_message_ids(service, query, 10)]
scores = spam_scores([build_text(m) for m in mails])

print(f"Query: {query}\n")
for mail, score in zip(mails, scores):
    verdict = "SPAM" if score >= THRESHOLD else "ok  "
    print(f"[{verdict}] {score:.3f}  {mail['subject'][:50]}  <{mail['from'][:35]}>")
