import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.db.models import Document, DocumentChunk, DocumentVersion, Project, SegmentType
from app.rag.embeddings import EmbeddingProviderError, HashEmbeddingProvider, get_embedding_provider
from app.rag.indexing_service import index_document_version
from app.rag.vector_store import VectorRecord, VectorStoreError, get_vector_store

engine = create_engine("sqlite:///:memory:")
TestingSession = sessionmaker(bind=engine)


def setup_module(_module):
    Base.metadata.create_all(bind=engine)


# --- embedding generation -------------------------------------------------

def test_hash_embedding_is_deterministic_and_correct_dimension():
    provider = HashEmbeddingProvider(dimension=64)
    v1 = provider.embed(["Diagnostic session control"])[0]
    v2 = provider.embed(["Diagnostic session control"])[0]
    assert len(v1) == 64
    assert v1 == v2


def test_hash_embedding_multiple_chunks_batch():
    provider = HashEmbeddingProvider(dimension=32)
    vectors = provider.embed(["chunk one", "chunk two", "chunk three"])
    assert len(vectors) == 3
    assert all(len(v) == 32 for v in vectors)
    assert vectors[0] != vectors[1]  # different text -> different vector


def test_get_embedding_provider_unknown_raises(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "EMBEDDING_PROVIDER", "not_a_real_provider")
    with pytest.raises(EmbeddingProviderError):
        get_embedding_provider()


# --- vector store: indexing, metadata, dedup, errors ----------------------

def _provider():
    return HashEmbeddingProvider(dimension=16)


def test_vector_store_indexing_and_search(tmp_path):
    provider = _provider()
    from app.rag.vector_store import VectorStore

    store = VectorStore(collection_name="test-collection", dimension=16, base_path=str(tmp_path))
    records = [
        VectorRecord(
            id="chunk-1",
            vector=provider.embed(["Diagnostic session control request"])[0],
            content_hash="hash-1",
            metadata={"document_name": "Spec A", "page_number": 1, "section_title": "3.2", "chunk_id": "chunk-1"},
        ),
        VectorRecord(
            id="chunk-2",
            vector=provider.embed(["Unrelated content about tyres"])[0],
            content_hash="hash-2",
            metadata={"document_name": "Spec A", "page_number": 5, "section_title": "9.1", "chunk_id": "chunk-2"},
        ),
    ]
    summary = store.upsert(records)
    assert summary.added == 2
    assert summary.updated == 0
    assert summary.skipped == 0
    assert store.count() == 2

    query_vector = provider.embed(["Diagnostic session control request"])[0]
    results = store.search(query_vector, top_k=1)
    assert len(results) == 1
    assert results[0].id == "chunk-1"
    assert results[0].metadata["document_name"] == "Spec A"
    assert results[0].metadata["section_title"] == "3.2"


def test_vector_store_duplicate_upsert_is_skipped(tmp_path):
    from app.rag.vector_store import VectorStore

    provider = _provider()
    store = VectorStore(collection_name="dedup-test", dimension=16, base_path=str(tmp_path))
    record = VectorRecord(id="chunk-1", vector=provider.embed(["some text"])[0], content_hash="hash-1", metadata={})

    first = store.upsert([record])
    second = store.upsert([record])  # identical content_hash -> should skip, not duplicate

    assert first.added == 1
    assert second.skipped == 1
    assert second.added == 0
    assert store.count() == 1


def test_vector_store_reindexing_updates_changed_content(tmp_path):
    from app.rag.vector_store import VectorStore

    provider = _provider()
    store = VectorStore(collection_name="reindex-test", dimension=16, base_path=str(tmp_path))

    v1 = VectorRecord(id="chunk-1", vector=provider.embed(["original text"])[0], content_hash="hash-v1", metadata={"v": 1})
    store.upsert([v1])

    v2 = VectorRecord(id="chunk-1", vector=provider.embed(["updated text"])[0], content_hash="hash-v2", metadata={"v": 2})
    summary = store.upsert([v2])

    assert summary.updated == 1
    assert summary.added == 0
    assert store.count() == 1  # still one entry, not two

    results = store.search(provider.embed(["updated text"])[0], top_k=1)
    assert results[0].metadata["v"] == 2


def test_vector_store_dimension_mismatch_raises(tmp_path):
    from app.rag.vector_store import VectorStore

    store = VectorStore(collection_name="dim-test", dimension=16, base_path=str(tmp_path))
    bad_record = VectorRecord(id="x", vector=[0.1, 0.2, 0.3], content_hash="h", metadata={})
    with pytest.raises(VectorStoreError):
        store.upsert([bad_record])


def test_vector_store_search_on_empty_store_returns_no_results(tmp_path):
    from app.rag.vector_store import VectorStore

    store = VectorStore(collection_name="empty-test", dimension=16, base_path=str(tmp_path))
    provider = _provider()
    results = store.search(provider.embed(["anything"])[0], top_k=5)
    assert results == []


def test_vector_store_persists_across_reload(tmp_path):
    from app.rag.vector_store import VectorStore

    provider = _provider()
    store = VectorStore(collection_name="persist-test", dimension=16, base_path=str(tmp_path))
    store.upsert([VectorRecord(id="chunk-1", vector=provider.embed(["persisted text"])[0], content_hash="h1", metadata={"k": "v"})])

    reloaded = VectorStore(collection_name="persist-test", dimension=16, base_path=str(tmp_path))
    assert reloaded.count() == 1
    results = reloaded.search(provider.embed(["persisted text"])[0], top_k=1)
    assert results[0].metadata["k"] == "v"


# --- indexing_service: DB chunks -> embeddings -> vector store ------------

def _seed_document_with_chunks(db):
    project = Project(name="Pilot")
    db.add(project)
    db.flush()

    document = Document(project_id=project.id, title="ISO 14229 Extract", source_type="uds_spec")
    db.add(document)
    db.flush()

    version = DocumentVersion(document_id=document.id, version_number=1, file_path="/tmp/spec.txt")
    db.add(version)
    db.flush()

    chunk1 = DocumentChunk(
        document_id=document.id,
        document_version_id=version.id,
        chunk_index=0,
        page_number=3,
        section_title="3.2 Diagnostic Session Control",
        chunk_type=SegmentType.TEXT,
        content="The tester shall request the default session before diagnostics.",
        content_hash="hash-a",
        char_count=64,
    )
    db.add(chunk1)
    db.commit()
    return project, document, version, chunk1


def test_index_document_version_persists_metadata(tmp_path, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "VECTOR_DB_PATH", str(tmp_path))
    db = TestingSession()
    try:
        project, document, version, chunk = _seed_document_with_chunks(db)
        summary = index_document_version(db, version.id, embedding_provider=HashEmbeddingProvider(dimension=32))
        assert summary.added == 1

        store = get_vector_store(collection_name=f"project-{project.id}", dimension=32)
        results = store.search(HashEmbeddingProvider(dimension=32).embed([chunk.content])[0], top_k=1)
        assert len(results) == 1
        meta = results[0].metadata
        assert meta["document_id"] == document.id
        assert meta["document_name"] == "ISO 14229 Extract"
        assert meta["document_version"] == 1
        assert meta["page_number"] == 3
        assert meta["section_title"] == "3.2 Diagnostic Session Control"
        assert meta["chunk_id"] == chunk.id
        assert meta["source_text"] == chunk.content
    finally:
        db.close()


def test_index_document_version_reprocessing_does_not_duplicate(tmp_path, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "VECTOR_DB_PATH", str(tmp_path))
    db = TestingSession()
    try:
        project, document, version, chunk = _seed_document_with_chunks(db)
        provider = HashEmbeddingProvider(dimension=32)
        index_document_version(db, version.id, embedding_provider=provider)
        second = index_document_version(db, version.id, embedding_provider=provider)

        assert second.skipped == 1
        assert second.added == 0
        store = get_vector_store(collection_name=f"project-{project.id}", dimension=32)
        assert store.count() == 1
    finally:
        db.close()


def test_index_document_version_missing_version_raises(tmp_path, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "VECTOR_DB_PATH", str(tmp_path))
    db = TestingSession()
    try:
        with pytest.raises(ValueError):
            index_document_version(db, "does-not-exist")
    finally:
        db.close()


def test_index_document_version_no_chunks_is_noop(tmp_path, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "VECTOR_DB_PATH", str(tmp_path))
    db = TestingSession()
    try:
        project = Project(name="Empty Project")
        db.add(project)
        db.flush()
        document = Document(project_id=project.id, title="Empty Doc", source_type="uds_spec")
        db.add(document)
        db.flush()
        version = DocumentVersion(document_id=document.id, version_number=1, file_path="/tmp/empty.txt")
        db.add(version)
        db.commit()

        summary = index_document_version(db, version.id, embedding_provider=HashEmbeddingProvider(dimension=16))
        assert summary.added == 0
        assert summary.updated == 0
        assert summary.skipped == 0
    finally:
        db.close()
