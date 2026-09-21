"""Audit logging, reusing the existing AuditRecord table (no new schema)."""
import json

from sqlalchemy.orm import Session

from app.db.models import AuditRecord


def log_action(
    db: Session,
    *,
    action: str,
    project_id: str | None = None,
    user_id: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    details: dict | None = None,
) -> AuditRecord:
    row = AuditRecord(
        project_id=project_id,
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=json.dumps(details) if details is not None else None,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row
