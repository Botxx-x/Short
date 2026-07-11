"""
Run this ONCE, locally, on your own machine (not in GitHub Actions — it
needs a real browser). It opens a Google consent screen, you approve
access to your own YouTube channel, and it prints a refresh token.

That refresh token is what the automated pipeline uses forever after —
paste it into GitHub Actions as the YT_REFRESH_TOKEN secret and you never
have to run this again, PROVIDED your OAuth consent screen is set to
"In production" in Google Cloud Console (Testing mode tokens expire after
7 days — see README).

Usage:
    python scripts/youtube_authorize.py
Requires YT_CLIENT_ID and YT_CLIENT_SECRET to already be set (in a local
.env file, or exported in your shell).
"""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from google_auth_oauthlib.flow import InstalledAppFlow

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def main() -> None:
    client_id = os.environ.get("YT_CLIENT_ID")
    client_secret = os.environ.get("YT_CLIENT_SECRET")

    if not client_id or not client_secret:
        print("Missing YT_CLIENT_ID / YT_CLIENT_SECRET.")
        print("Set them in a .env file next to this project (see .env.example) "
              "or export them in your shell, then re-run this script.")
        sys.exit(1)

    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }

    print("Opening your browser to sign in with the Google account that")
    print("owns the YouTube channel you want to automate...")
    print()
    print("If you see an 'unverified app' warning, that's expected for a")
    print("personal project — click 'Advanced' then 'Go to (your app name)'.")
    print()

    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
    creds = flow.run_local_server(port=0)

    print()
    print("=" * 70)
    print("SUCCESS. Save this refresh token as the YT_REFRESH_TOKEN secret")
    print("in your GitHub repo (Settings -> Secrets and variables -> Actions):")
    print()
    print(creds.refresh_token)
    print("=" * 70)
    print()
    print("Reminder: this token stays valid indefinitely ONLY if your OAuth")
    print("consent screen is set to 'In production' (Google Cloud Console ->")
    print("APIs & Services -> OAuth consent screen -> Publish App). In")
    print("'Testing' mode it expires after 7 days and you'd need to re-run")
    print("this script weekly.")


if __name__ == "__main__":
    main()
