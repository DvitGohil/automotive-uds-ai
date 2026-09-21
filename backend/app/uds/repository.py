"""
Persists structured UDS knowledge model entities (Stage 8) through the
existing DiagnosticKnowledgeUnit table (added in Stage 3) — no new table.
unit_type distinguishes entity kind; identifier is the entity's natural key
(service_id / DID / RID / NRC / "service_id:subfunction_id"); content holds
the entity's JSON serialization.
"""
import json

from sqlalchemy.orm import Session

from app.db.models import DiagnosticKnowledgeUnit
from app.uds.knowledge_model import UdsDid, UdsNrc, UdsRid, UdsService

_ENTITY_TYPES = {
    "service": UdsService,
    "did": UdsDid,
    "rid": UdsRid,
    "nrc": UdsNrc,
}


def save_uds_entity(
    db: Session,
    document_version_id: str,
    unit_type: str,
    identifier: str,
    entity,
) -> DiagnosticKnowledgeUnit:
    if unit_type not in _ENTITY_TYPES:
        raise ValueError(f"Unknown UDS entity type: {unit_type!r}. Supported: {sorted(_ENTITY_TYPES)}")

    title = getattr(entity, "service_name", None) or getattr(entity, "name", None) or getattr(
        entity, "nrc_name", None
    )
    row = DiagnosticKnowledgeUnit(
        document_version_id=document_version_id,
        unit_type=unit_type,
        identifier=identifier,
        title=title,
        content=json.dumps(entity.to_dict()),
        source_page=entity.source.page_number if entity.source else None,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def load_uds_entity(db: Session, document_version_id: str, unit_type: str, identifier: str):
    if unit_type not in _ENTITY_TYPES:
        raise ValueError(f"Unknown UDS entity type: {unit_type!r}. Supported: {sorted(_ENTITY_TYPES)}")

    row = (
        db.query(DiagnosticKnowledgeUnit)
        .filter(
            DiagnosticKnowledgeUnit.document_version_id == document_version_id,
            DiagnosticKnowledgeUnit.unit_type == unit_type,
            DiagnosticKnowledgeUnit.identifier == identifier,
        )
        .first()
    )
    if row is None:
        return None
    entity_cls = _ENTITY_TYPES[unit_type]
    return entity_cls.from_dict(json.loads(row.content))
