import json
import secrets
import urllib.parse
from datetime import datetime, timezone
from collections import defaultdict
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.models.models import User, Organization
from app.core.security import verify_password, create_access_token, hash_password
from app.core.config import get_settings
from app.schemas.schemas import TokenOut, RegisterIn
from app.api.deps import get_current_user

router = APIRouter(prefix="/api/auth", tags=["auth"])
settings = get_settings()

# Rate limiting simple en memoria: {ip: [timestamps]}
_login_attempts: dict[str, list] = defaultdict(list)
MAX_ATTEMPTS = 5
WINDOW_SECONDS = 60


def _check_rate_limit(ip: str):
    now = datetime.now(timezone.utc).timestamp()
    attempts = [t for t in _login_attempts[ip] if now - t < WINDOW_SECONDS]
    _login_attempts[ip] = attempts
    if len(attempts) >= MAX_ATTEMPTS:
        raise HTTPException(429, f"Demasiados intentos. Espera {WINDOW_SECONDS} segundos.")
    _login_attempts[ip].append(now)


@router.post("/login", response_model=TokenOut)
def login(request: Request, form: OAuth2PasswordRequestForm = Depends(),
          db: Session = Depends(get_db)):
    ip = request.client.host
    _check_rate_limit(ip)
    user = db.query(User).filter(User.email == form.username).first()
    if not user or not verify_password(form.password, user.password_hash):
        raise HTTPException(401, "Correo o contraseña incorrectos")
    # Login exitoso — limpia intentos
    _login_attempts.pop(ip, None)
    token = create_access_token(user.id, {"org": user.org_id, "role": user.role})
    org = db.get(Organization, user.org_id)
    return TokenOut(
        access_token=token,
        user={"id": user.id, "name": user.name, "email": user.email,
              "role": user.role, "org_name": org.name if org else ""},
    )


@router.post("/register", response_model=TokenOut)
def register(body: RegisterIn, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == body.email).first():
        raise HTTPException(400, "Ya existe una cuenta con ese correo")
    org = Organization(name=body.org_name.strip() or body.name)
    db.add(org); db.flush()
    user = User(
        org_id=org.id,
        name=body.name,
        email=body.email,
        password_hash=hash_password(body.password),
        role="admin",
    )
    db.add(user); db.commit(); db.refresh(user)
    token = create_access_token(user.id, {"org": user.org_id, "role": user.role})
    return TokenOut(
        access_token=token,
        user={"id": user.id, "name": user.name, "email": user.email,
              "role": user.role, "org_name": org.name},
    )


@router.get("/me")
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org = db.get(Organization, user.org_id)
    return {"id": user.id, "name": user.name, "email": user.email,
            "role": user.role, "org_id": user.org_id,
            "org_name": org.name if org else ""}


# ── Configuración de auth (para que el frontend sepa qué modo usar) ──────────

@router.get("/config")
def auth_config():
    """El frontend llama esto al cargar para saber si usar Zitadel o login local."""
    return {
        "mode": "zitadel" if settings.ZITADEL_DOMAIN else "local",
    }


# ── Zitadel SSO ───────────────────────────────────────────────────────────────

@router.get("/zitadel/login")
def zitadel_login(request: Request, redirect: str = ""):
    """Inicia el flujo PKCE hacia Zitadel.
    'redirect' es la URL del frontend a donde volver tras el login.
    """
    if not settings.ZITADEL_DOMAIN:
        raise HTTPException(400, "Zitadel no está configurado")
    from app.core.zitadel import create_pkce_pair, build_auth_url, save_state
    state = secrets.token_urlsafe(16)
    verifier, challenge = create_pkce_pair()
    # El callback siempre va al backend primero
    base = str(request.base_url).rstrip("/")
    callback_uri = f"{base}/api/auth/zitadel/callback"
    # Guardamos adónde redirigir al frontend después
    frontend_redirect = redirect or f"{base.replace(':8000', ':5500')}/"
    save_state(state, verifier, frontend_redirect)
    auth_url = build_auth_url(state, challenge, callback_uri)
    return RedirectResponse(auth_url, status_code=302)


@router.get("/zitadel/callback")
def zitadel_callback(
    request: Request,
    code: str,
    state: str,
    db: Session = Depends(get_db),
):
    """Recibe el código de Zitadel, lo valida, crea/sincroniza el usuario
    y redirige al frontend con el JWT local en la URL."""
    if not settings.ZITADEL_DOMAIN:
        raise HTTPException(400, "Zitadel no está configurado")

    from app.core.zitadel import pop_state, exchange_code, validate_id_token

    state_data = pop_state(state)
    if not state_data:
        raise HTTPException(400, "Estado inválido o expirado. Intenta de nuevo.")

    base = str(request.base_url).rstrip("/")
    callback_uri = f"{base}/api/auth/zitadel/callback"

    try:
        tokens = exchange_code(code, state_data["code_verifier"], callback_uri)
        claims = validate_id_token(tokens["id_token"])
    except Exception as exc:
        raise HTTPException(502, f"Error validando token de Zitadel: {exc}")

    email = claims.get("email", "")
    name = claims.get("name") or claims.get("preferred_username") or email
    org_name_claim = (
        claims.get("org_name")
        or claims.get("urn:zitadel:iam:org:name")
        or ""
    )

    # Buscar o crear usuario local (sin password — solo SSO)
    user = db.query(User).filter(User.email == email).first()
    if not user:
        org = Organization(name=org_name_claim or name)
        db.add(org)
        db.flush()
        user = User(
            org_id=org.id,
            name=name,
            email=email,
            password_hash="",  # sin contraseña local
            role="editor",
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    # Emitir JWT local (mismo formato que login normal)
    token = create_access_token(user.id, {"org": user.org_id, "role": user.role})
    org = db.get(Organization, user.org_id)
    user_json = json.dumps({
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "org_name": org.name if org else "",
    })

    # Redirigir al frontend con token en query string
    params = urllib.parse.urlencode({"token": token, "user": user_json})
    frontend_redirect = state_data["frontend_redirect"]
    return RedirectResponse(f"{frontend_redirect}?{params}", status_code=302)
