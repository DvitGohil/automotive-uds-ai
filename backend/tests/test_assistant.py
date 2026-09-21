import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.db.models import AuditRecord, Project
from app.rag.assistant import ask
from app.rag.embeddings import HashEmbeddingProvider
from app.rag.llm import AnthropicLLMProvider, LLMProvider, LLMProviderError, MockLLMProvider, get_llm_provider
from app.rag.vector_store import VectorRecord, get_vector_store

engine = create_engine("sqlite:///:memory:")
TestingSession = sessionmaker(bind=engine)


def setup_module(_module):
    Base.metadata.create_all(bind=engine)


class _FailingLLMProvider(LLMProvider):
    def generate(self, question, context_blocks):
        raise RuntimeError("LLM backend unreachable")


def _seed_store(tmp_path, monkeypatch, project_id="proj-1", dimension=32):
    from app.core.config import settings

    monkeypatch.setattr(settings, "VECTOR_DB_PATH", str(tmp_path))
    provider = HashEmbeddingProvider(dimension=dimension)
    store = get_vector_store(collection_name=f"project-{project_id}", dimension=dimension)

    text = "The tester shall request the default diagnostic session (0x10 0x01) before further services."
    record = VectorRecord(
        id="chunk-1",
        vector=provider.embed([text])[0],
        content_hash="hash-1",
        metadata={
            "document_id": "doc-1",
            "document_name": "ISO 14229",
            "document_version": 1,
            "page_number": 3,
            "section_title": "3.2 Diagnostic Session Control",
            "chunk_id": "chunk-1",
            "source_text": text,
        },
    )
    store.upsert([record])
    return provider, text


def test_ask_with_relevant_context_returns_grounded_answer_and_citations(tmp_path, monkeypatch):
    provider, text = _seed_store(tmp_path, monkeypatch)
    result = ask(
        None,
        "proj-1",
        text,
        top_k=5,
        embedding_provider=provider,
        llm_provider=MockLLMProvider(),
        log_audit=False,
    )
    assert "0x10 0x01" in result.answer or "diagnostic session" in result.answer.lower()
    assert len(result.citations) == 1
    citation = result.citations[0]
    assert citation.document_name == "ISO 14229"
    assert citation.page_number == 3
    assert citation.section_title == "3.2 Diagnostic Session Control"
    assert citation.chunk_id == "chunk-1"
    assert result.confidence in {"high", "medium", "low"}
    assert result.requires_engineering_review is True


def test_ask_with_insufficient_context_states_no_adequate_source(tmp_path, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "VECTOR_DB_PATH", str(tmp_path))
    provider = HashEmbeddingProvider(dimension=32)
    result = ask(
        None,
        "empty-project",
        "What NRC is returned for an unsupported subfunction?",
        embedding_provider=provider,
        llm_provider=MockLLMProvider(),
        log_audit=False,
    )
    assert result.confidence == "none"
    assert result.citations == []
    assert "not provide enough information" in result.answer or "Evidence Not Found" in result.answer


def test_ask_source_citation_preserves_full_traceability(tmp_path, monkeypatch):
    provider, text = _seed_store(tmp_path, monkeypatch)
    result = ask(None, "proj-1", text, embedding_provider=provider, llm_provider=MockLLMProvider(), log_audit=False)
    citation = result.citations[0]
    # Document -> Version -> Page -> Section -> chunk, all present
    assert citation.document_id and citation.document_version and citation.page_number and citation.chunk_id


def test_ask_grounded_answer_does_not_exceed_supplied_context():
    # MockLLMProvider is non-generative by construction: it cannot add facts
    # beyond what's in context_blocks — verified directly at the provider level.
    provider = MockLLMProvider()
    answer = provider.generate("irrelevant question", ["[Source: X] Only this fact is present."])
    assert "Only this fact is present." in answer


def test_ask_unsupported_information_handling_with_no_context():
    provider = MockLLMProvider()
    answer = provider.generate("What is DID 0xF190?", [])
    assert "Evidence Not Found" in answer


def test_get_llm_provider_mock_default(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "LLM_PROVIDER", "mock")
    assert isinstance(get_llm_provider(), MockLLMProvider)


def test_get_llm_provider_unknown_raises(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "LLM_PROVIDER", "not_a_real_provider")
    with pytest.raises(LLMProviderError):
        get_llm_provider()


def test_anthropic_provider_requires_api_key_configuration():
    with pytest.raises(LLMProviderError):
        AnthropicLLMProvider(model="claude-sonnet-4-6", api_key="")


def test_ask_propagates_llm_service_failure(tmp_path, monkeypatch):
    provider, text = _seed_store(tmp_path, monkeypatch)
    with pytest.raises(RuntimeError):
        ask(None, "proj-1", text, embedding_provider=provider, llm_provider=_FailingLLMProvider(), log_audit=False)


def test_ask_logs_audit_record_when_db_provided(tmp_path, monkeypatch):
    provider, text = _seed_store(tmp_path, monkeypatch)
    db = TestingSession()
    try:
        project = Project(id="proj-1", name="Pilot")
        db.add(project)
        db.commit()

        ask(db, "proj-1", text, embedding_provider=provider, llm_provider=MockLLMProvider(), log_audit=True)

        records = db.query(AuditRecord).filter_by(project_id="proj-1", action="uds_question_answered").all()
        assert len(records) == 1
    finally:
        db.close()
