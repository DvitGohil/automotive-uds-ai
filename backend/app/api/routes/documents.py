import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.security import require_api_key
from app.db.database import get_db
from app.db.models import Document, ExtractedSegment
from app.ingestion.extractors import SUPPORTED_EXTENSIONS
from app.ingestion.service import ingest_document

router = APIRouter(prefix="/documents", tags=["documents"], dependencies=[Depends(require_api_key)])


@router.post("/ingest")
async def ingest(
    project_id: str = Form(...),
    title: str = Form(...),
    source_type: str = Form(...),
    is_approved: bool = Form(False),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    suffix = Path(file.filename).suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported document format: {suffix}. Supported: {sorted(SUPPORTED_EXTENSIONS)}",
        )

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        document = ingest_document(
            db,
            project_id=project_id,
            title=title,
            source_type=source_type,
            original_file_path=tmp_path,
            original_filename=file.filename,
            is_approved=is_approved,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    return {
        "document_id": document.id,
        "title": document.title,
        "status": document.status,
        "is_approved": document.is_approved,
    }


@router.get("/{document_id}/segments")
def list_segments(document_id: str, db: Session = Depends(get_db)):
    document = db.query(Document).filter(Document.id == document_id).first()
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")

    segments = (
        db.query(ExtractedSegment)
        .join(ExtractedSegment.document_version)
        .filter(ExtractedSegment.document_version.has(document_id=document_id))
        .order_by(ExtractedSegment.page_number)
        .all()
    )

    return {
        "document": {"id": document.id, "title": document.title, "status": document.status},
        "segments": [
            {
                "id": s.id,
                "document_version_id": s.document_version_id,
                "page_number": s.page_number,
                "section_title": s.section_title,
                "segment_type": s.segment_type,
                "content": s.content,
                "metadata": s.extra_metadata,
            }
            for s in segments
        ],
    }
