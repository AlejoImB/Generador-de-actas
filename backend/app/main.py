from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
import os
from app.core.config import get_settings
from app.db.database import Base, engine
from app.models import models  # noqa: F401
from app.api import auth, templates, transcripts, actas

settings = get_settings()
Base.metadata.create_all(bind=engine)

# Re-parse existing templates schemas from their docx files on startup to ensure they have the latest table metadata
from app.db.database import SessionLocal
from app.models.models import Template
from app.services.word_service import extract_schema_from_docx

def migrate_template_schemas():
    db = SessionLocal()
    try:
        templates = db.query(Template).filter(Template.is_active == True).all()
        for t in templates:
            if t.file_path and os.path.exists(t.file_path):
                try:
                    with open(t.file_path, "rb") as f:
                        file_bytes = f.read()
                    new_schema = extract_schema_from_docx(file_bytes)
                    t.schema = new_schema
                    from sqlalchemy.orm.attributes import flag_modified
                    flag_modified(t, "schema")
                    print(f"Re-migrated template schema for: {t.name}")
                except Exception as e:
                    print(f"Error migrating template {t.name}: {e}")
        db.commit()
    except Exception as err:
        print(f"Migration error: {err}")
    finally:
        db.close()

migrate_template_schemas()

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


# Servir el frontend directamente en la raíz "/"
frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../frontend"))

@app.get("/")
def serve_index():
    return FileResponse(os.path.join(frontend_dir, "index.html"))

@app.get("/index.html")
def serve_index_html():
    return FileResponse(os.path.join(frontend_dir, "index.html"))
