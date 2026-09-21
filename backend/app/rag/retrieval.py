"""
RAG retrieval: takes a natural-language query, embeds it with the same
provider used for chunk indexing, and searches the project's local vector
store. Returns a clean, fully-traceable result structure for Stage 7 to
consume. Retrieves only from the local, approved-document vector store —
never fetches or invents information from anywhere else.
"""
from dataclasses import dataclass

from app.core.config import settings
from app.rag.collections import collection_name_for_project
from app.rag.embeddings import EmbeddingProvider, get_embedding_provider
from app.rag.vector_store import get_vector_store


@dataclass
class RetrievedChunk:
    chunk_id: str
    document_id: str
    document_name: str
    document_version: int
    page_number: int | None
    section_title: str | None
    source_text: str
    relevance_score: float


@dataclass
class RetrievalResult:
    query: str
    chunks: list[RetrievedChunk]
    has_sufficient_context: bool  # False if nothing met the relevance threshold


def retrieve(
    project_id: str,
    query: str,
    *,
    top_k: int = 5,
    min_relevance: float | None = None,
    embedding_provider: EmbeddingProvider | None = None,
) -> RetrievalResult:
    """
    Retrieve the most relevant approved-document chunks for `query` within
    a single project's collection. `min_relevance` (cosine similarity,
    -1..1) below which a result is dropped — defaults to
    settings.RETRIEVAL_MIN_RELEVANCE. Returns has_sufficient_context=False
    (with an empty chunk list) when no result clears the threshold, so
    Stage 7 can explicitly say "no adequate approved source found" instead
    of guessing.
    """
    if not query or not query.strip():
        raise ValueError("query must not be empty")

    provider = embedding_provider or get_embedding_provider()
    threshold = settings.RETRIEVAL_MIN_RELEVANCE if min_relevance is None else min_relevance

    store = get_vector_store(
        collection_name=collection_name_for_project(project_id),
        dimension=provider.dimension,
    )

    query_vector = provider.embed([query])[0]
    raw_results = store.search(query_vector, top_k=top_k)

    chunks = [
        RetrievedChunk(
            chunk_id=r.id,
            document_id=r.metadata.get("document_id"),
            document_name=r.metadata.get("document_name"),
            document_version=r.metadata.get("document_version"),
            page_number=r.metadata.get("page_number"),
            section_title=r.metadata.get("section_title"),
            source_text=r.metadata.get("source_text", ""),
            relevance_score=r.score,
        )
        for r in raw_results
        if r.score >= threshold
    ]

    return RetrievalResult(query=query, chunks=chunks, has_sufficient_context=len(chunks) > 0)
