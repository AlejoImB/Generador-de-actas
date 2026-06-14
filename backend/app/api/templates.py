import os
import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.models.models import Template, User
from app.schemas.schemas import TemplateIn, TemplateOut, TemplatePatchIn
from app.api.deps import get_current_user
from app.services.word_service import extract_schema_from_docx

router = APIRouter(prefix="/api/templates", tags=["templates"])

UPLOAD_DIR = "uploads/templates"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.get("", response_model=list[TemplateOut])
def list_templates(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.query(Template).filter(
        Template.org_id == user.org_id, Template.is_active == True  # noqa: E712
    ).all()


@router.post("", response_model=TemplateOut)
def create_template(body: TemplateIn, db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    """Crear una plantilla nueva = solo insertar datos. Sin desarrollo."""
    if user.role not in ("admin", "editor"):
        raise HTTPException(403, "No autorizado")
    t = Template(org_id=user.org_id, name=body.name, description=body.description,
                 icon=body.icon, schema=body.schema)
    db.add(t); db.commit(); db.refresh(t)
    return t


@router.post("/upload", response_model=TemplateOut)
async def upload_template(
    name: str = Form(...),
    description: str = Form(""),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Sube un documento Word (.docx) y crea una plantilla automáticamente."""
    if not file.filename.endswith(".docx"):
        raise HTTPException(400, "El archivo debe ser un .docx")
        
    file_bytes = await file.read()
    schema = extract_schema_from_docx(file_bytes)
    
    safe_filename = f"{uuid.uuid4().hex}.docx"
    file_path = os.path.join(UPLOAD_DIR, safe_filename)
    with open(file_path, "wb") as f:
        f.write(file_bytes)
        
    t = Template(org_id=user.org_id, name=name, description=description,
                 icon="📄", schema=schema, file_path=file_path)
    db.add(t); db.commit(); db.refresh(t)
    return t

@router.put("/{template_id}", response_model=TemplateOut)
def update_template(template_id: str, body: TemplateIn, db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    t = db.get(Template, template_id)
    if not t or t.org_id != user.org_id:
        raise HTTPException(404, "Plantilla no encontrada")
    t.name, t.description, t.icon, t.schema = body.name, body.description, body.icon, body.schema
    t.version += 1
    db.commit(); db.refresh(t)
    return t


@router.patch("/{template_id}", response_model=TemplateOut)
def patch_template(template_id: str, body: TemplatePatchIn, db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    t = db.get(Template, template_id)
    if not t or t.org_id != user.org_id:
        raise HTTPException(404, "Plantilla no encontrada")
    t.name = body.name
    t.description = body.description
    db.commit(); db.refresh(t)
    return t


@router.delete("/{template_id}", status_code=204)
def delete_template(template_id: str, db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    t = db.get(Template, template_id)
    if not t or t.org_id != user.org_id:
        raise HTTPException(404, "Plantilla no encontrada")
    if user.role != "admin":
        raise HTTPException(403, "Solo administradores pueden eliminar plantillas")
    t.is_active = False
    db.commit()
