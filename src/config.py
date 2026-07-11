"""
Central configuration for the Shorts pipeline.
Everything you're likely to want to tune lives here instead of being
scattered across modules.
"""
import os
from pathlib import Path

# --- Secrets / API keys (set as env vars locally via .env, or as
# GitHub Actions repo secrets in production — see README) -------------------
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY", "")
YT_CLIENT_ID = os.environ.get("YT_CLIENT_ID", "")
YT_CLIENT_SECRET = os.environ.get("YT_CLIENT_SECRET", "")
YT_REFRESH_TOKEN = os.environ.get("YT_REFRESH_TOKEN", "")

# --- Paths -------------------------------------------------------------
ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
WORK_DIR = ROOT_DIR / "work"          # scratch space, wiped each run
TOPICS_LOG = DATA_DIR / "used_topics.json"   # history, committed back to git

# --- Content / script generation ----------------------------------------
# "gemini-2.5-flash" is the current free-tier workhorse model as of mid-2026.
# Google's free-tier lineup shifts fairly often — if this starts failing,
# check https://ai.google.dev/gemini-api/docs/pricing for the current
# free-eligible model names and swap the constant below.
GEMINI_MODEL_CANDIDATES = [
    "gemini-flash-latest",   # Google keeps this pointed at their current model
    "gemini-3.5-flash",      # pinned fallback if the alias ever misbehaves
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
