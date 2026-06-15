from datetime import datetime, timezone
from collections import defaultdict
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.models.models import User, Organization
from app.core.security import verify_password, create_access_token, hash_password
from app.schemas.schemas import TokenOut, RegisterIn
from app.api.deps import get_current_user

router = APIRouter(prefix="/api/auth", tags=["auth"])

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
