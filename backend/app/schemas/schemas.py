"""Schemas Pydantic (contratos de la API)."""
from pydantic import BaseModel, EmailStr
from typing import Any
from datetime import datetime


# ---- Auth ----
class LoginIn(BaseModel):
    email: EmailStr
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


# ---- Templates ----
class TemplateField(BaseModel):
    key: str
    label: str
    type: str = "text"          # text | list | date | people | table
    required: bool = False
    hint: str = ""


class TemplateSection(BaseModel):
    key: str
    title: str
    fields: list[TemplateField]


class TemplateIn(BaseModel):
    name: str
    description: str = ""
    icon: str = "◫"
    schema: dict                # {"sections": [...]}

class TemplatePatchIn(BaseModel):
    name: str
    description: str = ""


class TemplateOut(BaseModel):
    id: str
    name: str
    description: str
    icon: str
    version: int
    is_active: bool
    schema: dict
    class Config: from_attributes = True


# ---- Transcripts ----
class TranscriptIn(BaseModel):
    title: str
    content: str
    source: str = "upload"


class TranscriptEditIn(BaseModel):
    content: str


class TranscriptOut(BaseModel):
    id: str
    title: str
    source: str
    word_count: int
    current_version: int
    content: str
    created_at: datetime
    class Config: from_attributes = True


# ---- Actas ----
class GenerateIn(BaseModel):
    transcript_id: str
    template_id: str


class ActaOut(BaseModel):
    id: str
    transcript_id: str
    template_id: str
    status: str
    data: dict
    missing_fields: list
    avg_confidence: int
    created_at: datetime
    class Config: from_attributes = True


class FieldEditIn(BaseModel):
    section_key: str
    field_key: str
    value: Any
