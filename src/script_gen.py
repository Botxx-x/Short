"""
Generates one video's worth of content: a hook, a narration script, and
YouTube metadata (title/description/tags), using the Gemini API with
structured JSON output.
"""
import json
import random
from typing import List

from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from . import config


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
    """Calls Gemini once and returns a fully-formed, structured video script."""
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

    response = client.models.generate_content(
        model=config.GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            response_mime_type="application/json",
            response_schema=VideoScript,
            temperature=1.1,
        ),
    )

    script: VideoScript = response.parsed
    _save_topic(script.topic, script.title)
    return script


if __name__ == "__main__":
    # Quick manual test: python -m src.script_gen
    result = generate_script()
    print(json.dumps(result.model_dump(), indent=2))
