"""Move everything in your spammail label to Trash (after you've reviewed it).

Usage:  python trash_spam.py personal
"""
import sys

from gmail_client import get_service, list_message_ids, trash_messages

account = sys.argv[1] if len(sys.argv) > 1 else "personal"
service = get_service(account)

ids = list_message_ids(service, "label:spammail", 100000)
print(f"{len(ids)} emails are in the spammail label.")
if not ids:
    raise SystemExit("Nothing to do.")

answer = input("Type TRASH to move them all to Trash: ")
if answer.strip() == "TRASH":
    trash_messages(service, ids)
    print("Done. Open Gmail > Trash > 'Empty Trash now' to free up storage.")
else:
    print("Cancelled. Nothing was changed.")
