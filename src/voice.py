"""
Text-to-speech via edge-tts, with word-level timestamps for captions.

Note on boundary type: edge_tts.Communicate defaults to SentenceBoundary,
NOT WordBoundary. We pass boundary="WordBoundary" explicitly or caption
timing will be wrong/missing (verified against edge-tts 7.2.8 source).
"""
import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import List

import edge_tts

from . import config

TICKS_PER_SECOND = 10_000_000  # edge-tts reports offset/duration in 100ns ticks


@dataclass
class WordTiming:
    text: str
    start: float   # seconds
    duration: float  # seconds


async def _synthesize(text: str, audio_path: Path) -> List[WordTiming]:
    communicate = edge_tts.Communicate(
        text,
        config.TTS_VOICE,
        rate=config.TTS_RATE,
        boundary="WordBoundary",
    )

    word_timings: List[WordTiming] = []
    with open(audio_path, "wb") as f:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                word_timings.append(
                    WordTiming(
                        text=chunk["text"],
                        start=chunk["offset"] / TICKS_PER_SECOND,
                        duration=chunk["duration"] / TICKS_PER_SECOND,
                    )
                )

    if not word_timings:
        raise RuntimeError(
            "edge-tts returned no WordBoundary events — check the voice name "
            f"'{config.TTS_VOICE}' is still valid (edge-tts --list-voices)."
        )
    return word_timings


def synthesize(text: str, audio_path: Path) -> List[WordTiming]:
    """Synchronous wrapper. Writes an mp3 to audio_path, returns word timings."""
    return asyncio.run(_synthesize(text, audio_path))


if __name__ == "__main__":
    # Quick manual test: python -m src.voice
    timings = synthesize(
        "This is a short test of the voice pipeline.", Path("test_audio.mp3")
    )
    for w in timings[:5]:
        print(f"{w.start:.2f}s  (+{w.duration:.2f}s)  {w.text}")
    print(f"...{len(timings)} words total, ends at "
          f"{timings[-1].start + timings[-1].duration:.2f}s")
