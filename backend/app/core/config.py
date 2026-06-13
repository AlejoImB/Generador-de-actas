"""Configuración central. Lee variables de entorno (12-factor).
En producción los secretos vienen de Secret Manager; aquí de .env."""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_NAME: str = "ActaIA"
    ENV: str = "dev"
    SECRET_KEY: str = "cambia-esto-en-produccion-por-un-secreto-largo"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 8
    DATABASE_URL: str = "sqlite:///./acta_ia.db"

    # Proveedor de IA. Si no hay API key, el sistema usa un extractor
    # determinístico de demostración para que la app funcione end-to-end.
    AI_PROVIDER: str = "anthropic"           # anthropic | openai | gemini | mock
    ANTHROPIC_API_KEY: str = ""
    AI_MODEL: str = "claude-sonnet-4-5"
    CORS_ORIGINS: str = "*"


@lru_cache
def get_settings() -> Settings:
    return Settings()
