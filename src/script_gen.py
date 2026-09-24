"""
Generates one video's worth of content: a hook, a narration script, and
YouTube metadata (title/description/tags), using the Gemini API with
structured JSON output.
"""
import json
import random
import time
from difflib import SequenceMatcher
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

# How similar (0-1, via difflib's SequenceMatcher ratio) a new topic/title
# can be to a past one before it's treated as a repeat and regenerated.
# This is a cheap, offline text-similarity check — not semantic/embedding
# based — so it catches near-identical wording but won't catch the same
# fact described in totally different words. Good enough as a hard floor
# on top of the "don't repeat these" prompt instruction, which was the
# only thing doing this job before and could be ignored by the model.
DUPLICATE_SIMILARITY_THRESHOLD = 0.6
MAX_DUPLICATE_RETRIES = 3


class VideoScript(BaseModel):
    topic: str = Field(description="Short internal label for this video's subject")
    hook: str = Field(description="The first spoken line — must grab attention instantly")
    script: str = Field(description="Full narration text, written to be read aloud")
    title: str = Field(description="YouTube title, under 90 characters, includes the hook")
    description: str = Field(description="YouTube description, 2-3 sentences plus #Shorts")
    tags: List[str] = Field(description="8-12 relevant YouTube tags")
    hashtags: List[str] = Field(
        description="3-5 hashtags for the description, each starting with '#', no "
        "spaces inside a tag (e.g. '#history', '#ScienceFacts'). Mix one or two broad "
        "niche tags (e.g. '#facts', '#didyouknow') with two or three specific to this "
        "video's topic. These are shown to viewers, so keep them relevant and readable."
    )
    visual_keywords: List[str] = Field(
        description="3-5 concrete, literal search terms for stock background footage "
        "(e.g. 'ocean waves aerial', 'city street night'). Avoid abstract words."
    )


SYSTEM_INSTRUCTION = """You write short, punchy narration scripts for a YouTube Shorts channel
called "Funfactz" — a bite-sized knowledge channel that covers surprising facts,
psychology, science, mysteries, and history.

Voice and format rules (apply to every script, this is the channel's consistent identity):
- Open with a hook line in the first sentence that makes someone stop scrolling.
  No throat-clearing, no "did you know" cliches, no greetings.
- Strongly prefer this hook shape, since it's the channel's best-performing pattern:
  state a rule, limit, or assumption as fact, in a way that implies a strange or
  counterintuitive reason behind it — then resolve that reason as the payoff.
  Examples of the shape (do not reuse these topics): "This animal can never leave its
  country again — here's why." / "This ship sailed for 38 years with no one on board."
  / "You'd think the biggest animal ever could swallow you. It can't." The hook should
  make someone need the explanation, not just find the fact mildly interesting.
- Conversational, punchy, short sentences. Write for the EAR, not the eye.
- End on a satisfying payoff or a slight twist, THEN a one-line follow prompt tied to
  that payoff (e.g. "Follow for more stuff that sounds fake but isn't"). Keep it under
  1.5 seconds spoken, never a generic "like and subscribe," and vary the phrasing between
  videos so it doesn't sound copy-pasted.
- Every fact must be something you're confident is true and verifiable. Never invent
  statistics, studies, or quotes. If you're not sure a detail is accurate, leave it out
  rather than guess.
- Do not use emoji or asterisks in the script text (it's read aloud by TTS).
- Do not write anything that reads as a template — vary sentence rhythm and structure
  between videos, not just the topic."""


def _load_recent_topics(limit: int = None) -> List[dict]:
    """Returns the most recent {topic, title} entries, most-recent-last.
    Both fields are included (not just topic) so the model has enough
    context to spot a reworded repeat, not just an exact-label match."""
    if limit is None:
        limit = config.TOPIC_HISTORY_LIMIT
    if not config.TOPICS_LOG.exists():
        return []
    try:
        history = json.loads(config.TOPICS_LOG.read_text())
    except (json.JSONDecodeError, OSError):
        return []
    return history[-limit:]


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


def _most_similar_past_entry(topic: str, title: str, history: List[dict]):
    """Returns (entry, ratio) for the closest past topic/title match, or
    (None, 0.0) if history is empty. Checks both fields since a repeat
    might show up as a near-identical topic label, a near-identical
    title, or both."""
    best_entry, best_ratio = None, 0.0
    topic_l, title_l = topic.lower(), title.lower()
    for entry in history:
        t_ratio = SequenceMatcher(None, topic_l, entry.get("topic", "").lower()).ratio()
        h_ratio = SequenceMatcher(None, title_l, entry.get("title", "").lower()).ratio()
        ratio = max(t_ratio, h_ratio)
        if ratio > best_ratio:
            best_entry, best_ratio = entry, ratio
    return best_entry, best_ratio


def _build_prompt(angle: str, avoid: List[dict]) -> str:
    if avoid:
        avoid_text = "\n".join(f"- {e['topic']}: {e['title']}" for e in avoid)
    else:
        avoid_text = "(none yet)"

    return f"""Write one new video script.

Angle for this video: {angle}

Target length: {config.TARGET_SCRIPT_WORDS} words of spoken narration.

Do NOT repeat any of these already-used topics, INCLUDING reworded or
differently-framed versions of the same underlying fact or story (pick
something genuinely different, not just a different sentence for the
same idea):
{avoid_text}

Return the result matching the required JSON schema."""


def _generate_once(prompt: str) -> VideoScript:
    """Calls Gemini with the given prompt and returns a parsed VideoScript.
    Retries transient failures (server overload, rate limits) with backoff
    on the same model before giving up on it and trying the next candidate
    in GEMINI_MODEL_CANDIDATES."""
    if not config.GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is not set")

    client = genai.Client(api_key=config.GEMINI_API_KEY)

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

    return response.parsed


def generate_script() -> VideoScript:
    """Generates a video script, rejecting and regenerating (up to
    MAX_DUPLICATE_RETRIES times) if the topic/title is too similar to a
    recently-used one. Falls back to using the last candidate anyway if
    it's still a near-duplicate after all retries, so a stubborn topic
    can't stall the whole run."""
    angle = random.choice(config.CONTENT_ANGLES)
    history = _load_recent_topics()

    # Grows with each rejected candidate this run, so a retry doesn't
    # just regenerate the same near-duplicate again.
    avoid = list(history)
    script = None

    for dup_attempt in range(MAX_DUPLICATE_RETRIES + 1):
        prompt = _build_prompt(angle, avoid)
        script = _generate_once(prompt)

        match, ratio = _most_similar_past_entry(script.topic, script.title, history)
        if ratio < DUPLICATE_SIMILARITY_THRESHOLD:
            break

        print(f"      (topic '{script.topic}' looks {ratio:.0%} similar to past "
              f"video '{match['title']}' — regenerating, attempt "
              f"{dup_attempt + 1}/{MAX_DUPLICATE_RETRIES})")
        avoid.append({"topic": script.topic, "title": script.title})
    else:
        print("      (still looked like a duplicate after max retries — "
              "using it anyway rather than stalling the run; consider "
              "raising MAX_DUPLICATE_RETRIES or widening CONTENT_ANGLES "
              "if this keeps happening)")

    _save_topic(script.topic, script.title)
    return script


if __name__ == "__main__":
    # Quick manual test: python -m src.script_gen
    result = generate_script()
    print(json.dumps(result.model_dump(), indent=2))
