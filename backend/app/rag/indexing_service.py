from sqlalchemy.orm import Session

from app.db.models import Document, DocumentChunk, DocumentVersion
from app.rag.collections import collection_name_for_project
from app.rag.embeddings import EmbeddingProvider, get_embedding_provider
from app.rag.vector_store import UpsertSummary, VectorRecord, get_vector_store


def _collection_name_for_project(project_id: str) -> str:
    # Kept as a thin alias for backward compatibility with existing imports.
    return collection_name_for_project(project_id)


def index_document_version(
    db: Session,
    document_version_id: str,
    *,
    embedding_provider: EmbeddingProvider | None = None,
) -> UpsertSummary:
    """
    Embed and index all DocumentChunk rows for a document version into that
    project's local vector store collection. Upsert-by-chunk-id with a
    content-hash check: unchanged chunks are skipped (no duplicate indexing);
    changed chunks (e.g. after re-chunking a new document version) update the
    existing vector in place.
    """
    version = db.query(DocumentVersion).filter(DocumentVersion.id == document_version_id).first()
    if version is None:
        raise ValueError(f"DocumentVersion not found: {document_version_id}")

    document = db.query(Document).filter(Document.id == version.document_id).first()
    if document is None:
        raise ValueError(f"Document not found for version: {document_version_id}")

    chunks = (
        db.query(DocumentChunk)
        .filter(DocumentChunk.document_version_id == document_version_id)
        .order_by(DocumentChunk.chunk_index)
        .all()
    )

    provider = embedding_provider or get_embedding_provider()
    store = get_vector_store(
        collection_name=_collection_name_for_project(document.project_id),
        dimension=provider.dimension,
    )

    if not chunks:
        return UpsertSummary()

    vectors = provider.embed([c.content for c in chunks])

    records = [
        VectorRecord(
            id=chunk.id,
            vector=vectors[i],
            content_hash=chunk.content_hash,
            metadata={
                "document_id": document.id,
                "document_name": document.title,
                "document_version": version.version_number,
                "page_number": chunk.page_number,
                "section_title": chunk.section_title,
                "chunk_id": chunk.id,
                "source_text": chunk.content,
            },
        )
        for i, chunk in enumerate(chunks)
    ]

    return store.upsert(records)
