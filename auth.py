"""Run this on your laptop to connect a Gmail account.

Usage:  python auth.py personal
        python auth.py work        (a second account)
"""
import sys

from google_auth_oauthlib.flow import InstalledAppFlow

from gmail_client import SCOPES, token_path

account = sys.argv[1] if len(sys.argv) > 1 else "personal"

flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
# prompt="consent" makes sure Google gives us a refresh token
creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")

with open(token_path(account), "w") as f:
    f.write(creds.to_json())
print(f"Saved {token_path(account)}. You're connected!")
