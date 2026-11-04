"""Helpers for talking to the Gmail API (with a built-in speed limit)."""
import base64
import os
import time
from collections import deque
from html.parser import HTMLParser

import httplib2
from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_httplib2 import AuthorizedHttp
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# gmail.modify lets us read mail, add/remove labels and move to Trash.
# It does NOT allow permanent delete (that's intentional and safer).
SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]

# Gmail allows about 6,000 "quota units" per minute per user. We stay under
# that. Costs: reading a full email = 60, list page = 5, batchModify = 50,
# trash = 20, labels = 1-5.
QUOTA_PER_MINUTE = 5000


class _Throttle:
    """Sliding 60-second window: waits if we're about to spend too many units."""

    def __init__(self):
        self.log = deque()  # (timestamp, units)

    def spend(self, units):
        while True:
            now = time.time()
            while self.log and now - self.log[0][0] >= 60:
                self.log.popleft()
            used = sum(u for _, u in self.log)
            if not self.log or used + units <= QUOTA_PER_MINUTE:
                break
            time.sleep(max(0.5, 60 - (now - self.log[0][0])))
        self.log.append((time.time(), units))


_throttle = _Throttle()


def call(request, cost):
    """Run a Gmail request: respect the speed limit, retry if Gmail says 'slow down'."""
    for attempt in range(6):
        _throttle.spend(cost)
        try:
            return request.execute()
        except HttpError as err:
            text = str(err)
            too_fast = err.resp.status == 429 or (
                err.resp.status == 403
                and ("rateLimitExceeded" in text or "Quota exceeded" in text)
            )
            if not too_fast:
                raise
            print("  Gmail says slow down. Waiting 65 seconds, then retrying...")
            time.sleep(65)
        except (TimeoutError, ConnectionError):
            print("  Network hiccup. Waiting 5 seconds, then retrying...")
            time.sleep(5)
    raise RuntimeError("Gmail kept refusing the request. Try again in a few minutes.")


def token_path(account):
    return f"token_{account}.json"


def get_service(account="personal"):
    """Return a Gmail API client for one saved account."""
    path = token_path(account)
    if not os.path.exists(path):
        raise SystemExit(f"No token for '{account}'. Run: python auth.py {account}")

    creds = Credentials.from_authorized_user_file(path, SCOPES)
    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except RefreshError:
            raise SystemExit(
                f"Token for '{account}' expired or was revoked. "
                f"Run: python auth.py {account}"
            )
        with open(path, "w") as f:
            f.write(creds.to_json())
    # timeout=60 stops the program hanging forever on a dead connection
    http = AuthorizedHttp(creds, http=httplib2.Http(timeout=60))
    return build("gmail", "v1", http=http)


def list_message_ids(service, query="in:inbox", limit=10):
    """Return up to `limit` message IDs matching a Gmail search query."""
    ids, page_token = [], None
    while len(ids) < limit:
        resp = call(
            service.users().messages().list(
                userId="me",
                q=query,
                maxResults=min(500, limit - len(ids)),
                pageToken=page_token,
            ),
            5,
        )
        ids += [m["id"] for m in resp.get("messages", [])]
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return ids


class _HTMLToText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def _html_to_text(html):
    parser = _HTMLToText()
    parser.feed(html)
    return " ".join(" ".join(parser.parts).split())


def _decode(data):
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)).decode(
        "utf-8", errors="replace"
    )


def _extract_text(payload):
    """Walk the MIME tree; prefer text/plain, fall back to stripped HTML."""
    plain, html = [], []

    def walk(part):
        mime = part.get("mimeType", "")
        data = part.get("body", {}).get("data")
        if data and mime == "text/plain":
            plain.append(_decode(data))
        elif data and mime == "text/html":
            html.append(_decode(data))
        for sub in part.get("parts", []):
            walk(sub)

    walk(payload)
    if plain:
        return " ".join(" ".join(plain).split())
    return _html_to_text(" ".join(html))


def get_email(service, msg_id):
    """Fetch one email and return a simple dict."""
    msg = call(
        service.users().messages().get(userId="me", id=msg_id, format="full"), 60
    )
    headers = {h["name"].lower(): h["value"] for h in msg["payload"]["headers"]}
    return {
        "id": msg_id,
        "from": headers.get("from", ""),
        "subject": headers.get("subject", "(no subject)"),
        "labels": msg.get("labelIds", []),
        "text": _extract_text(msg["payload"]) or msg.get("snippet", ""),
    }


# ---------------------------------------------------------------------------
# Labels, moving mail, trashing mail
# ---------------------------------------------------------------------------
def get_or_create_label(service, name):
    """Return the ID of a Gmail label, creating it if it doesn't exist."""
    labels = call(service.users().labels().list(userId="me"), 1).get("labels", [])
    for label in labels:
        if label["name"].lower() == name.lower():
            return label["id"]
    created = call(
        service.users().labels().create(
            userId="me",
            body={
                "name": name,
                "labelListVisibility": "labelShow",
                "messageListVisibility": "show",
            },
        ),
        5,
    )
    return created["id"]


def batch_modify(service, ids, add=None, remove=None):
    """Add/remove labels on many emails at once (Gmail allows 1000 per call)."""
    if not ids:
        return
    for start in range(0, len(ids), 1000):
        call(
            service.users().messages().batchModify(
                userId="me",
                body={
                    "ids": ids[start:start + 1000],
                    "addLabelIds": add or [],
                    "removeLabelIds": remove or [],
                },
            ),
            50,
        )


def trash_messages(service, ids):
    """Move emails to Trash (recoverable for 30 days)."""
    for n, msg_id in enumerate(ids, 1):
        call(service.users().messages().trash(userId="me", id=msg_id), 20)
        if n % 50 == 0 or n == len(ids):
            print(f"  trashed {n}/{len(ids)}")
