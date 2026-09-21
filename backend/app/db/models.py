import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.db.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class UserRole(str, enum.Enum):
    ENGINEER = "engineer"
    LEAD = "lead"
    QUALITY_MANAGER = "quality_manager"
    ADMIN = "admin"


class DocumentStatus(str, enum.Enum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    INGESTED = "ingested"
    FAILED = "failed"


class ReviewStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EDITED = "edited"


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=_uuid)
    email = Column(String(255), unique=True, nullable=False, index=True)
    full_name = Column(String(255), nullable=False)
    password_hash = Column(String(255), nullable=True)  # set on registration; null = no password (legacy/seeded rows)
    role = Column(Enum(UserRole), nullable=False, default=UserRole.ENGINEER)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    projects = relationship("ProjectMember", back_populates="user")


class Project(Base):
    """An authorized project workspace (per-project document/vector collection scoping)."""

    __tablename__ = "projects"

    id = Column(String(36), primary_key=True, default=_uuid)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    members = relationship("ProjectMember", back_populates="project")
    documents = relationship("Document", back_populates="project")
    test_cases = relationship("TestCase", back_populates="project")


class ProjectMember(Base):
    """Join table: which users are authorized on which project."""

    __tablename__ = "project_members"

    id = Column(String(36), primary_key=True, default=_uuid)
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    role = Column(Enum(UserRole), nullable=False, default=UserRole.ENGINEER)

    project = relationship("Project", back_populates="members")
    user = relationship("User", back_populates="projects")


class Document(Base):
    """An uploaded/approved source document (UDS spec, OEM spec, ECU extract, requirement, etc.)."""

    __tablename__ = "documents"

    id = Column(String(36), primary_key=True, default=_uuid)
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False)
    title = Column(String(255), nullable=False)
    source_type = Column(String(100), nullable=False)  # e.g. uds_spec, oem_spec, ecu_extract, requirement
    status = Column(Enum(DocumentStatus), nullable=False, default=DocumentStatus.UPLOADED)
    is_approved = Column(Boolean, default=False, nullable=False)  # Rule 5: only approved docs are source of truth
    uploaded_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    project = relationship("Project", back_populates="documents")
    versions = relationship("DocumentVersion", back_populates="document")


class DocumentVersion(Base):
    """Immutable version snapshot of a document (file path/hash + extracted-text pointer)."""

    __tablename__ = "document_versions"

    id = Column(String(36), primary_key=True, default=_uuid)
    document_id = Column(String(36), ForeignKey("documents.id"), nullable=False)
    version_number = Column(Integer, nullable=False, default=1)
    file_path = Column(String(1024), nullable=False)
    file_hash = Column(String(128), nullable=True)
    extracted_text_path = Column(String(1024), nullable=True)  # populated during ingestion stage
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    document = relationship("Document", back_populates="versions")


class DiagnosticKnowledgeUnit(Base):
    """
    Structured metadata for a piece of extracted UDS knowledge (service, DID, RID, NRC,
    session/security rule, etc.) sourced from an approved document version.
    Embedding/vector storage itself is implemented in the RAG stage; this table only
    tracks the structured record and its traceable source and optional vector reference.
    """

    __tablename__ = "diagnostic_knowledge_units"

    id = Column(String(36), primary_key=True, default=_uuid)
    document_version_id = Column(String(36), ForeignKey("document_versions.id"), nullable=False)
    unit_type = Column(String(50), nullable=False)  # service | did | rid | nrc | session | security | other
    identifier = Column(String(100), nullable=True)  # e.g. 0x22, DID hex, RID hex
    title = Column(String(255), nullable=True)
    content = Column(Text, nullable=False)
    source_page = Column(Integer, nullable=True)
    vector_ref = Column(String(255), nullable=True)  # id in the vector store, set in a later stage
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    document_version = relationship("DocumentVersion")


class TestCase(Base):
    """A generated (or manually authored) diagnostic test case."""

    __tablename__ = "test_cases"

    id = Column(String(36), primary_key=True, default=_uuid)
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False)
    title = Column(String(255), nullable=False)
    objective = Column(Text, nullable=True)
    scenario_category = Column(String(100), nullable=True)  # negative-test category; null for positive tests
    invalid_condition = Column(Text, nullable=True)  # negative-test description of what's wrong; null for positive
    request_definition = Column(Text, nullable=True)  # constructed UDS request, set in test-generation stage
    preconditions = Column(Text, nullable=True)
    expected_response = Column(Text, nullable=True)
    pass_criteria = Column(Text, nullable=True)  # JSON list of strings
    fail_criteria = Column(Text, nullable=True)  # JSON list of strings
    is_negative_case = Column(Boolean, default=False, nullable=False)
    generated_by_ai = Column(Boolean, default=False, nullable=False)
    review_status = Column(Enum(ReviewStatus), nullable=False, default=ReviewStatus.PENDING)
    created_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    project = relationship("Project", back_populates="test_cases")
    validation_results = relationship("ValidationResult", back_populates="test_case")


class ValidationResult(Base):
    """Result of deterministic/response validation run against a test case (not auto-executed on an ECU)."""

    __tablename__ = "validation_results"

    id = Column(String(36), primary_key=True, default=_uuid)
    test_case_id = Column(String(36), ForeignKey("test_cases.id"), nullable=False)
    validation_type = Column(String(50), nullable=False)  # request_structure | expected_response | coverage
    passed = Column(Boolean, nullable=True)  # null until run
    details = Column(Text, nullable=True)
    reviewed_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    review_status = Column(Enum(ReviewStatus), nullable=False, default=ReviewStatus.PENDING)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    test_case = relationship("TestCase", back_populates="validation_results")


class SegmentType(str, enum.Enum):
    TEXT = "text"
    TABLE = "table"


class ExtractedSegment(Base):
    """
    A single extracted unit of content from a document version, kept fully
    traceable to Document -> Version -> Page -> Section. Populated by the
    ingestion stage only (no embeddings, no LLM interpretation here).
    """

    __tablename__ = "extracted_segments"

    id = Column(String(36), primary_key=True, default=_uuid)
    document_version_id = Column(String(36), ForeignKey("document_versions.id"), nullable=False)
    page_number = Column(Integer, nullable=True)
    section_title = Column(String(500), nullable=True)
    segment_type = Column(Enum(SegmentType), nullable=False, default=SegmentType.TEXT)
    content = Column(Text, nullable=False)  # raw text, or JSON-serialized table rows for TABLE segments
    extra_metadata = Column(Text, nullable=True)  # JSON string: e.g. {"source_format": "pdf", "table_shape": [r, c]}
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    document_version = relationship("DocumentVersion")


class DocumentChunk(Base):
    """
    A chunk of a document version's extracted content, sized for embeddings/RAG.
    Traceable to Document -> Version -> Page -> Section -> source ExtractedSegment.
    Reprocessing a document version replaces its chunk set (no uncontrolled duplication).
    """

    __tablename__ = "document_chunks"

    id = Column(String(36), primary_key=True, default=_uuid)
    document_id = Column(String(36), ForeignKey("documents.id"), nullable=False)
    document_version_id = Column(String(36), ForeignKey("document_versions.id"), nullable=False)
    extracted_segment_id = Column(String(36), ForeignKey("extracted_segments.id"), nullable=True)
    chunk_index = Column(Integer, nullable=False)
    page_number = Column(Integer, nullable=True)
    section_title = Column(String(500), nullable=True)
    chunk_type = Column(Enum(SegmentType), nullable=False, default=SegmentType.TEXT)
    content = Column(Text, nullable=False)
    content_hash = Column(String(64), nullable=False, index=True)  # sha256 hex, dedup/change-detection aid
    char_count = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    document = relationship("Document")
    document_version = relationship("DocumentVersion")
    extracted_segment = relationship("ExtractedSegment")


class AuditRecord(Base):
    """Traceability/audit log entry for engineering actions (ingestion, generation, review decisions)."""

    __tablename__ = "audit_records"

    id = Column(String(36), primary_key=True, default=_uuid)
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    action = Column(String(100), nullable=False)  # e.g. document_uploaded, test_generated, test_approved
    entity_type = Column(String(100), nullable=True)  # e.g. document, test_case, validation_result
    entity_id = Column(String(36), nullable=True)
    details = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
