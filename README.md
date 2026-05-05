# Gop-FM

AI radio stack with Icecast streaming, Liquidsoap automation, an OpenAI-powered DJ orchestrator, and a local Chatterbox-based TTS service.

![Valera DJ](assets/valera.png)

## Overview

The project is designed to be built and started from the repository root with Docker Compose.

The stack contains four services:

- `icecast` publishes the radio stream on port `8000`.
- `liquidsoap` plays music from a local library, watches for queued jingles, and pushes audio to Icecast.
- `orchestrator` receives track change events, generates a short DJ line with OpenAI, calls the TTS service, and writes ready-to-play WAV files into the jingles queue.
- `tts_api` is a FastAPI service that synthesizes WAV audio from text using Chatterbox Multilingual TTS and local voice reference files.

## Runtime Flow

1. `liquidsoap` starts playback from `/music`.
2. On track metadata updates, `liquidsoap` sends a `track_started` event to `orchestrator`.
3. `orchestrator` asks OpenAI to generate a short in-character radio line.
4. `orchestrator` sends that text to `tts_api`.
5. `tts_api` returns a WAV file.
6. `orchestrator` normalizes the WAV with `ffmpeg` and writes it to `/jingles/queued`.
7. `liquidsoap` detects the queued file, moves it into `/jingles/playing`, and plays it before falling back to music.

There is a built-in cooldown of 60 seconds between generated DJ inserts.

## Repository Layout

```text
.
├── docker-compose.yml
├── .env
├── liquidsoap/
│   ├── Dockerfile
│   └── radio.liq
├── orchestrator/
│   ├── Dockerfile
│   ├── main.py
│   └── requirements.txt
└── tts_api/
    ├── Dockerfile
    ├── README.md
    ├── app/
    ├── voices/
    ├── requirements.txt
    └── pyproject.toml
```

## Requirements

- Docker Engine with Docker Compose
- An OpenAI API key for the orchestrator
- A local music directory on the host
- A local jingles directory on the host
- For `tts_api`, an NVIDIA-capable host is the intended target because the image is based on CUDA
- If you want GPU acceleration inside containers, the host should have NVIDIA drivers and NVIDIA Container Toolkit installed

## NVIDIA Container Toolkit

If `tts_api` starts with a warning that no NVIDIA driver was detected inside the container, the host Docker runtime is not configured for GPU passthrough yet.

Before continuing, verify that the host driver is working:

```bash
nvidia-smi
```

For Ubuntu or Debian, install NVIDIA Container Toolkit on the host:

```bash
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | \
  sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg

curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
  sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

sudo apt-get update

export NVIDIA_CONTAINER_TOOLKIT_VERSION=1.17.8-1
sudo apt-get install -y \
  nvidia-container-toolkit=${NVIDIA_CONTAINER_TOOLKIT_VERSION} \
  nvidia-container-toolkit-base=${NVIDIA_CONTAINER_TOOLKIT_VERSION} \
  libnvidia-container-tools=${NVIDIA_CONTAINER_TOOLKIT_VERSION} \
  libnvidia-container1=${NVIDIA_CONTAINER_TOOLKIT_VERSION}

sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

If your host is not Ubuntu or Debian, follow the official NVIDIA guide for the matching package manager.

After installation, validate Docker GPU access:

```bash
docker run --rm --gpus all nvidia/cuda:12.6.3-cudnn-runtime-ubuntu24.04 nvidia-smi
```

Then rebuild and start this project again:

```bash
docker compose up --build
```

You can confirm the TTS service is using CUDA with:

```bash
curl http://localhost:8005/health
```

Expected result:

- `cuda_available` should be `true`
- `device` should be `cuda`

## Configuration

All runtime variables are defined in `.env` file.

### Icecast

- `ICECAST_SOURCE_PASSWORD`
- `ICECAST_ADMIN_PASSWORD`
- `ICECAST_RELAY_PASSWORD`
- `ICECAST_ADMIN_USERNAME`
- `ICECAST_ADMIN_EMAIL`
- `ICECAST_HOSTNAME`

### Host Paths

- `MUSIC_PATH` points to the host directory with audio files
- `JINGLES_PATH` points to the host directory used for generated jingles

Expected structure under `JINGLES_PATH` at runtime:

```text
JINGLES_PATH/
├── queued/
└── playing/
```

The directories are created on demand if they do not exist.

### Orchestrator

- `OPENAI_API_KEY`
- `TTS_URL`
- `LLM_SYSTEM_PROMPT`

Default internal Compose URL:

```text
http://tts_api:8005/tts
```

The DJ persona and style prompt are configured through `LLM_SYSTEM_PROMPT` in the root `.env`

### TTS API

- `TTS_HOST`
- `TTS_PORT`
- `TTS_DEVICE`
- `TTS_PRELOAD`
- `TTS_DEFAULT_LANGUAGE`
- `TTS_DEFAULT_EXAGGERATION`
- `TTS_DEFAULT_CFG_WEIGHT`
- `TTS_DEFAULT_TEMPERATURE`
- `TTS_MAX_TEXT_LENGTH`
- `TTS_VOICES_DIR`

The included TTS code also uses `RUAccent`, so that dependency is part of the TTS service build.

## Quick Start

Use `.env.example` as a template. Copy it to a `.env` file in the project root, or place it in another location on your filesystem as needed.

1. Edit the `.env` and set at least:
   - `OPENAI_API_KEY`
   - `MUSIC_PATH`
   - `JINGLES_PATH`
   - `LLM_SYSTEM_PROMPT`
2. Make sure your host directories exist and contain music files.
3. Put voice reference WAV files into `tts_api/voices/`.
4. Build and start the stack:

```bash
docker compose up --build -d
```

or if you're using a .env file that is not located in the project root, run Docker Compose with the --env-file option to specify its path.

```bash
docker compose --env-file /absolute/path/to/your/.env up --build -d
```

5. Open Icecast:

```text
http://localhost:8000
```

The stream mount configured in Liquidsoap is:

```text
http://localhost:8000/gopfm.mp3
```

## Services

### Icecast

- Exposed on `localhost:8000`
- Receives source audio from `liquidsoap`
- Serves the final MP3 stream

### Liquidsoap

- Builds from `./liquidsoap`
- Mounts `MUSIC_PATH` as `/music`
- Mounts `JINGLES_PATH` as `/jingles`
- Sends track events to `http://orchestrator:9000/event`
- Publishes to Icecast mount `/gopfm.mp3`

### Orchestrator

- Internal-only service in the root Compose network
- Receives `POST /event`
- Calls OpenAI Responses API
- Calls `tts_api` through `TTS_URL`
- Reads DJ persona and style instructions from `LLM_SYSTEM_PROMPT`
- Converts returned audio to `44.1kHz`, stereo, PCM WAV before queuing playback

The default configuration is tuned for a DJ persona named Valera and uses the `valera` voice when calling TTS.

### TTS API

- Exposed on `localhost:8005` by default inside the current root compose
- Builds from `./tts_api`
- Requests `gpus: all` in Docker Compose
- Mounts `./tts_api/voices` into the container as `/app/voices`
- Generates WAV speech from text and a selected reference voice

Available endpoints:

- `GET /health`
- `GET /languages`
- `POST /tts`

Example request:

```bash
curl -X POST http://localhost:8005/tts \
  -H 'Content-Type: application/json' \
  -d '{
    "text": "Привет! В студии Валера и вы на Гоп эфэм",
    "language_id": "ru",
    "voice": "valera",
    "exaggeration": 0.6,
    "cfg_weight": 0.6,
    "temperature": 0.6
  }' \
  --output speech.wav
```

## License

The original code in this repository is licensed under [Apache License 2.0](LICENSE).

This project also uses third-party software under separate licenses, including GPL, MIT, and Apache-licensed components. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

Notable upstream licenses:

- Icecast: GPL-2.0
- Liquidsoap: GPL-2.0-or-later
- Chatterbox TTS: MIT
- FastAPI: MIT
- pydantic-settings: MIT
- OpenAI Python SDK: Apache-2.0
- RUAccent: Apache Software License


## Notes

- `icecast` uses host port `8000`, while `tts_api` uses host port `8005` in the root Compose setup.
- `orchestrator` is not published to the host; `liquidsoap` reaches it over the internal Compose network at `http://orchestrator:9000/event`.
- The root stack is wired so `orchestrator` talks to `tts_api` over the internal Compose network, not through the host.
- GPU support for `tts_api` also requires NVIDIA drivers and NVIDIA Container Toolkit on the host.
- The first TTS startup can take time because model weights may need to be downloaded.
- The root directory currently contains the Compose project, while `tts_api` remains its own nested Git repository.

## Development

To rebuild only one service:

```bash
docker compose build tts_api
docker compose up tts_api
```

To inspect the fully resolved Compose configuration:

```bash
docker compose config
```

## Troubleshooting

If no AI jingles are played:

- Check that `OPENAI_API_KEY` is set
- Check `docker compose logs orchestrator`
- Check `docker compose logs tts_api`
- Check that `tts_api/voices/valera.wav` exists
- Check that `JINGLES_PATH/queued` receives generated WAV files

If the TTS container is slow or falls back to CPU:

- Verify NVIDIA drivers on the host
- Verify NVIDIA Container Toolkit installation
- Check `GET /health` on the TTS service to confirm the active device
