from typing import Literal

from pydantic import BaseModel, Field, field_validator


SUPPORTED_LANGUAGES: dict[str, str] = {
    "ar": "Arabic",
    "da": "Danish",
    "de": "German",
    "el": "Greek",
    "en": "English",
    "es": "Spanish",
    "fi": "Finnish",
    "fr": "French",
    "he": "Hebrew",
    "hi": "Hindi",
    "it": "Italian",
    "ja": "Japanese",
    "ko": "Korean",
    "ms": "Malay",
    "nl": "Dutch",
    "no": "Norwegian",
    "pl": "Polish",
    "pt": "Portuguese",
    "ru": "Russian",
    "sv": "Swedish",
    "sw": "Swahili",
    "tr": "Turkish",
    "zh": "Chinese",
}


class TTSRequest(BaseModel):
    text: str = Field(..., min_length=1)
    language_id: str = Field(default="ru")
    output_format: Literal["wav", "ogg"] = "wav"
    exaggeration: float | None = Field(default=None, ge=0.0, le=2.0)
    cfg_weight: float | None = Field(default=None, ge=0.0, le=2.0)
    temperature: float | None = Field(default=None, ge=0.05, le=5.0)
    seed: int | None = Field(default=None, ge=0)
    voice: str | None = Field(default=None, min_length=1)

    @field_validator("language_id")
    @classmethod
    def validate_language(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in SUPPORTED_LANGUAGES:
            supported = ", ".join(sorted(SUPPORTED_LANGUAGES))
            raise ValueError(f"Unsupported language_id '{value}'. Supported: {supported}")
        return normalized

    @field_validator("voice")
    @classmethod
    def validate_voice(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        if not normalized:
            raise ValueError("voice must not be empty")
        allowed = set("abcdefghijklmnopqrstuvwxyz0123456789_-")
        if any(char not in allowed for char in normalized):
            raise ValueError("voice may contain only lowercase latin letters, digits, '-' and '_'")
        return normalized


class LanguageItem(BaseModel):
    code: str
    name: str


class LanguagesResponse(BaseModel):
    languages: list[LanguageItem]
    count: int


class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    device: str
    cuda_available: bool
    cuda_device_name: str | None = None
