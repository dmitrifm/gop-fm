# Chatterbox Multilingual TTS Service

Python microservice that accepts text and returns a generated WAV or OGG file
using Chatterbox Multilingual TTS. The service prefers CUDA automatically, so an
NVIDIA RTX 4060 will be used when PyTorch sees the GPU.

## API

- `GET /health` - service status, CUDA availability, active device.
- `GET /languages` - supported Chatterbox Multilingual language codes.
- `POST /tts` - synthesize speech and return `audio/wav` or `audio/ogg`.

`/tts` accepts either JSON or `multipart/form-data`.

Voice references are resolved from local WAV files in the project voice
directory, for example `voices/valera.wav` or `voices/sergei.wav`. To use one
of them, pass `voice=valera` or `voice=sergei` in the request.

JSON example:

```bash
curl -X POST http://localhost:8005/tts \
  -H 'Content-Type: application/json' \
  -d '{
    "text": "Привет. Это тест синтеза речи.",
    "language_id": "ru",
    "output_format": "wav",
    "voice": "valera",
    "exaggeration": 0.5,
    "cfg_weight": 0.5,
    "temperature": 0.8
  }' \
  --output speech.wav
```

Multipart example:

```bash
curl -X POST http://localhost:8005/tts \
  -F 'text=Bonjour, ceci est un test.' \
  -F 'language_id=fr' \
  -F 'output_format=ogg' \
  -F 'voice=sergei' \
  -F 'exaggeration=0.7' \
  -F 'cfg_weight=0.3' \
  --output speech.ogg
```

Parameters:

- `text` - required input text.
- `language_id` - language code, default `ru`.
- `output_format` - output audio format: `wav` or `ogg`, default `wav`.
- `exaggeration` - emotion/intensity control, default `0.5`.
- `cfg_weight` - CFG/pacing control, default `0.5`; lower values can slow expressive speech.
- `temperature` - sampling temperature, default `0.8`.
- `seed` - optional deterministic seed if supported by the installed Chatterbox version.
- `voice` - optional voice name; the service looks up `<voices dir>/<voice>.wav`.

For Russian (`language_id=ru`), the service expands standalone numbers into
words before synthesis, so `2025` is spoken as words instead of being passed to
the model as raw digits.

## Local Run

Use Python 3.11 or 3.12. For CUDA, install a PyTorch build that matches your
driver/CUDA stack if the default wheel is not CUDA-enabled.

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Put reference voice WAV files into `voices/` before calling `/tts`, for example:
`voices/valera.wav`, `voices/sergei.wav`.

Check that CUDA is active:

```bash
curl http://localhost:8005/health
```

For an RTX 4060, `"device"` should be `"cuda"` and `cuda_available` should be
`true`.

## Docker

The image is based on an NVIDIA CUDA runtime. The host needs NVIDIA Container
Toolkit installed.

```bash
docker build -t gop-fm-tts .
docker run --gpus all -p 8005:8005 \
  -e HOST=0.0.0.0 \
  -e PORT=8005 \
  -e TTS_DEVICE=auto \
  -e TTS_PRELOAD=true \
  gop-fm-tts
```

The first startup downloads Chatterbox model weights and can take time.

## Configuration

Important defaults:

- `TTS_DEVICE=auto` - use CUDA if available, otherwise CPU.
- `TTS_PRELOAD=true` - load the model at startup instead of first request.
- `TTS_MAX_TEXT_LENGTH=4000` - per-request text limit.
- `TTS_VOICES_DIR=voices` - directory with local voice reference WAV files.
