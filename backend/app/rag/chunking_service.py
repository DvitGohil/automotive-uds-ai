from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import DocumentChunk, DocumentVersion, ExtractedSegment
from app.rag.chunking import ChunkInput, build_chunks


def chunk_document_version(
    db: Session,
    document_version_id: str,
    *,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> list[DocumentChunk]:
    """
    Chunk all ExtractedSegments belonging to a document version and persist
    them as DocumentChunk rows, fully traceable to document/version/page/section
    and the originating segment.

    Reprocessing is idempotent: any existing chunk set for this document
    version is replaced (not appended to), so re-running this on the same or
    an updated version never accumulates duplicate chunks.
    """
    version = db.query(DocumentVersion).filter(DocumentVersion.id == document_version_id).first()
    if version is None:
        raise ValueError(f"DocumentVersion not found: {document_version_id}")

    segments = (
        db.query(ExtractedSegment)
        .filter(ExtractedSegment.document_version_id == document_version_id)
        .order_by(ExtractedSegment.page_number)
        .all()
    )

    inputs = [
        ChunkInput(
            segment_id=s.id,
            document_id=version.document_id,
            document_version_id=document_version_id,
            page_number=s.page_number,
            section_title=s.section_title,
            segment_type=s.segment_type.value if hasattr(s.segment_type, "value") else s.segment_type,
            content=s.content,
        )
        for s in segments
    ]

    size = chunk_size if chunk_size is not None else settings.CHUNK_SIZE
    overlap = chunk_overlap if chunk_overlap is not None else settings.CHUNK_OVERLAP
    built = build_chunks(inputs, chunk_size=size, chunk_overlap=overlap)

    # Idempotent replace: clear this version's existing chunks before inserting the new set.
    db.query(DocumentChunk).filter(DocumentChunk.document_version_id == document_version_id).delete()
    db.flush()

    rows: list[DocumentChunk] = []
    for chunk in built:
        row = DocumentChunk(
            document_id=version.document_id,
            document_version_id=document_version_id,
            extracted_segment_id=chunk.segment_id,
            chunk_index=chunk.chunk_index,
            page_number=chunk.page_number,
            section_title=chunk.section_title,
            chunk_type=chunk.chunk_type,
            content=chunk.content,
            content_hash=chunk.content_hash,
            char_count=chunk.char_count,
        )
        db.add(row)
        rows.append(row)

    db.commit()
    for row in rows:
        db.refresh(row)
    return rows
