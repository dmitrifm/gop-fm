from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    host: str = Field(default="0.0.0.0", alias="HOST")
    port: int = Field(default=8000, alias="PORT")

    tts_device: str = Field(default="auto", alias="TTS_DEVICE")
    tts_preload: bool = Field(default=True, alias="TTS_PRELOAD")

    tts_default_language: str = Field(default="ru", alias="TTS_DEFAULT_LANGUAGE")
    tts_default_exaggeration: float = Field(default=0.5, alias="TTS_DEFAULT_EXAGGERATION")
    tts_default_cfg_weight: float = Field(default=0.5, alias="TTS_DEFAULT_CFG_WEIGHT")
    tts_default_temperature: float = Field(default=0.8, alias="TTS_DEFAULT_TEMPERATURE")
    tts_max_text_length: int = Field(default=4000, alias="TTS_MAX_TEXT_LENGTH")
    tts_voices_dir: str = Field(default="voices", alias="TTS_VOICES_DIR")


@lru_cache
def get_settings() -> Settings:
    return Settings()
