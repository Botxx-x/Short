"""
Uploads the finished video to YouTube via the Data API v3, authenticating
with a long-lived refresh token (no browser interaction at run time —
that one-time step happens in scripts/youtube_authorize.py).

Two separate Google approval gates affect this, and they are NOT the same
thing — see README "YouTube setup" section before relying on this:
  1. OAuth consent screen Testing -> Production (fixes refresh tokens
     expiring every 7 days).
  2. YouTube's own API compliance audit for the *project* (fixes uploaded
     videos being forced to Private regardless of what privacyStatus you
     request — this applies to all unverified API projects created after
     28 July 2020, per Google's own docs). Submit the Audit and Quota
     Extension form early; it can take weeks to clear. Until it does,
     uploads will still succeed, they'll just land as Private.
"""
from pathlib import Path
from typing import List

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

from . import config

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def _get_service():
    missing = [name for name, val in [
        ("YT_CLIENT_ID", config.YT_CLIENT_ID),
        ("YT_CLIENT_SECRET", config.YT_CLIENT_SECRET),
        ("YT_REFRESH_TOKEN", config.YT_REFRESH_TOKEN),
    ] if not val]
    if missing:
        raise RuntimeError(f"Missing YouTube credentials: {', '.join(missing)}")

    creds = Credentials(
        token=None,
        refresh_token=config.YT_REFRESH_TOKEN,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=config.YT_CLIENT_ID,
        client_secret=config.YT_CLIENT_SECRET,
        scopes=SCOPES,
    )
    return build("youtube", "v3", credentials=creds)


def upload_short(
    video_path: Path,
    title: str,
    description: str,
    tags: List[str],
) -> str:
    """Uploads video_path as a Short. Returns the new video's ID."""
    youtube = _get_service()

    # "#Shorts" in the title/description is the strongest programmatic
    # signal YouTube uses to route a vertical, <60s upload onto the
    # Shorts shelf — there's no separate "shorts" endpoint.
    if "#shorts" not in title.lower() and "#shorts" not in description.lower():
        description = f"{description}\n\n#Shorts"

    body = {
        "snippet": {
            "title": title[:100],
            "description": description[:5000],
            "tags": tags,
            "categoryId": config.YT_CATEGORY_ID,
        },
        "status": {
            "privacyStatus": config.YT_PRIVACY_STATUS,
            "selfDeclaredMadeForKids": False,
            # This channel's content is written from scratch by an LLM and
            # narrated by TTS, not a realistic depiction of real people/events,
            # so it does not meet YouTube's bar for "altered or synthetic"
            # disclosure (that's for realistic fakery, not AI-assisted
            # production) — see support.google.com/youtube/answer/15447836.
            # Flip this to True if your content changes to depict real
            # people, places, or events in a realistic way.
            "containsSyntheticMedia": False,
        },
    }

    media = MediaFileUpload(str(video_path), chunksize=-1, resumable=True, mimetype="video/mp4")
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    try:
        while response is None:
            status, response = request.next_chunk()
    except HttpError as e:
        raise RuntimeError(f"YouTube upload failed: {e}") from e

    return response["id"]


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python -m src.youtube_upload <path-to-mp4>")
        raise SystemExit(1)
    video_id = upload_short(
        Path(sys.argv[1]),
        title="Test upload — please ignore",
        description="Manual test upload from the pipeline.",
        tags=["test"],
    )
    print(f"Uploaded: https://youtube.com/watch?v={video_id}")
