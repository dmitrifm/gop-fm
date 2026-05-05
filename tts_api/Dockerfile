FROM nvidia/cuda:12.6.3-cudnn-runtime-ubuntu24.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH=/opt/venv/bin:$PATH

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-venv ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN python3 -m venv /opt/venv \
    && pip install --upgrade pip \
    && pip install -r requirements.txt

COPY app ./app
COPY voices ./voices

ENV HOST=0.0.0.0 \
    PORT=8000 \
    TTS_DEVICE=auto \
    TTS_PRELOAD=true

EXPOSE 8000

CMD ["sh", "-c", "python -m uvicorn app.main:app --host ${HOST:-0.0.0.0} --port ${PORT:-8000}"]
