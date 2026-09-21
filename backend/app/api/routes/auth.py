from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.auth import create_access_token, hash_password, verify_password
from app.core.security import get_current_user
from app.db.database import get_db
from app.db.models import User

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterIn(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    full_name: str = Field(max_length=255)
    password: str = Field(min_length=8, max_length=200)


class LoginIn(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(max_length=200)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    email: str


@router.post("/register", response_model=TokenOut)
def register(payload: RegisterIn, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing is not None:
        raise HTTPException(status_code=409, detail="A user with this email already exists")

    user = User(email=payload.email, full_name=payload.full_name, password_hash=hash_password(payload.password))
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(user.id, user.email)
    return TokenOut(access_token=token, user_id=user.id, email=user.email)


@router.post("/login", response_model=TokenOut)
def login(payload: LoginIn, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if user is None or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_access_token(user.id, user.email)
    return TokenOut(access_token=token, user_id=user.id, email=user.email)


@router.post("/logout")
def logout():
    """
    JWTs are stateless and self-expiring (JWT_EXPIRE_MINUTES); there is no
    server-side session/token-blocklist table in this project's architecture
    to revoke a token early. The client is responsible for discarding the
    token. This endpoint exists for a consistent frontend logout flow and to
    document that behavior explicitly, rather than implying a security
    guarantee this stateless setup doesn't provide.
    """
    return {"detail": "Logged out. Discard the access token client-side; it will also expire naturally."}


@router.get("/me")
def me(current_user: User | None = Depends(get_current_user)):
    if current_user is None:
        return {"authenticated": False}
    return {
        "authenticated": True,
        "id": current_user.id,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "role": current_user.role,
    }
