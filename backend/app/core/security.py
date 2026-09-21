from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.core.auth import decode_access_token
from app.core.config import settings
from app.db.database import get_db
from app.db.models import ProjectMember, User


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    """
    Enforces the X-API-Key header when settings.API_KEY is configured.
    Auth is disabled (dev default) when API_KEY is empty, matching the
    project's existing "no unnecessary infrastructure" pilot posture.
    Coarse-grained gate only — identity/authorization is handled separately
    by get_current_user / check_project_access below.
    """
    if not settings.API_KEY:
        return
    if x_api_key != settings.API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


def get_current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User | None:
    """
    Resolves the caller's identity from a verified JWT (Authorization: Bearer
    <token>), issued only by POST /auth/login. Unlike the previous X-User-Id
    header, this cannot be spoofed by the client — the token is signed
    server-side and its claims are cryptographically verified.

    Returns None (not an error) when JWT_SECRET isn't configured (dev/pilot
    mode, auth disabled), matching the project's existing on/off posture.
    Raises 401 for a missing/invalid/expired token whenever JWT_SECRET IS
    configured, since a caller in that mode is expected to authenticate.
    """
    if not settings.JWT_SECRET:
        return None

    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing or malformed Authorization header")

    token = authorization.split(" ", 1)[1].strip()
    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user = db.query(User).filter(User.id == payload.get("sub")).first()
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")
    return user


def check_project_access(db: Session, project_id: str, user: User | None) -> None:
    """
    Authorization check (IDOR protection): the caller must be a member of the
    project they're trying to access. Tied to the same on/off posture as
    get_current_user — when JWT_SECRET isn't configured (dev/pilot mode),
    this check is skipped too.
    """
    if not settings.JWT_SECRET:
        return
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    member = (
        db.query(ProjectMember)
        .filter(ProjectMember.project_id == project_id, ProjectMember.user_id == user.id)
        .first()
    )
    if member is None:
        raise HTTPException(status_code=403, detail="User is not authorized for this project")


def require_project_access(
    project_id: str,
    current_user: User | None = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    """FastAPI dependency form of check_project_access for routes with project_id as a path param."""
    check_project_access(db, project_id, current_user)
