import pytest

from app.rag.embeddings import HashEmbeddingProvider
from app.rag.retrieval import retrieve
from app.rag.vector_store import VectorRecord, get_vector_store


def _seed_store(tmp_path, monkeypatch, project_id="proj-1", dimension=32):
    from app.core.config import settings

    monkeypatch.setattr(settings, "VECTOR_DB_PATH", str(tmp_path))
    provider = HashEmbeddingProvider(dimension=dimension)
    store = get_vector_store(collection_name=f"project-{project_id}", dimension=dimension)

    docs = [
        ("chunk-1", "The tester shall request the default diagnostic session before further services.",
         {"document_id": "doc-1", "document_name": "ISO 14229", "document_version": 1,
          "page_number": 3, "section_title": "3.2 Diagnostic Session Control", "chunk_id": "chunk-1"}),
        ("chunk-2", "Security access requires a seed and key exchange sequence.",
         {"document_id": "doc-1", "document_name": "ISO 14229", "document_version": 1,
          "page_number": 4, "section_title": "3.3 Security Access", "chunk_id": "chunk-2"}),
        ("chunk-3", "Routine control supports start, stop, and request results subfunctions.",
         {"document_id": "doc-1", "document_name": "ISO 14229", "document_version": 1,
          "page_number": 6, "section_title": "3.5 RoutineControl", "chunk_id": "chunk-3"}),
    ]
    records = []
    for chunk_id, text, meta in docs:
        vector = provider.embed([text])[0]
        records.append(VectorRecord(id=chunk_id, vector=vector, content_hash=chunk_id, metadata={**meta, "source_text": text}))
    store.upsert(records)
    return provider, {c[0]: c[1] for c in docs}


def test_retrieve_relevant_query_returns_matching_chunk(tmp_path, monkeypatch):
    provider, texts = _seed_store(tmp_path, monkeypatch)
    result = retrieve("proj-1", texts["chunk-1"], top_k=5, min_relevance=-1.0, embedding_provider=provider)

    assert result.has_sufficient_context is True
    assert result.chunks[0].chunk_id == "chunk-1"
    assert result.chunks[0].document_name == "ISO 14229"
    assert result.chunks[0].section_title == "3.2 Diagnostic Session Control"


def test_retrieve_multiple_relevant_chunks_ordered_by_relevance(tmp_path, monkeypatch):
    provider, texts = _seed_store(tmp_path, monkeypatch)
    result = retrieve("proj-1", "diagnostic session and security access", top_k=3, min_relevance=-1.0, embedding_provider=provider)
    assert len(result.chunks) >= 1
    scores = [c.relevance_score for c in result.chunks]
    assert scores == sorted(scores, reverse=True)


def test_retrieve_top_k_limits_results(tmp_path, monkeypatch):
    provider, texts = _seed_store(tmp_path, monkeypatch)
    result = retrieve("proj-1", "diagnostic services overview", top_k=2, min_relevance=-1.0, embedding_provider=provider)
    assert len(result.chunks) <= 2


def test_retrieve_metadata_preserved(tmp_path, monkeypatch):
    provider, texts = _seed_store(tmp_path, monkeypatch)
    result = retrieve("proj-1", texts["chunk-2"], top_k=1, min_relevance=-1.0, embedding_provider=provider)
    chunk = result.chunks[0]
    assert chunk.document_id == "doc-1"
    assert chunk.document_version == 1
    assert chunk.page_number == 4
    assert chunk.source_text == texts["chunk-2"]


def test_retrieve_no_result_when_store_empty(tmp_path, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "VECTOR_DB_PATH", str(tmp_path))
    provider = HashEmbeddingProvider(dimension=32)
    result = retrieve("empty-project", "any UDS question", embedding_provider=provider)
    assert result.has_sufficient_context is False
    assert result.chunks == []


def test_retrieve_low_relevance_filtered_out(tmp_path, monkeypatch):
    provider, texts = _seed_store(tmp_path, monkeypatch)
    # Force an unreachable relevance bar so nothing clears the threshold.
    result = retrieve("proj-1", texts["chunk-1"], top_k=5, min_relevance=1.5, embedding_provider=provider)
    assert result.has_sufficient_context is False
    assert result.chunks == []


def test_retrieve_filters_by_project_collection(tmp_path, monkeypatch):
    provider, texts = _seed_store(tmp_path, monkeypatch, project_id="proj-1")
    # A different project has its own empty collection — no cross-project leakage.
    result = retrieve("proj-2", texts["chunk-1"], min_relevance=-1.0, embedding_provider=provider)
    assert result.has_sufficient_context is False
    assert result.chunks == []


def test_retrieve_rejects_empty_query(tmp_path, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "VECTOR_DB_PATH", str(tmp_path))
    with pytest.raises(ValueError):
        retrieve("proj-1", "   ", embedding_provider=HashEmbeddingProvider(dimension=32))
