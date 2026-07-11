"""
Assembles the final vertical video: loops/crops background clips to cover
the voiceover length, burns in the ASS captions, muxes the audio.
Outputs H.264 + AAC in an MP4 container, which is what YouTube's ingest
pipeline expects (mismatched codecs are the most common cause of an
upload silently landing in a "Processing failed" state).
"""
import json
import math
import subprocess
from pathlib import Path
from typing import List

from . import config


def _run(cmd: List[str]) -> None:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"Command failed: {' '.join(cmd)}\n--- stderr ---\n{result.stderr[-3000:]}"
        )


def _ffprobe_duration(path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "json", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(json.loads(result.stdout)["format"]["duration"])


def _normalize_clip(src: Path, dst: Path) -> None:
    """Scale+crop to fill the vertical frame, strip audio, standardize
    codec/fps so clips concatenate cleanly regardless of source size."""
    vf = (
        f"scale={config.VIDEO_WIDTH}:{config.VIDEO_HEIGHT}:force_original_aspect_ratio=increase,"
        f"crop={config.VIDEO_WIDTH}:{config.VIDEO_HEIGHT},"
        f"fps={config.VIDEO_FPS},setsar=1"
    )
    _run(["ffmpeg", "-y", "-i", str(src), "-vf", vf, "-an",
          "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", str(dst)])


def _build_looped_background(clips: List[Path], min_duration: float, work_dir: Path) -> Path:
    normalized = []
    for i, clip in enumerate(clips):
        norm = work_dir / f"norm_{i:02d}.mp4"
        _normalize_clip(clip, norm)
        normalized.append(norm)

    clip_durations = [_ffprobe_duration(c) for c in normalized]
    total = sum(clip_durations) or 1.0
    reps = max(1, math.ceil((min_duration + 1.5) / total))

    list_path = work_dir / "concat_list.txt"
    with open(list_path, "w") as f:
        for _ in range(reps):
            for c in normalized:
                f.write(f"file '{c.resolve().as_posix()}'\n")

    looped_path = work_dir / "background_looped.mp4"
    _run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_path),
          "-c", "copy", str(looped_path)])
    return looped_path


def render_video(audio_path: Path, ass_path: Path, background_clips: List[Path],
                  output_path: Path, work_dir: Path) -> Path:
    work_dir.mkdir(parents=True, exist_ok=True)
    audio_duration = _ffprobe_duration(audio_path)
    background = _build_looped_background(background_clips, audio_duration, work_dir)

    # Escape the subtitles path for ffmpeg's filter-argument parser (colons
    # and backslashes are special inside a filtergraph string).
    ass_filter_path = str(ass_path.resolve()).replace("\\", "/").replace(":", "\\:")

    _run([
        "ffmpeg", "-y",
        "-i", str(background),
        "-i", str(audio_path),
        "-vf", f"ass={ass_filter_path}",
        "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        str(output_path),
    ])
    return output_path


if __name__ == "__main__":
    # Self-contained smoke test using synthetic clips + tone audio —
    # no network required. Run: python -m src.render
    from .captions import build_ass
    from .voice import WordTiming

    tmp = Path("test_render")
    tmp.mkdir(exist_ok=True)

    # Fake 6s audio tone standing in for a real TTS voiceover
    fake_audio = tmp / "fake_audio.mp3"
    _run(["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=6",
          "-c:a", "libmp3lame", str(fake_audio)])

    # Two fake colored background clips standing in for Pexels downloads
    clip_a = tmp / "clip_a.mp4"
    clip_b = tmp / "clip_b.mp4"
    _run(["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=blue:s=640x360:d=3",
          "-c:v", "libx264", str(clip_a)])
    _run(["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=green:s=640x360:d=3",
          "-c:v", "libx264", str(clip_b)])

    demo_words = [WordTiming("Testing", 0.2, 0.4), WordTiming("the", 0.6, 0.15),
                  WordTiming("render", 0.8, 0.5), WordTiming("pipeline", 1.4, 0.6)]
    ass_path = build_ass(demo_words, tmp / "captions.ass")

    out = render_video(fake_audio, ass_path, [clip_a, clip_b], tmp / "final.mp4", tmp / "work")
    print("Rendered:", out, "-", _ffprobe_duration(out), "seconds")
