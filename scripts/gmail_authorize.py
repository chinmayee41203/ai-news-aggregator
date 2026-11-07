"""One-time Gmail sign-in for sending the digest through the Gmail API.

Before running: put the OAuth client file you downloaded from Google Cloud at
    credentials/client_secret.json

Run:  uv run python scripts/gmail_authorize.py

A browser window opens. Sign in with the Gmail account in MY_EMAIL. Google
shows "Google hasn't verified this app" (normal for a personal project):
click Advanced → Go to ... (unsafe) → Continue/Allow.

The resulting token is saved to credentials/gmail_token.json (gitignored).
It only allows *sending* email — not reading your inbox.
"""

import sys
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

ROOT = Path(__file__).resolve().parent.parent
CLIENT_FILE = ROOT / "credentials" / "client_secret.json"
TOKEN_FILE = ROOT / "credentials" / "gmail_token.json"
SCOPES = ["https://www.googleapis.com/auth/gmail.send"]


def main() -> None:
    if not CLIENT_FILE.exists():
        sys.exit(f"Missing {CLIENT_FILE}. Download the OAuth client JSON from Google Cloud and save it there.")

    flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_FILE), SCOPES)
    creds = flow.run_local_server(port=0, open_browser=True, timeout_seconds=600)

    TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
    print(f"Gmail sending authorized. Token saved to {TOKEN_FILE}")


if __name__ == "__main__":
    main()
