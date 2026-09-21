"""
Grounded UDS engineering assistant. Answers a question using ONLY the
approved-document context Stage 6 retrieval finds — never outside knowledge.
Decision-support only: never executes anything against an ECU.
"""
import json
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import AuditRecord
from app.rag.embeddings import EmbeddingProvider
from app.rag.llm import LLMProvider, get_llm_provider
from app.rag.retrieval import retrieve


@dataclass
class Citation:
    document_id: str
    document_name: str
    document_version: int
    page_number: int | None
    section_title: str | None
    chunk_id: str


@dataclass
class GroundedAnswer:
    question: str
    answer: str
    citations: list[Citation] = field(default_factory=list)
    confidence: str = "none"  # "high" | "medium" | "low" | "none"
    limitations: str | None = None
    requires_engineering_review: bool = True  # decision-support only, always


INSUFFICIENT_CONTEXT_ANSWER = (
    "The available approved sources do not provide enough information to answer this "
    "question. Evidence Not Found. Review Required."
)


def _confidence_from_scores(scores: list[float]) -> str:
    if not scores:
        return "none"
    top = max(scores)
    if top >= 0.6:
        return "high"
    if top >= 0.3:
        return "medium"
    return "low"


def ask(
    db: Session | None,
    project_id: str,
    question: str,
    *,
    top_k: int | None = None,
    embedding_provider: EmbeddingProvider | None = None,
    llm_provider: LLMProvider | None = None,
    log_audit: bool = True,
) -> GroundedAnswer:
    retrieval_result = retrieve(
        project_id,
        question,
        top_k=top_k or settings.RETRIEVAL_TOP_K,
        embedding_provider=embedding_provider,
    )

    if not retrieval_result.has_sufficient_context:
        answer = GroundedAnswer(
            question=question,
            answer=INSUFFICIENT_CONTEXT_ANSWER,
            citations=[],
            confidence="none",
            limitations="No approved source content met the relevance threshold for this query.",
        )
    else:
        provider = llm_provider or get_llm_provider()
        context_blocks = [
            f"[Source: {c.document_name} v{c.document_version}, page {c.page_number}, "
            f"section {c.section_title}]\n{c.source_text}"
            for c in retrieval_result.chunks
        ]
        raw_answer = provider.generate(question, context_blocks)
        citations = [
            Citation(
                document_id=c.document_id,
                document_name=c.document_name,
                document_version=c.document_version,
                page_number=c.page_number,
                section_title=c.section_title,
                chunk_id=c.chunk_id,
            )
            for c in retrieval_result.chunks
        ]
        confidence = _confidence_from_scores([c.relevance_score for c in retrieval_result.chunks])
        answer = GroundedAnswer(
            question=question,
            answer=raw_answer,
            citations=citations,
            confidence=confidence,
            limitations=(
                "Retrieved context has limited relevance to the question; verify against source "
                "documents before relying on this answer."
                if confidence == "low"
                else None
            ),
        )

    if log_audit and db is not None:
        db.add(
            AuditRecord(
                project_id=project_id,
                action="uds_question_answered",
                entity_type="query",
                details=json.dumps(
                    {
                        "question": question,
                        "confidence": answer.confidence,
                        "citation_count": len(answer.citations),
                    }
                ),
            )
        )
        db.commit()

    return answer
