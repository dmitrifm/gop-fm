import inspect
import os
import re
import tempfile
import threading
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import numpy as np
import torch
import torchaudio as ta

from ruaccent import RUAccent

from app.config import Settings


class TTSEngine:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._model: Any | None = None
        self._accent: Any | None = None

        self._device = self._resolve_device(settings.tts_device)

        self._load_lock = threading.Lock()
        self._accent_lock = threading.Lock()
        self._generate_lock = threading.Lock()

    @property
    def device(self) -> str:
        return self._device

    @property
    def loaded(self) -> bool:
        return self._model is not None

    def load(self) -> None:
        if self._model is not None:
            return

        with self._load_lock:
            if self._model is not None:
                return

            if self._device == "cuda":
                torch.set_float32_matmul_precision("high")

            self._ensure_perth_watermarker()

            from chatterbox.mtl_tts import ChatterboxMultilingualTTS

            self._model = ChatterboxMultilingualTTS.from_pretrained(device=self._device)

    def generate_to_wav_file(
        self,
        *,
        text: str,
        language_id: str,
        output_dir: str,
        audio_prompt_path: str | None = None,
        generation_options: Mapping[str, Any] | None = None,
    ) -> str:
        return self.generate_to_audio_file(
            text=text,
            language_id=language_id,
            output_dir=output_dir,
            output_format="wav",
            audio_prompt_path=audio_prompt_path,
            generation_options=generation_options,
        )

    def generate_to_audio_file(
        self,
        *,
        text: str,
        language_id: str,
        output_dir: str,
        output_format: str,
        audio_prompt_path: str | None = None,
        generation_options: Mapping[str, Any] | None = None,
    ) -> str:
        normalized_output_format = output_format.strip().lower()
        wav, sample_rate = self._generate_wav_tensor(
            text=text,
            language_id=language_id,
            audio_prompt_path=audio_prompt_path,
            generation_options=generation_options,
        )

        fd, path = tempfile.mkstemp(
            prefix="tts-",
            suffix=f".{normalized_output_format}",
            dir=output_dir,
        )
        os.close(fd)
        save_kwargs = {}
        if normalized_output_format != "wav":
            save_kwargs["format"] = normalized_output_format
        if normalized_output_format == "ogg":
            save_kwargs["backend"] = "soundfile"
        ta.save(path, wav.cpu(), sample_rate, **save_kwargs)
        return path

    # ===================== RUACCENT =====================

    def _load_accent(self) -> None:
        if self._accent is not None:
            return

        with self._accent_lock:
            if self._accent is not None:
                return

            accent = RUAccent()
            accent.load(
                omograph_model_size="turbo2",
                use_dictionary=True,
                custom_dict={},
                device="GPU" if self._device == "cuda" else "CPU",
                workdir=None,
                tiny_mode=True,
            )

            self._patch_ruaccent_token_type_ids(accent)

            self._accent = accent

    def _apply_stress(self, text: str) -> str:
        if not text.strip():
            return text

        self._load_accent()
        assert self._accent is not None

        try:
            raw = self._accent.process_all(text)
            return self._ruaccent_to_combining_acute(raw)
        except Exception:
            return text

    def _patch_ruaccent_token_type_ids(self, accent: Any) -> None:
        for attr_name in ("accent_model", "omograph_model"):
            model = getattr(accent, attr_name, None)
            if model is None:
                continue

            session = getattr(model, "session", None)
            if session is None:
                continue

            model.session = self._wrap_onnx_session_with_token_type_ids(session)

    @staticmethod
    def _wrap_onnx_session_with_token_type_ids(session: Any) -> Any:
        class SessionWrapper:
            def __init__(self, wrapped: Any) -> None:
                self._wrapped = wrapped
                self._input_names = {
                    item.name for item in wrapped.get_inputs()
                }

            def run(self, output_names: Any, input_feed: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
                if (
                    "token_type_ids" in self._input_names
                    and "token_type_ids" not in input_feed
                    and "input_ids" in input_feed
                ):
                    input_feed = dict(input_feed)
                    input_feed["token_type_ids"] = np.zeros_like(input_feed["input_ids"])

                return self._wrapped.run(output_names, input_feed, *args, **kwargs)

            def __getattr__(self, name: str) -> Any:
                return getattr(self._wrapped, name)

        return SessionWrapper(session)

    @staticmethod
    def _ruaccent_to_combining_acute(text: str) -> str:
        vowels = "аеёиоуыэюяАЕЁИОУЫЭЮЯ"

        def repl(match: re.Match[str]) -> str:
            return match.group(1) + "\u0301"

        # +о → о́
        text = re.sub(rf"\+([{vowels}])", repl, text)

        # remove remaining "+"  characters
        text = text.replace("+", "")

        # custom fix example
        post_process_map = {
            "мусора": "мусора́",
        }

        for source, target in post_process_map.items():
            text = text.replace(source, target)

        return text

    # ===================== UTILS =====================

    def _filter_generate_kwargs(self, kwargs: dict[str, Any]) -> dict[str, Any]:
        assert self._model is not None
        signature = inspect.signature(self._model.generate)
        if any(param.kind == inspect.Parameter.VAR_KEYWORD for param in signature.parameters.values()):
            return kwargs
        return {key: value for key, value in kwargs.items() if key in signature.parameters}

    def _generate_wav_tensor(
        self,
        *,
        text: str,
        language_id: str,
        audio_prompt_path: str | None = None,
        generation_options: Mapping[str, Any] | None = None,
    ) -> tuple[torch.Tensor, int]:
        self.load()
        assert self._model is not None

        normalized_language_id = language_id.strip().lower()
        if normalized_language_id.startswith("ru"):
            text = self._apply_stress(text)

        kwargs = {
            "language_id": language_id,
            "audio_prompt_path": audio_prompt_path,
            **dict(generation_options or {}),
        }
        kwargs = {key: value for key, value in kwargs.items() if value is not None}
        kwargs = self._filter_generate_kwargs(kwargs)

        with self._generate_lock:
            wav = self._model.generate(text, **kwargs)

        wav = self._normalize_wav_tensor(wav)
        sample_rate = int(getattr(self._model, "sr", 24000))
        return wav, sample_rate

    @staticmethod
    def _normalize_wav_tensor(wav: torch.Tensor) -> torch.Tensor:
        if not isinstance(wav, torch.Tensor):
            wav = torch.as_tensor(wav)
        wav = wav.detach()
        if wav.ndim == 1:
            wav = wav.unsqueeze(0)
        if wav.ndim == 2 and wav.shape[0] > wav.shape[1]:
            wav = wav.transpose(0, 1)
        if wav.dtype != torch.float32:
            wav = wav.float()
        return wav.clamp(-1.0, 1.0)

    @staticmethod
    def _resolve_device(configured_device: str) -> str:
        device = configured_device.strip().lower()
        if device == "auto":
            return "cuda" if torch.cuda.is_available() else "cpu"
        if device == "cuda" and not torch.cuda.is_available():
            return "cpu"
        return device

    @staticmethod
    def _ensure_perth_watermarker() -> None:
        import perth

        if getattr(perth, "PerthImplicitWatermarker", None) is not None:
            return

        class NoOpPerthImplicitWatermarker:
            def apply_watermark(
                self,
                wav: np.ndarray,
                watermark: np.ndarray | None = None,
                sample_rate: int = 44100,
                **_: Any,
            ) -> np.ndarray:
                return wav

            def get_watermark(
                self,
                watermarked_wav: np.ndarray,
                sample_rate: int = 44100,
                watermark_length: int | None = None,
                **_: Any,
            ) -> np.ndarray:
                length = watermark_length if watermark_length is not None else 0
                return np.zeros(length, dtype=np.float32)

        perth.PerthImplicitWatermarker = NoOpPerthImplicitWatermarker


def resolve_voice_prompt_path(voices_dir: str, voice: str) -> str:
    base_dir = Path(voices_dir).expanduser()
    if not base_dir.is_absolute():
        base_dir = Path.cwd() / base_dir
    base_dir = base_dir.resolve()

    path = (base_dir / f"{voice}.wav").resolve()

    try:
        path.relative_to(base_dir)
    except ValueError as exc:
        raise FileNotFoundError(f"Voice file does not exist: {path}") from exc

    if not path.is_file():
        raise FileNotFoundError(f"Voice file does not exist: {path}")

    return str(path)
