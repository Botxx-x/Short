"""
End-to-end pipeline: generate a script, voice it, caption it, find
background footage, render the final vertical video, upload to YouTube.

Run locally with:  python -m src.run
Run in CI:          see .github/workflows/publish.yml
"""
import shutil
import sys
import time
from pathlib import Path

from . import captions, config, render, script_gen, visuals, voice, youtube_upload


def main() -> None:
    run_id = time.strftime("%Y%m%d-%H%M%S")
    work_dir = config.WORK_DIR / run_id
    work_dir.mkdir(parents=True, exist_ok=True)

    try:
        print(f"[1/5] Generating script (run {run_id})...")
        script = script_gen.generate_script()
        print(f"      topic: {script.topic}")
        print(f"      title: {script.title}")

        print("[2/5] Synthesizing voice...")
        audio_path = work_dir / "voice.mp3"
        word_timings = voice.synthesize(script.script, audio_path)
        total_duration = word_timings[-1].start + word_timings[-1].duration
        print(f"      {len(word_timings)} words, {total_duration:.1f}s")

        print("[3/5] Building captions + fetching background footage...")
        ass_path = captions.build_ass(word_timings, work_dir / "captions.ass")
        bg_clips = visuals.fetch_background_clips(script.visual_keywords, work_dir / "bg")
        print(f"      {len(bg_clips)} background clips")

        print("[4/5] Rendering final video...")
        final_path = work_dir / "final.mp4"
        render.render_video(audio_path, ass_path, bg_clips, final_path, work_dir / "render_tmp")
        size_mb = final_path.stat().st_size / (1024 * 1024)
        print(f"      {final_path} ({size_mb:.1f} MB)")

        print("[5/5] Uploading to YouTube...")
        video_id = youtube_upload.upload_short(
            final_path, script.title, script.description, script.tags
        )
        print(f"      done: https://youtube.com/watch?v={video_id}")

    except Exception as exc:
        print(f"PIPELINE FAILED: {exc}", file=sys.stderr)
        raise
    finally:
        # Keep work_dir around on failure for debugging; clean up on success
        # so repeated CI runs don't pile up disk usage.
        if (work_dir / "final.mp4").exists():
            shutil.rmtree(work_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
