# Quick Curious — automated Shorts pipeline

Generates a script (Gemini), voices it (edge-tts), captions it, grabs background
footage (Pexels), renders a vertical video (FFmpeg), and uploads it to YouTube —
on a schedule, via GitHub Actions, for free. Every step runs unattended once
it's set up; nothing needs your computer to stay on.

```
script_gen.py → voice.py → captions.py → visuals.py → render.py → youtube_upload.py
   (Gemini)      (edge-tts)    (ASS file)    (Pexels)     (FFmpeg)    (YouTube API)
```

## Before you start

You'll create four free accounts/credentials. All of it is free at this
project's volume (8 videos/day):

| Service | What it's for | Free tier |
|---|---|---|
| [Google AI Studio](https://aistudio.google.com) | Gemini API key (scripts) | Generous, no card needed |
| [Pexels](https://www.pexels.com/api/) | Background footage | 200 req/hour, 20k/month |
| [Google Cloud Console](https://console.cloud.google.com) | YouTube upload access | 100 uploads/day by default |
| GitHub | Hosts + runs the schedule | Free for public repos |

## Setup

### 1. Gemini API key
Go to [aistudio.google.com](https://aistudio.google.com) → **Get API key** →
**Create API key in new project**. Copy it.

### 2. Pexels API key
Sign in at [pexels.com/api](https://www.pexels.com/api/) → request a key.
It's issued instantly.

### 3. YouTube API access (the fiddly part — read this fully)
1. In [Google Cloud Console](https://console.cloud.google.com), create a project.
2. **APIs & Services → Library** → enable **YouTube Data API v3**.
3. **APIs & Services → OAuth consent screen**: User type **External**. Fill in
   the required fields (app name, your email). Add scope
   `https://www.googleapis.com/auth/youtube.upload`. Add your own Google
   account as a test user.
4. **APIs & Services → Credentials → Create Credentials → OAuth client ID** →
   type **Desktop app**. Copy the **Client ID** and **Client Secret**.
5. On your own computer (not GitHub Actions — this step needs a real browser),
   clone this repo, copy `.env.example` to `.env`, fill in `YT_CLIENT_ID` and
   `YT_CLIENT_SECRET`, then:
   ```
   pip install -r requirements.txt
   python scripts/youtube_authorize.py
   ```
   Approve access in the browser window that opens (click through the
   "unverified app" warning — expected for a personal project). It prints a
   **refresh token** — save it, you'll need it in step 7.

6. **Stop the refresh token from expiring weekly.** Go back to **OAuth consent
   screen** and click **Publish App** to move it from "Testing" to
   "In production". Testing-mode tokens expire after 7 days; production
   tokens don't expire. This is one of the two things that trips people up —
   see Troubleshooting if you skip it.

7. **The other thing that trips people up:** brand-new API projects have their
   uploaded videos forced to **Private** by YouTube, no matter what privacy
   status you request, until the project passes YouTube's own compliance
   audit. This is documented behavior, not a bug in this code. Submit the
   [Audit and Quota Extension form](https://support.google.com/youtube/contact/yt_api_form)
   as soon as you finish this setup — reviews can take a few weeks. Until
   it's approved, the pipeline will still run and upload successfully, the
   videos will just sit as Private, and you can manually flip individual ones
   to Public from YouTube Studio in the meantime if you want them live sooner.

### 4. Push to GitHub and add secrets
Push this repo to a new GitHub repository, then **Settings → Secrets and
variables → Actions → New repository secret**, and add all five:
`GEMINI_API_KEY`, `PEXELS_API_KEY`, `YT_CLIENT_ID`, `YT_CLIENT_SECRET`,
`YT_REFRESH_TOKEN`.

That's it — `.github/workflows/publish.yml` runs every 3 hours automatically.
You can also trigger it manually from the repo's **Actions** tab
(**Publish Short → Run workflow**) to test it without waiting for the clock.

## Testing locally before you trust the schedule

Each stage runs standalone so you can debug without burning API calls on the
whole pipeline:

```bash
python -m src.script_gen     # prints a generated script as JSON
python -m src.voice          # synthesizes test_audio.mp3 + prints word timings
python -m src.render         # self-contained smoke test, no API keys needed
python -m src.run            # the full pipeline, end to end
```

## Customizing

Nearly everything tunable lives in `src/config.py`:
- `CONTENT_ANGLES` — the topic pool. Add/remove angles to reshape the niche.
- `TTS_VOICE` — run `edge-tts --list-voices` for the full list.
- `CAPTION_WORDS_PER_CHUNK`, `CAPTION_FONT_SIZE` — caption style.
- `YT_PRIVACY_STATUS` — set to `"private"` while you're still testing quality.

The channel's voice/format rules live in `SYSTEM_INSTRUCTION` at the top of
`src/script_gen.py` — that consistent identity is what keeps this from
reading as mass-produced filler under YouTube's inauthentic-content policy,
so it's worth tuning to sound like you, not deleting.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Uploads land as Private | Unaudited API project (see step 7 above) | Submit the audit form; wait |
| `invalid_grant` / token errors after ~7 days | OAuth consent screen still in Testing | Publish the app (step 6) |
| "Processing failed" in Studio | Bad codec | Shouldn't happen — `render.py` always outputs H.264+AAC, but confirm with `ffprobe` if you modified it |
| `quotaExceeded` | Hit the daily API quota | Resets at midnight Pacific; check usage in Cloud Console |
| No background clips found | Pexels query too obscure | The script generator writes `visual_keywords` — nudge the prompt in `script_gen.py` toward more literal, concrete terms |

## A note on scale

This is deliberately one channel, one consistent format. If you're tempted to
copy this into five channels blasting every trending topic at once — don't;
that pattern is exactly what YouTube's inauthentic-content detection targets,
and it's also just not that fun to run. One channel with a real identity,
tuned over time, is both the safer and the more interesting version of this
project.
