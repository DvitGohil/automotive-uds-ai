import hashlib
import json
import shutil
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Document, DocumentStatus, DocumentVersion, ExtractedSegment
from app.ingestion.extractors import SUPPORTED_EXTENSIONS, extract


def _hash_file(file_path: str) -> str:
    digest = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _storage_path_for(document_id: str, version_number: int, original_filename: str) -> Path:
    storage_root = Path(settings.DOCUMENT_STORAGE_PATH)
    target_dir = storage_root / document_id
    target_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(original_filename).suffix.lower()
    return target_dir / f"v{version_number}{suffix}"


def ingest_document(
    db: Session,
    *,
    project_id: str,
    title: str,
    source_type: str,
    original_file_path: str,
    original_filename: str,
    is_approved: bool = False,
    uploaded_by: str | None = None,
) -> Document:
    """
    Create a Document from an uploaded file, extract its content, and persist
    fully traceable ExtractedSegment rows (Document -> Version -> Page ->
    Section). Does not touch embeddings or run any LLM step.
    """
    suffix = Path(original_filename).suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported document format: {suffix}. Supported: {sorted(SUPPORTED_EXTENSIONS)}")

    document = Document(
        project_id=project_id,
        title=title,
        source_type=source_type,
        status=DocumentStatus.PROCESSING,
        is_approved=is_approved,
        uploaded_by=uploaded_by,
    )
    db.add(document)
    db.flush()  # assigns document.id

    stored_path = _storage_path_for(document.id, version_number=1, original_filename=original_filename)
    shutil.copyfile(original_file_path, stored_path)

    version = DocumentVersion(
        document_id=document.id,
        version_number=1,
        file_path=str(stored_path),
        file_hash=_hash_file(str(stored_path)),
    )
    db.add(version)
    db.flush()  # assigns version.id

    try:
        units = extract(str(stored_path))
    except Exception:
        document.status = DocumentStatus.FAILED
        db.commit()
        raise

    for unit in units:
        db.add(
            ExtractedSegment(
                document_version_id=version.id,
                page_number=unit.page_number,
                section_title=unit.section_title,
                segment_type=unit.segment_type,
                content=unit.content,
                extra_metadata=json.dumps(unit.metadata) if unit.metadata else None,
            )
        )

    version.extracted_text_path = str(stored_path)
    document.status = DocumentStatus.INGESTED
    db.commit()
    db.refresh(document)
    return document
