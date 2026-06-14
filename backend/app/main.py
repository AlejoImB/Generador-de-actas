from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.core.config import get_settings
from app.db.database import Base, engine
from app.models import models  # noqa: F401
from app.api import auth, templates, transcripts, actas

settings = get_settings()
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Detto API", version="1.0.0",
              description="Generación de actas de reunión — Detto by Innovasoft")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.CORS_ORIGINS.split(",")],
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

MAX_UPLOAD_MB = 10

@app.middleware("http")
async def limit_upload_size(request: Request, call_next):
    if request.method == "POST":
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > MAX_UPLOAD_MB * 1024 * 1024:
            return JSONResponse(
                status_code=413,
                content={"detail": f"Archivo demasiado grande. Máximo {MAX_UPLOAD_MB} MB."}
            )
    return await call_next(request)

app.include_router(auth.router)
app.include_router(templates.router)
app.include_router(transcripts.router)
app.include_router(actas.router)


@app.get("/api/health")
def health():
    return {"status": "ok", "ai_provider": settings.AI_PROVIDER,
            "ai_ready": bool(settings.ANTHROPIC_API_KEY) or settings.AI_PROVIDER == "mock"}
