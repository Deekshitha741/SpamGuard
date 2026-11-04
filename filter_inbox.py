"""Step 4: find spam in your inbox and move it to a 'spammail' label.

By default this is a DRY RUN: it only prints what it WOULD do.
Add --apply to really move emails (they leave the inbox, nothing is deleted).

Usage:
  python filter_inbox.py personal --limit 100              # dry run
  python filter_inbox.py personal --limit 100 --apply      # do it
  python filter_inbox.py personal --limit 5000 --apply     # clear a backlog
"""
import argparse
import time

from googleapiclient.errors import HttpError

from gmail_client import (
    batch_modify,
    get_email,
    get_or_create_label,
    get_service,
    list_message_ids,
)
from model import build_text, spam_scores

SPAM_LABEL_NAME = "spammail"
CHECKED_LABEL_NAME = "checked-mail"  # marks emails we've already judged
BATCH = 50


def load_allowlist(path="allowlist.txt"):
    try:
        with open(path) as f:
            return [l.strip().lower() for l in f
                    if l.strip() and not l.startswith("#")]
    except FileNotFoundError:
        return []


def is_allowed(sender, allowlist):
    return any(entry in sender.lower() for entry in allowlist)


parser = argparse.ArgumentParser()
parser.add_argument("account", nargs="?", default="personal")
parser.add_argument("--limit", type=int, default=100, help="max emails this run")
parser.add_argument("--threshold", type=float, default=0.85,
                    help="spam score needed to move an email (0-1)")
parser.add_argument("--max-minutes", type=float, default=0,
                    help="stop cleanly after this many minutes (0 = no limit)")
parser.add_argument("--apply", action="store_true", help="really move emails")
args = parser.parse_args()

service = get_service(args.account)
allowlist = load_allowlist()

query = f"in:inbox -label:{CHECKED_LABEL_NAME}"
ids = list_message_ids(service, query, args.limit)
mode = "APPLYING" if args.apply else "DRY RUN (nothing will change)"
print(f"{len(ids)} unchecked inbox emails found. {mode}\n")
print(f"Estimated time: about {max(1, round(len(ids) / 75))} minute(s) (Gmail speed limit).\n")

if args.apply:
    spam_label = get_or_create_label(service, SPAM_LABEL_NAME)
    checked_label = get_or_create_label(service, CHECKED_LABEL_NAME)

total_spam = 0
scanned = 0
started = time.time()
for start in range(0, len(ids), BATCH):
    if args.max_minutes and time.time() - started > args.max_minutes * 60:
        print("Time limit reached. The next run will continue from here.")
        break
    mails = []
    for msg_id in ids[start:start + BATCH]:
        try:
            mails.append(get_email(service, msg_id))
        except HttpError:
            continue  # email vanished meanwhile, skip it

    scores = spam_scores([build_text(m) for m in mails])
    spam_ids, ok_ids = [], []
    for mail, score in zip(mails, scores):
        protected = "STARRED" in mail["labels"] or is_allowed(mail["from"], allowlist)
        is_spam = score >= args.threshold and not protected
        (spam_ids if is_spam else ok_ids).append(mail["id"])
        if not args.apply:
            tag = "SPAM" if is_spam else ("safe" if protected else "ok  ")
            print(f"[{tag}] {score:.3f}  {mail['subject'][:50]}  <{mail['from'][:30]}>")

    if args.apply:
        # spam: add labels, take out of inbox. not spam: just mark as checked.
        batch_modify(service, spam_ids, add=[spam_label, checked_label], remove=["INBOX"])
        batch_modify(service, ok_ids, add=[checked_label])

    total_spam += len(spam_ids)
    scanned += len(mails)
    done = min(start + BATCH, len(ids))
    print(f"Processed {done}/{len(ids)}  |  spam so far: {total_spam}")

print(f"\nDone. {total_spam} of {scanned} scanned emails flagged as spam.")
if not args.apply:
    print("This was a dry run. Add --apply to move them.")
