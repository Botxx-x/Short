"""
Central configuration for the Shorts pipeline.
Everything you're likely to want to tune lives here instead of being
scattered across modules.
"""
import os
from pathlib import Path

# --- Secrets / API keys (set as env vars locally via .env, or as
# GitHub Actions repo secrets in production — see README) -------------------
def _env(name: str) -> str:
    """Reads an env var and strips stray whitespace/newlines. A trailing
    newline is an easy mistake when pasting a value into a GitHub Actions
    secret box, and it silently breaks anything that puts the value
    straight into an HTTP header (like Pexels' Authorization header) —
    that's what caused the 'Invalid header value' crash."""
    return os.environ.get(name, "").strip()


GEMINI_API_KEY = _env("GEMINI_API_KEY")
PEXELS_API_KEY = _env("PEXELS_API_KEY")
YT_CLIENT_ID = _env("YT_CLIENT_ID")
YT_CLIENT_SECRET = _env("YT_CLIENT_SECRET")
YT_REFRESH_TOKEN = _env("YT_REFRESH_TOKEN")

# --- Paths -------------------------------------------------------------
ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
WORK_DIR = ROOT_DIR / "work"          # scratch space, wiped each run
TOPICS_LOG = DATA_DIR / "used_topics.json"   # history, committed back to git

# --- Content / script generation ----------------------------------------
# Google retires Gemini model IDs with little warning — gemini-2.5-flash,
# what this was originally set to, started returning 404 "no longer
# available to new users" for newly-created API keys (confirmed by your
# July 11 2026 run). script_gen.py tries these in order and automatically
# falls through on that specific 404, so the next retirement doesn't take
# the whole pipeline down with it:
#   1. "gemini-flash-latest" — an alias Google keeps pointed at whatever
#      its current recommended flash model is (currently Gemini 3.5
#      Flash), so this should keep working across future retirements
#      without any edits here.
#   2. "gemini-3.5-flash" — that same current model, pinned directly, as
#      a fallback in case the alias itself ever has an issue.
# If BOTH of these ever fail, check
# https://ai.google.dev/gemini-api/docs/models for the current lineup and
# add a working name to this list.
GEMINI_MODEL_CANDIDATES = [
    "gemini-flash-latest",
    "gemini-3.5-flash",
]

# Broad, algorithm-friendly pool. The script generator picks ONE angle per
# video but always writes it in the same voice/format (see PROMPT below),
# so the channel still reads as one coherent identity rather than random
# AI-generated filler — see the note on YouTube's "inauthentic content"
# policy in the README before you change this.
CONTENT_ANGLES = [
    "a little-known but verified historical fact",
    "a psychology or human-behavior fact that explains something everyday",
    "a science or space fact that sounds unbelievable but is true",
    "an unsolved mystery or strange unexplained event",
    "a surprising fact about the human body",
    "a strange-but-true law or historical rule from somewhere in the world",
    "a fact about animals that most people get wrong",
]

TARGET_SCRIPT_WORDS = "110-150"   # ≈ 45-60 seconds spoken at the rate below

# --- Voice (edge-tts) ------------------------------------------------------
TTS_VOICE = "en-US-ChristopherNeural"   # run `edge-tts --list-voices` for options
TTS_RATE = "+8%"                        # slightly faster reads better on Shorts

# --- Video -------------------------------------------------------------
VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
VIDEO_FPS = 30

# Caption styling (burned-in ASS subtitles)
CAPTION_FONT = "DejaVu Sans"     # bundled on most Linux runners incl. GitHub Actions
CAPTION_FONT_SIZE = 90
CAPTION_WORDS_PER_CHUNK = 3       # short punchy bursts, not full sentences

# --- YouTube -------------------------------------------------------------
YT_CATEGORY_ID = "27"     # "Education" — see videoCategories.list for others
YT_PRIVACY_STATUS = "public"
