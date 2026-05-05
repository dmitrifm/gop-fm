import os
import shutil
import tempfile
from contextlib import asynccontextmanager
from functools import partial
from pathlib import Path
from typing import Annotated

import anyio
import torch
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import ValidationError
from starlette.background import BackgroundTask

from app.config import Settings, get_settings
from app.schemas import (
    HealthResponse,
    LanguageItem,
    LanguagesResponse,
    SUPPORTED_LANGUAGES,
    TTSRequest,
)
from app.tts_engine import TTSEngine, resolve_voice_prompt_path

settings = get_settings()
engine = TTSEngine(settings)


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.tts_preload:
        await anyio.to_thread.run_sync(engine.load)
    yield


app = FastAPI(
    title="Chatterbox Multilingual TTS Service",
    version="0.1.0",
    description="Simple API that converts text into WAV audio using Chatterbox Multilingual.",
    lifespan=lifespan,
)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    cuda_device_name = torch.cuda.get_device_name(0) if torch.cuda.is_available() else None
    return HealthResponse(
        status="ok",
        model_loaded=engine.loaded,
        device=engine.device,
        cuda_available=torch.cuda.is_available(),
        cuda_device_name=cuda_device_name,
    )


@app.get("/languages", response_model=LanguagesResponse)
def languages() -> LanguagesResponse:
    items = [LanguageItem(code=code, name=name) for code, name in SUPPORTED_LANGUAGES.items()]
    return LanguagesResponse(languages=items, count=len(items))


@app.post("/tts")
async def synthesize(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> FileResponse:
    payload = await _parse_tts_request(request=request, settings=settings)
    if len(payload.text) > settings.tts_max_text_length:
        raise HTTPException(
            status_code=413,
            detail=f"text is too long; max length is {settings.tts_max_text_length} characters",
        )

    with tempfile.TemporaryDirectory(prefix="tts-request-") as request_dir:
        audio_prompt_path = await _resolve_audio_prompt_path(
            payload=payload,
            settings=settings,
        )
        generate = partial(
            engine.generate_to_wav_file,
            text=payload.text,
            language_id=payload.language_id,
            output_dir=request_dir,
            audio_prompt_path=audio_prompt_path,
            generation_options={
                "exaggeration": payload.exaggeration,
                "cfg_weight": payload.cfg_weight,
                "temperature": payload.temperature,
                "seed": payload.seed,
            },
        )
        output_path = await anyio.to_thread.run_sync(generate)
        durable_output = _move_to_durable_temp(output_path)

    return FileResponse(
        durable_output,
        media_type="audio/wav",
        filename="speech.wav",
        background=BackgroundTask(_unlink_file, durable_output),
    )


async def _parse_tts_request(
    *,
    request: Request,
    settings: Settings,
) -> TTSRequest:
    content_type = request.headers.get("content-type", "")
    if content_type.startswith("application/json"):
        body = await request.json()
        if not isinstance(body, dict):
            raise HTTPException(status_code=422, detail="JSON body must be an object")
        body.setdefault("language_id", settings.tts_default_language)
    else:
        form = await request.form()
        body = {
            key: value
            for key, value in form.items()
            if not hasattr(value, "filename")
        }
        if "language_id" not in body:
            body["language_id"] = settings.tts_default_language

    body.setdefault("exaggeration", settings.tts_default_exaggeration)
    body.setdefault("cfg_weight", settings.tts_default_cfg_weight)
    body.setdefault("temperature", settings.tts_default_temperature)

    try:
        return TTSRequest.model_validate(body)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc


async def _resolve_audio_prompt_path(
    *,
    payload: TTSRequest,
    settings: Settings,
) -> str | None:
    if payload.voice is None:
        return None

    try:
        return resolve_voice_prompt_path(settings.tts_voices_dir, payload.voice)
    except FileNotFoundError as exc:
        available_voices = _list_available_voices(settings.tts_voices_dir)
        detail = str(exc)
        if available_voices:
            detail = f"{detail}. Available voices: {', '.join(available_voices)}"
        raise HTTPException(status_code=400, detail=detail) from exc


def _list_available_voices(voices_dir: str) -> list[str]:
    base_dir = Path(voices_dir).expanduser()
    if not base_dir.is_absolute():
        base_dir = Path.cwd() / base_dir
    if not base_dir.exists():
        return []
    return sorted(path.stem for path in base_dir.glob("*.wav") if path.is_file())


def _move_to_durable_temp(path: str) -> str:
    fd, durable_path = tempfile.mkstemp(prefix="tts-response-", suffix=".wav")
    os.close(fd)
    Path(durable_path).unlink(missing_ok=True)
    shutil.move(path, durable_path)
    return durable_path


def _unlink_file(path: str) -> None:
    Path(path).unlink(missing_ok=True)
