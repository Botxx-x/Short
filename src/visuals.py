"""
Fetches free, royalty-free background video clips from Pexels, keyed off
the visual_keywords the script generator produced for this video.
"""
from pathlib import Path
from typing import List, Optional

import requests

from . import config

SEARCH_URL = "https://api.pexels.com/videos/search"


def _pick_file_url(video_json: dict) -> Optional[str]:
    """Prefer a mid-resolution file (fast download, still plenty sharp for a
    1080x1920 export) over the largest 4K master file Pexels offers."""
    files = [f for f in video_json.get("video_files", []) if f.get("link")]
    if not files:
        return None
    mid = [f for f in files if f.get("height") and 720 <= f["height"] <= 1440]
    pool = mid or files
    pool.sort(key=lambda f: f.get("height", 0))
    return pool[len(pool) // 2]["link"]


def _search(query: str, headers: dict, portrait_only: bool) -> list:
    params = {"query": query, "per_page": 6}
    if portrait_only:
        params["orientation"] = "portrait"
    resp = requests.get(SEARCH_URL, headers=headers, params=params, timeout=20)
    resp.raise_for_status()
    return resp.json().get("videos", [])


def fetch_background_clips(keywords: List[str], work_dir: Path) -> List[Path]:
    """Downloads one background clip per keyword (falls back to a generic
    query if a specific keyword returns nothing). Returns paths in order."""
    if not config.PEXELS_API_KEY:
        raise RuntimeError("PEXELS_API_KEY is not set")

    headers = {"Authorization": config.PEXELS_API_KEY}
    work_dir.mkdir(parents=True, exist_ok=True)
    downloaded: List[Path] = []

    queries = keywords if keywords else ["abstract motion background"]

    for i, query in enumerate(queries):
        results = _search(query, headers, portrait_only=True)
        if not results:
            results = _search(query, headers, portrait_only=False)
        if not results:
            results = _search("abstract background motion", headers, portrait_only=True)
        if not results:
            continue

        url = _pick_file_url(results[0])
        if not url:
            continue

        out_path = work_dir / f"bg_{i:02d}.mp4"
        with requests.get(url, stream=True, timeout=60) as r:
            r.raise_for_status()
            with open(out_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=1 << 16):
                    f.write(chunk)
        downloaded.append(out_path)

    if not downloaded:
        raise RuntimeError(
            "Could not fetch any background clips from Pexels — check "
            "PEXELS_API_KEY and rate limits (200 req/hour on the free tier)."
        )
    return downloaded


if __name__ == "__main__":
    # Quick manual test: python -m src.visuals
    clips = fetch_background_clips(["ocean waves aerial", "city street night"], Path("test_bg"))
    print("Downloaded:", clips)
