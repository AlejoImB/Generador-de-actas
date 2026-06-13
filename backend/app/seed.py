"""Siembra datos de arranque: organización, usuario demo y plantillas.
Ejecutar:  python -m app.seed
Las plantillas son data-driven: agregar una nueva = añadir un dict aquí
o usar el endpoint POST /api/templates (sin tocar código)."""
from app.db.database import SessionLocal, Base, engine
from app.models.models import Organization, User, Template
from app.core.security import hash_password

Base.metadata.create_all(bind=engine)

TEMPLATES = [
    {
        "name": "Comité de Gerencia", "icon": "◫",
        "description": "Acta formal con decisiones, compromisos y riesgos ejecutivos.",
        "schema": {"sections": [
            {"key": "identificacion", "title": "Identificación", "fields": [
                {"key": "reunion", "label": "Reunión", "type": "text", "required": True,
                 "hint": "nombre o tipo de la reunión"},
                {"key": "fecha_hora", "label": "Fecha y hora", "type": "date", "required": True,
                 "hint": "fecha y hora de inicio/fin"}]},
            {"key": "asistentes", "title": "Asistentes", "fields": [
                {"key": "participantes", "label": "Participantes", "type": "people",
                 "required": True, "hint": "personas presentes en la reunión"}]},
            {"key": "decisiones", "title": "Decisiones", "fields": [
                {"key": "decision", "label": "Decisión tomada", "type": "text",
                 "required": True, "hint": "acuerdos y decisiones aprobadas"}]},
            {"key": "compromisos", "title": "Compromisos", "fields": [
                {"key": "compromiso", "label": "Compromiso", "type": "text", "required": False,
                 "hint": "tareas, responsable y fecha de cumplimiento"}]},
            {"key": "riesgos", "title": "Riesgos", "fields": [
                {"key": "riesgo", "label": "Riesgo identificado", "type": "text",
                 "required": False, "hint": "riesgos o alertas mencionadas"}]},
        ]},
    },
    {
        "name": "Reunión Ágil", "icon": "⚡",
        "description": "Sprint review/retro: avances, bloqueos y acciones por responsable.",
        "schema": {"sections": [
            {"key": "identificacion", "title": "Identificación", "fields": [
                {"key": "sprint", "label": "Sprint", "type": "text", "required": True,
                 "hint": "número o nombre del sprint"},
                {"key": "participantes", "label": "Equipo", "type": "people", "required": True,
                 "hint": "miembros del equipo presentes"}]},
            {"key": "avances", "title": "Avances", "fields": [
                {"key": "avance", "label": "Avances", "type": "text", "required": True,
                 "hint": "qué se completó"}]},
            {"key": "bloqueos", "title": "Bloqueos", "fields": [
                {"key": "bloqueo", "label": "Bloqueos", "type": "text", "required": False,
                 "hint": "impedimentos y riesgos"}]},
            {"key": "tareas", "title": "Tareas", "fields": [
                {"key": "tarea", "label": "Tareas pendientes", "type": "text", "required": False,
                 "hint": "acciones, responsable y fecha"}]},
        ]},
    },
    {
        "name": "Comité de Riesgos", "icon": "⚠",
        "description": "Riesgos, controles, hallazgos y planes de mitigación.",
        "schema": {"sections": [
            {"key": "identificacion", "title": "Identificación", "fields": [
                {"key": "reunion", "label": "Reunión", "type": "text", "required": True,
                 "hint": "nombre de la sesión de riesgos"},
                {"key": "fecha_hora", "label": "Fecha", "type": "date", "required": True,
                 "hint": "fecha de la reunión"}]},
            {"key": "riesgos", "title": "Riesgos", "fields": [
                {"key": "riesgo", "label": "Riesgo", "type": "text", "required": True,
                 "hint": "riesgos identificados"}]},
            {"key": "mitigacion", "title": "Mitigación", "fields": [
                {"key": "plan", "label": "Plan de mitigación", "type": "text", "required": False,
                 "hint": "controles y responsables"}]},
        ]},
    },
]


def run():
    db = SessionLocal()
    if db.query(Organization).first():
        print("Ya existe data. Nada que sembrar.")
        return
    org = Organization(name="Innovasoft Colombia", plan="empresarial")
    db.add(org); db.commit(); db.refresh(org)

    user = User(org_id=org.id, name="Ana Torres", email="ana.torres@empresa.com",
                password_hash=hash_password("Demo1234"), role="admin")
    db.add(user)
    for t in TEMPLATES:
        db.add(Template(org_id=org.id, name=t["name"], icon=t["icon"],
                        description=t["description"], schema=t["schema"]))
    db.commit()
    print("✓ Seed completo.")
    print("  Login: ana.torres@empresa.com / Demo1234")
    print(f"  Org: {org.name} · {len(TEMPLATES)} plantillas")


if __name__ == "__main__":
    run()
