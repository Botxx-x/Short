"""
Generates one video's worth of content: a hook, a narration script, and
YouTube metadata (title/description/tags), using the Gemini API with
structured JSON output.
"""
import json
import random
import time
from typing import List

from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from . import config

# Errors worth waiting out and retrying on the SAME model: 503 (server
# overloaded — what actually happened on 13 July), 429 (rate/quota
# limited), 500 (generic transient server error). 404 (model doesn't
# exist for this key) is NOT in this set — no amount of waiting fixes a
# wrong model name, so that one skips straight to the next candidate.
RETRYABLE_CODES = {429, 500, 503}
MAX_RETRIES_PER_MODEL = 3
RETRY_BACKOFF_SECONDS = [20, 40, 80]


class VideoScript(BaseModel):
    topic: str = Field(description="Short internal label for this video's subject")
    hook: str = Field(description="The first spoken line — must grab attention instantly")
    script: str = Field(description="Full narration text, written to be read aloud")
    title: str = Field(description="YouTube title, under 90 characters, includes the hook")
    description: str = Field(description="YouTube description, 2-3 sentences plus #Shorts")
    tags: List[str] = Field(description="8-12 relevant YouTube tags")
    visual_keywords: List[str] = Field(
        description="3-5 concrete, literal search terms for stock background footage "
        "(e.g. 'ocean waves aerial', 'city street night'). Avoid abstract words."
    )


SYSTEM_INSTRUCTION = """You write short, punchy narration scripts for a YouTube Shorts channel
called "Quick Curious" — a bite-sized knowledge channel that covers surprising facts,
psychology, science, mysteries, and history.

Voice and format rules (apply to every script, this is the channel's consistent identity):
- Open with a hook line in the first sentence that makes someone stop scrolling.
  No throat-clearing, no "did you know" cliches, no greetings.
- Conversational, punchy, short sentences. Write for the EAR, not the eye.
- End on a satisfying payoff or a slight twist, not a trailing-off summary.
- Every fact must be something you're confident is true and verifiable. Never invent
  statistics, studies, or quotes. If you're not sure a detail is accurate, leave it out
  rather than guess.
- Do not use emoji or asterisks in the script text (it's read aloud by TTS).
- Do not write anything that reads as a template — vary sentence rhythm and structure
  between videos, not just the topic."""


def _load_recent_topics(limit: int = 40) -> List[str]:
    if not config.TOPICS_LOG.exists():
        return []
    try:
        history = json.loads(config.TOPICS_LOG.read_text())
    except (json.JSONDecodeError, OSError):
        return []
    return [entry["topic"] for entry in history[-limit:]]


def _save_topic(topic: str, title: str) -> None:
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    history = []
    if config.TOPICS_LOG.exists():
        try:
            history = json.loads(config.TOPICS_LOG.read_text())
        except (json.JSONDecodeError, OSError):
            history = []
    history.append({"topic": topic, "title": title})
    config.TOPICS_LOG.write_text(json.dumps(history, indent=2))


def generate_script() -> VideoScript:
    """Calls Gemini and returns a fully-formed, structured video script.
    Retries transient failures (server overload, rate limits) with backoff
    on the same model before giving up on it and trying the next candidate
    in GEMINI_MODEL_CANDIDATES."""
    if not config.GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is not set")

    client = genai.Client(api_key=config.GEMINI_API_KEY)
    angle = random.choice(config.CONTENT_ANGLES)
    recent = _load_recent_topics()

    prompt = f"""Write one new video script.

Angle for this video: {angle}

Target length: {config.TARGET_SCRIPT_WORDS} words of spoken narration.

Do NOT repeat any of these already-used topics (pick something genuinely different):
{json.dumps(recent) if recent else "(none yet)"}

Return the result matching the required JSON schema."""

    gen_config = types.GenerateContentConfig(
        system_instruction=SYSTEM_INSTRUCTION,
        response_mime_type="application/json",
        response_schema=VideoScript,
        temperature=1.1,
    )

    response = None
    last_error = None

    for model_name in config.GEMINI_MODEL_CANDIDATES:
        for attempt in range(MAX_RETRIES_PER_MODEL + 1):
            try:
                response = client.models.generate_content(
                    model=model_name, contents=prompt, config=gen_config,
                )
                break  # success
            except genai.errors.APIError as e:
                code = getattr(e, "code", None)
                last_error = e

                if code == 404:
                    # This model ID doesn't exist for this key at all —
                    # no point retrying it, move on to the next candidate.
                    break

                if code in RETRYABLE_CODES and attempt < MAX_RETRIES_PER_MODEL:
                    wait = RETRY_BACKOFF_SECONDS[attempt]
                    print(f"      ({model_name} returned {code}, probably "
                          f"temporary — retrying in {wait}s, attempt "
                          f"{attempt + 2}/{MAX_RETRIES_PER_MODEL + 1})")
                    time.sleep(wait)
                    continue

                # Either not a retryable code, or retries on this model
                # are exhausted — fall through to the next candidate model.
                break

        if response is not None:
            if model_name != config.GEMINI_MODEL_CANDIDATES[0]:
                print(f"      (note: fell back to {model_name} — update "
                      f"GEMINI_MODEL_CANDIDATES in config.py so this stops happening)")
            break

    if response is None:
        raise RuntimeError(
            f"All candidate Gemini models failed after retries (tried "
            f"{config.GEMINI_MODEL_CANDIDATES}). Last error: {last_error}. "
            f"If this keeps happening across multiple runs, Google's API may "
            f"be having a wider outage — check https://status.cloud.google.com, "
            f"otherwise this run will simply be retried at the next scheduled "
            f"3-hour slot."
        ) from last_error

    script: VideoScript = response.parsed
    _save_topic(script.topic, script.title)
    return script


if __name__ == "__main__":
    # Quick manual test: python -m src.script_gen
    result = generate_script()
    print(json.dumps(result.model_dump(), indent=2))
