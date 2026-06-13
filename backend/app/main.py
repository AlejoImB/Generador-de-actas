"""Punto de entrada de la API ActaIA (modular monolith, listo para dividir
en microservicios: cada router/servicio ya tiene fronteras limpias)."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import get_settings
from app.db.database import Base, engine
from app.models import models  # noqa: F401  (registra las tablas)
from app.api import auth, templates, transcripts, actas

settings = get_settings()
Base.metadata.create_all(bind=engine)

app = FastAPI(title="ActaIA API", version="0.1.0",
              description="Generación inteligente de actas de reunión")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.CORS_ORIGINS.split(",")],
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(templates.router)
app.include_router(transcripts.router)
app.include_router(actas.router)


@app.get("/api/health")
def health():
    return {"status": "ok", "ai_provider": settings.AI_PROVIDER,
            "ai_ready": bool(settings.ANTHROPIC_API_KEY) or settings.AI_PROVIDER == "mock"}
