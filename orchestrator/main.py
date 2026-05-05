import os
import time
import uuid
import requests
from pathlib import Path
from fastapi import FastAPI, Request
from openai import OpenAI
import subprocess

app = FastAPI()
client = OpenAI()

JINGLES_DIR = Path("/jingles")
QUEUED_DIR = JINGLES_DIR / "queued"
TTS_URL = os.environ["TTS_URL"]
LLM_SYSTEM_PROMPT = os.environ["LLM_SYSTEM_PROMPT"]

last_spoken_at = 0
MIN_INTERVAL_SECONDS = 60


@app.post("/event")
async def event(req: Request):
    global last_spoken_at

    data = await req.json()

    if data.get("event") != "track_started":
        return {"ok": True, "ignored": True}

    now = time.time()

    if now - last_spoken_at < MIN_INTERVAL_SECONDS:
        return {"ok": True, "skipped": "cooldown"}

    artist = data.get("artist") or "Unknown artist"
    title = data.get("title") or "Unknown title"
    filename = data.get("filename") or ""

    prompt = (
        f"{LLM_SYSTEM_PROMPT}\n\n"
        f"artist: {artist}\n"
        f"title: {title}\n"
        f"file: {filename}\n"
    )

    response = client.responses.create(
        model="gpt-5.5",
        input=prompt,
    )

    text = response.output_text.strip()
    if not text:
        return {"ok": False, "error": "empty llm response"}

    tts_response = requests.post(
        TTS_URL,
        json={
            "text": text,
            "language_id": "ru",
            "exaggeration": 0.6,
            "cfg_weight": 0.6,
            "temperature": 0.6,
            "voice": "valera",
        },
        timeout=180,
    )
    tts_response.raise_for_status()

    QUEUED_DIR.mkdir(parents=True, exist_ok=True)

    name = f"valera-{int(now)}-{uuid.uuid4().hex}.wav"
    final_path = QUEUED_DIR / name

    raw_tmp_path = QUEUED_DIR / f"{name}.raw.tmp"
    fixed_tmp_path = QUEUED_DIR / f"{name}.tmp"

    with open(raw_tmp_path, "wb") as f:
        f.write(tts_response.content)
        f.flush()
        os.fsync(f.fileno())

    result = subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel", "error",
            "-i", str(raw_tmp_path),
            "-ar", "44100",
            "-ac", "2",
            "-c:a", "pcm_s16le",
            "-f", "wav",
            str(fixed_tmp_path),
        ],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        return {"ok": False, "error": "ffmpeg failed", "stderr": result.stderr}

    raw_tmp_path.unlink(missing_ok=True)

    os.chmod(fixed_tmp_path, 0o644)

    os.replace(fixed_tmp_path, final_path)

    last_spoken_at = now

    return {
        "ok": True,
        "text": text,
        "wav": str(final_path),
    }
