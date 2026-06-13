# ActaIA — Generación inteligente de actas de reunión

Plataforma empresarial que convierte transcripciones (TXT/DOCX/PDF o texto pegado)
en actas estructuradas usando IA, con **plantillas configurables sin código**,
**trazabilidad a la fuente**, **detección de campos faltantes**, **flujo de
aprobación** y **auditoría**.

Stack: **FastAPI + SQLAlchemy + JWT** (backend) · **HTML/JS sin build** (frontend)
· **Anthropic** (IA, con fallback determinístico para probar sin API key).

---

## Arranque rápido (3 comandos)

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env            # AI_PROVIDER=mock funciona sin credenciales
python -m app.seed              # crea BD + usuario demo + 3 plantillas
uvicorn app.main:app --reload   # API en http://localhost:8000  (docs: /docs)
```

Frontend: abre `frontend/index.html` en el navegador (apunta a `localhost:8000`).

**Usuario demo:** `ana.torres@empresa.com` / `Demo1234`

### Activar IA real
En `.env`: `AI_PROVIDER=anthropic` y `ANTHROPIC_API_KEY=sk-ant-...`.
El servicio arma un *prompt dinámico* desde el schema de la plantilla y exige
salida JSON estructurada con `value / confidence / source` por campo.

---

## Flujo de 3 pasos (igual que el producto)
1. **Cargar transcripción** — subir archivo o pegar texto (con historial de versiones).
2. **Seleccionar plantilla** — define qué secciones/campos se extraen.
3. **Generar y revisar** — la IA completa el acta; cada campo muestra confianza y
   la cita de origen; los campos obligatorios sin evidencia se marcan como
   faltantes y bloquean la aprobación hasta validarse.

---

## Estructura

```
backend/
  app/
    main.py              # FastAPI: monta routers, CORS, crea tablas
    core/config.py       # settings desde entorno (.env / Secret Manager)
    core/security.py     # bcrypt + JWT
    db/database.py       # SQLAlchemy (SQLite dev → Postgres prod)
    models/models.py     # Organization, User, Template, Transcript(+Version), Acta, AuditLog
    schemas/schemas.py   # contratos Pydantic
    services/ai_service.py  # prompt dinámico + JSON estructurado + anti-alucinación + scoring
    services/files.py    # extracción TXT/DOCX/PDF
    api/                 # auth, templates, transcripts, actas (fronteras listas para microservicios)
    seed.py              # datos demo
  test_smoke.py          # prueba E2E (python test_smoke.py)
frontend/
  index.html             # SPA conectada por fetch a la API
```

## API principal
| Método | Ruta | Descripción |
|---|---|---|
| POST | `/api/auth/login` | Login (OAuth2 password) → JWT |
| GET  | `/api/templates` | Listar plantillas |
| POST | `/api/templates` | **Crear plantilla nueva (sin código)** |
| POST | `/api/transcripts` | Crear transcripción desde texto |
| POST | `/api/transcripts/upload` | Subir TXT/DOCX/PDF |
| PUT  | `/api/transcripts/{id}` | Editar → nueva versión |
| POST | `/api/actas/generate` | **Generar acta con IA** |
| PATCH| `/api/actas/{id}/field` | Validar/editar un campo |
| POST | `/api/actas/{id}/approve` | Aprobar (bloquea si faltan obligatorios) |
| GET  | `/api/actas/{id}/audit` | Registro de auditoría |

## Plantillas configurables sin código
Una plantilla es solo datos: `schema = {"sections":[{"key","title","fields":[
{"key","label","type","required","hint"}]}]}`. Agregar una plantilla nueva =
`POST /api/templates`. La IA se adapta automáticamente porque el prompt se
construye desde ese schema.

## Pasar a producción
- `DATABASE_URL` → PostgreSQL.
- Secretos desde Secret Manager (mismo `Settings`).
- Frontend a Vite/React si se quiere build; el contrato de API no cambia.
- Cada router/servicio ya está desacoplado para extraerlo como microservicio.

> Nota: el warning de Pydantic sobre el campo `schema` es cosmético (la API
> funciona); puede silenciarse con un alias de campo si se prefiere.
