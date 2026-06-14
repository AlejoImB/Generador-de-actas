from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.models.models import User, Organization
from app.core.security import verify_password, create_access_token, hash_password
from app.schemas.schemas import TokenOut, RegisterIn
from app.api.deps import get_current_user

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenOut)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == form.username).first()
    if not user or not verify_password(form.password, user.password_hash):
        raise HTTPException(401, "Correo o contraseña incorrectos")
    token = create_access_token(user.id, {"org": user.org_id, "role": user.role})
    return TokenOut(
        access_token=token,
        user={"id": user.id, "name": user.name, "email": user.email, "role": user.role},
    )


@router.post("/register", response_model=TokenOut)
def register(body: RegisterIn, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == body.email).first():
        raise HTTPException(400, "Ya existe una cuenta con ese correo")
    org = Organization(name=body.org_name or body.name)
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
        user={"id": user.id, "name": user.name, "email": user.email, "role": user.role},
    )


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return {"id": user.id, "name": user.name, "email": user.email, "role": user.role,
            "org_id": user.org_id}
