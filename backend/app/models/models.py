"""Modelo de datos. Diseñado multi-tenant (organización) y con plantillas
data-driven: la estructura del acta vive en Template.schema (JSON), de modo
que agregar una plantilla nueva NO requiere tocar el código."""
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Text, ForeignKey, JSON, Integer, DateTime, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.database import Base


def _id() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Organization(Base):
    __tablename__ = "organizations"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    name: Mapped[str] = mapped_column(String(160))
    plan: Mapped[str] = mapped_column(String(40), default="empresarial")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    users = relationship("User", back_populates="org")
    templates = relationship("Template", back_populates="org")


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"))
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(30), default="editor")  # admin|editor|reviewer
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    org = relationship("Organization", back_populates="users")


class Template(Base):
    """Plantilla configurable. `schema` define las secciones y campos.
    Ejemplo de schema:
      {"sections":[{"key":"asistentes","title":"Asistentes",
        "fields":[{"key":"participantes","label":"Participantes",
                   "type":"list","required":true,"hint":"personas presentes"}]}]}"""
    __tablename__ = "templates"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"))
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text, default="")
    icon: Mapped[str] = mapped_column(String(8), default="◫")
    version: Mapped[int] = mapped_column(Integer, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    schema: Mapped[dict] = mapped_column(JSON)
    file_path: Mapped[str] = mapped_column(String(255), nullable=True) # Para guardar el archivo .docx
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    org = relationship("Organization", back_populates="templates")


class Transcript(Base):
    __tablename__ = "transcripts"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"))
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String(200))
    source: Mapped[str] = mapped_column(String(40), default="upload")  # upload|zoom|meet|teams
    content: Mapped[str] = mapped_column(Text)
    word_count: Mapped[int] = mapped_column(Integer, default=0)
    current_version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    versions = relationship("TranscriptVersion", back_populates="transcript",
                            cascade="all, delete-orphan")


class TranscriptVersion(Base):
    """Historial de versiones de la transcripción (edición manual)."""
    __tablename__ = "transcript_versions"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    transcript_id: Mapped[str] = mapped_column(ForeignKey("transcripts.id"))
    version: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    edited_by: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    transcript = relationship("Transcript", back_populates="versions")


class Acta(Base):
    __tablename__ = "actas"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"))
    transcript_id: Mapped[str] = mapped_column(ForeignKey("transcripts.id"))
    template_id: Mapped[str] = mapped_column(ForeignKey("templates.id"))
    template_version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(30), default="draft")  # draft|review|approved
    data: Mapped[dict] = mapped_column(JSON)          # contenido extraído por sección/campo
    missing_fields: Mapped[list] = mapped_column(JSON, default=list)
    avg_confidence: Mapped[int] = mapped_column(Integer, default=0)
    reviewer_id: Mapped[str] = mapped_column(String(32), default="")
    created_by: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    audit = relationship("AuditLog", back_populates="acta", cascade="all, delete-orphan")


class AuditLog(Base):
    """Registro de auditoría: quién hizo qué y cuándo."""
    __tablename__ = "audit_logs"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    acta_id: Mapped[str] = mapped_column(ForeignKey("actas.id"))
    actor: Mapped[str] = mapped_column(String(120))
    action: Mapped[str] = mapped_column(String(80))
    detail: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    acta = relationship("Acta", back_populates="audit")
