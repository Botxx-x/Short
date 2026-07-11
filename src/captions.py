"""
Turns word-level TTS timings into a styled .ass subtitle file that FFmpeg
burns into the video. Words are grouped into short bursts (a few words at
a time) rather than full sentences — that's the punchy caption style that
performs well on Shorts, and it's driven entirely by real speech timing
so it never drifts out of sync with the voiceover.
"""
from pathlib import Path
from typing import List

from . import config
from .voice import WordTiming


def _fmt_time(seconds: float) -> str:
    """ASS timestamps: H:MM:SS.cc (centiseconds)."""
    if seconds < 0:
        seconds = 0
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    centis = int(round((seconds - int(seconds)) * 100))
    return f"{hours}:{minutes:02d}:{secs:02d}.{centis:02d}"


def _escape(text: str) -> str:
    return text.replace("{", "(").replace("}", ")")


def _chunk_words(words: List[WordTiming], size: int) -> List[List[WordTiming]]:
    return [words[i:i + size] for i in range(0, len(words), size)]


HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font},{size},&H00FFFFFF,&H000000FF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,6,0,2,60,60,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def build_ass(word_timings: List[WordTiming], output_path: Path) -> Path:
    chunks = _chunk_words(word_timings, config.CAPTION_WORDS_PER_CHUNK)

    lines = [HEADER.format(
        width=config.VIDEO_WIDTH,
        height=config.VIDEO_HEIGHT,
        font=config.CAPTION_FONT,
        size=config.CAPTION_FONT_SIZE,
        margin_v=int(config.VIDEO_HEIGHT * 0.32),
    )]

    for chunk in chunks:
        if not chunk:
            continue
        start = chunk[0].start
        end = chunk[-1].start + chunk[-1].duration
        text = _escape(" ".join(w.text for w in chunk).upper())
        lines.append(
            f"Dialogue: 0,{_fmt_time(start)},{_fmt_time(end)},Default,,0,0,0,,{text}\n"
        )

    output_path.write_text("".join(lines), encoding="utf-8")
    return output_path


if __name__ == "__main__":
    # Quick manual test using synthetic timings
    from .voice import WordTiming as WT
    demo = [WT("This", 0.0, 0.3), WT("is", 0.3, 0.2), WT("a", 0.5, 0.15),
            WT("caption", 0.65, 0.5), WT("test.", 1.15, 0.4)]
    build_ass(demo, Path("test_captions.ass"))
    print(Path("test_captions.ass").read_text())
