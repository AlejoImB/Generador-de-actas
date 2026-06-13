from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.models.models import Transcript, TranscriptVersion, User
from app.schemas.schemas import TranscriptIn, TranscriptOut, TranscriptEditIn
from app.services.files import extract_text
from app.api.deps import get_current_user

router = APIRouter(prefix="/api/transcripts", tags=["transcripts"])


def _wc(text: str) -> int:
    return len(text.split())


@router.get("", response_model=list[TranscriptOut])
def list_transcripts(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.query(Transcript).filter(Transcript.org_id == user.org_id)\
             .order_by(Transcript.created_at.desc()).all()


@router.post("", response_model=TranscriptOut)
def create_transcript(body: TranscriptIn, db: Session = Depends(get_db),
                      user: User = Depends(get_current_user)):
    t = Transcript(org_id=user.org_id, owner_id=user.id, title=body.title,
                   source=body.source, content=body.content, word_count=_wc(body.content))
    db.add(t); db.commit(); db.refresh(t)
    db.add(TranscriptVersion(transcript_id=t.id, version=1, content=t.content,
                             edited_by=user.id))
    db.commit()
    return t


@router.post("/upload", response_model=TranscriptOut)
async def upload(file: UploadFile = File(...), title: str = Form(""),
                 source: str = Form("upload"), db: Session = Depends(get_db),
                 user: User = Depends(get_current_user)):
    """Carga TXT, DOCX o PDF y extrae el texto."""
    raw = await file.read()
    try:
        text = extract_text(file.filename, raw)
    except Exception as e:
        raise HTTPException(422, f"No se pudo leer el archivo: {e}")
    if not text.strip():
        raise HTTPException(422, "El archivo no contiene texto extraíble")
    t = Transcript(org_id=user.org_id, owner_id=user.id,
                   title=title or file.filename, source=source,
                   content=text, word_count=_wc(text))
    db.add(t); db.commit(); db.refresh(t)
    db.add(TranscriptVersion(transcript_id=t.id, version=1, content=text, edited_by=user.id))
    db.commit()
    return t


@router.put("/{tid}", response_model=TranscriptOut)
def edit_transcript(tid: str, body: TranscriptEditIn, db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    """Edición manual -> crea una nueva versión en el historial."""
    t = db.get(Transcript, tid)
    if not t or t.org_id != user.org_id:
        raise HTTPException(404, "Transcripción no encontrada")
    t.current_version += 1
    t.content = body.content
    t.word_count = _wc(body.content)
    db.add(TranscriptVersion(transcript_id=t.id, version=t.current_version,
                             content=body.content, edited_by=user.id))
    db.commit(); db.refresh(t)
    return t


@router.get("/{tid}/versions")
def versions(tid: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    t = db.get(Transcript, tid)
    if not t or t.org_id != user.org_id:
        raise HTTPException(404, "Transcripción no encontrada")
    return [{"version": v.version, "edited_by": v.edited_by,
             "created_at": v.created_at} for v in sorted(t.versions, key=lambda x: x.version)]
