from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All settings come from environment variables prefixed UGC_ (or a .env file)."""

    model_config = SettingsConfigDict(env_prefix="UGC_", env_file=".env", extra="ignore")

    data_dir: Path = Path("./data")
    api_key: str | None = None  # when set, clients must send X-API-Key
    workers: int = 1  # concurrent render jobs
    step_retries: int = 2  # attempts per plugin before falling back to the next one

    # Preferred plugin per capability; others remain as automatic fallbacks.
    # Example: UGC_PREFERRED='{"analyze": "claude", "voice": "voicestudio"}'
    preferred: dict[str, str] = {}

    anthropic_model: str = "claude-opus-5-5"
    voicestudio_url: str = "http://localhost:3900"
    voicestudio_engine: str = "kittentts"  # Apache-2.0 weights: safe for commercial ads
    voice_speed: float = 1.2
    kitten_model: str = "KittenML/kitten-tts-mini-0.8"  # or kitten-tts-nano-0.8 (smaller, lower quality)
    kitten_voice: str = "Jasper"  # Bella, Jasper, Luna, Bruno, Rosie, Hugo, Kiki, Leo
    allow_private_urls: bool = False  # dev only: let product links point at localhost/LAN
    fetch_user_agent: str = "UGCStudioBot/0.1 (+https://github.com/jobyjoy039-cyber/Blog)"
    font: str = "Inter"


@lru_cache
def get_settings() -> Settings:
    return Settings()
