import io
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.models.models import Acta, Transcript, Template, AuditLog, User
from app.schemas.schemas import GenerateIn, ActaOut, FieldEditIn
from app.services.ai_service import generate_acta
from app.api.deps import get_current_user
from app.services.word_service import render_acta_to_docx

router = APIRouter(prefix="/api/actas", tags=["actas"])


def _log(db, acta_id, actor, action, detail=""):
    db.add(AuditLog(acta_id=acta_id, actor=actor, action=action, detail=detail))


@router.get("", response_model=list[ActaOut])
def list_actas(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.query(Acta).filter(Acta.org_id == user.org_id)\
             .order_by(Acta.created_at.desc()).all()


@router.post("/generate", response_model=ActaOut)
def generate(body: GenerateIn, db: Session = Depends(get_db),
             user: User = Depends(get_current_user)):
    """Paso 3 del flujo: ejecuta la IA sobre la transcripción usando el
    schema de la plantilla y produce el acta estructurada."""
    tr = db.get(Transcript, body.transcript_id)
    tpl = db.get(Template, body.template_id)
    if not tr or tr.org_id != user.org_id:
        raise HTTPException(404, "Transcripción no encontrada")
    if not tpl or tpl.org_id != user.org_id:
        raise HTTPException(404, "Plantilla no encontrada")

    data, missing, avg = generate_acta(tpl.schema, tr.content)
    acta = Acta(org_id=user.org_id, transcript_id=tr.id, template_id=tpl.id,
                template_version=tpl.version, status="draft", data=data,
                missing_fields=missing, avg_confidence=avg, created_by=user.id)
    db.add(acta); db.commit(); db.refresh(acta)
    _log(db, acta.id, user.name, "generada",
         f"{len(missing)} campos faltantes · confianza media {avg}%")
    db.commit()
    return acta


@router.get("/{aid}", response_model=ActaOut)
def get_acta(aid: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    a = db.get(Acta, aid)
    if not a or a.org_id != user.org_id:
        raise HTTPException(404, "Acta no encontrada")
    return a


@router.patch("/{aid}/field", response_model=ActaOut)
def edit_field(aid: str, body: FieldEditIn, db: Session = Depends(get_db),
               user: User = Depends(get_current_user)):
    """Edición/validación manual de un campo (p.ej. completar faltante)."""
    a = db.get(Acta, aid)
    if not a or a.org_id != user.org_id:
        raise HTTPException(404, "Acta no encontrada")
    data = dict(a.data)
    sec = data.get(body.section_key)
    if not sec or body.field_key not in sec["fields"]:
        raise HTTPException(422, "Campo inexistente en el acta")
    sec["fields"][body.field_key].update(
        {"value": body.value, "confidence": 100, "source": "Validado por usuario"})
    a.data = data
    a.missing_fields = [m for m in a.missing_fields
                        if not (m["section"] == body.section_key and m["field"] == body.field_key)]
    db.commit(); db.refresh(a)
    _log(db, a.id, user.name, "campo editado", f'{body.section_key}.{body.field_key}')
    db.commit()
    return a


@router.post("/{aid}/approve", response_model=ActaOut)
def approve(aid: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    a = db.get(Acta, aid)
    if not a or a.org_id != user.org_id:
        raise HTTPException(404, "Acta no encontrada")
    if a.missing_fields:
        raise HTTPException(409, "No se puede aprobar: hay campos obligatorios faltantes")
    a.status = "approved"; a.reviewer_id = user.id
    db.commit(); db.refresh(a)
    _log(db, a.id, user.name, "aprobada")
    db.commit()
    return a


@router.get("/{aid}/audit")
def audit(aid: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    a = db.get(Acta, aid)
    if not a or a.org_id != user.org_id:
        raise HTTPException(404, "Acta no encontrada")
    return [{"actor": l.actor, "action": l.action, "detail": l.detail,
             "created_at": l.created_at} for l in sorted(a.audit, key=lambda x: x.created_at)]

@router.get("/{aid}/download")
def download(aid: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Descarga el acta final inyectando los datos en la plantilla Word original."""
    a = db.get(Acta, aid)
    if not a or a.org_id != user.org_id:
        raise HTTPException(404, "Acta no encontrada")
    if a.status != "approved":
        raise HTTPException(400, "El acta debe estar aprobada para ser descargada")
        
    tpl = db.get(Template, a.template_id)
    if not tpl or not tpl.file_path:
        raise HTTPException(400, "La plantilla original no está disponible")
        
    tpl_type = tpl.schema.get("_tpl_type", "auto")
    docx_bytes = render_acta_to_docx(tpl.file_path, a.data, tpl_type)
    return StreamingResponse(
        io.BytesIO(docx_bytes),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="Acta_{a.id}.docx"'}
    )
