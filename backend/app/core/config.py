"""Configuración central. Lee variables de entorno (12-factor).
En producción los secretos vienen de Secret Manager; aquí de .env."""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_NAME: str = "Detto"
    ENV: str = "dev"
    SECRET_KEY: str = "cambia-esto-en-produccion-por-un-secreto-largo"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 8
    DATABASE_URL: str = "sqlite:///./acta_ia.db"

    # Proveedor de IA — elegir uno: anthropic | groq | ollama | mock
    AI_PROVIDER: str = "anthropic"
    AI_MODEL: str = "claude-sonnet-4-6"

    # Anthropic (Claude)
    ANTHROPIC_API_KEY: str = ""

    # Groq (nube, gratuito con límites generosos)
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.1-70b-versatile"   # o mixtral-8x7b-32768

    # Ollama (local, sin costo)
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.1:8b"              # o mistral:7b, gemma2:9b

    CORS_ORIGINS: str = "*"

    # ── Zitadel (SSO corporativo) ─────────────────────────
    # Si ZITADEL_DOMAIN está vacío la app usa auth local
    ZITADEL_DOMAIN: str = ""          # https://auth.tuempresa.com
    ZITADEL_CLIENT_ID: str = ""       # del app detto-frontend en Zitadel
    ZITADEL_CLIENT_SECRET: str = ""   # del app detto-backend en Zitadel
    ZITADEL_PROJECT_ID: str = ""      # ID del proyecto Detto en Zitadel


@lru_cache
def get_settings() -> Settings:
    return Settings()
