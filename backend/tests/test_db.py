from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.db.models import (
    AuditRecord,
    Document,
    DocumentVersion,
    DiagnosticKnowledgeUnit,
    Project,
    TestCase,
    User,
    ValidationResult,
)

# Isolated in-memory DB per test run — does not touch the dev SQLite file.
engine = create_engine("sqlite:///:memory:")
TestingSession = sessionmaker(bind=engine)


def setup_module(_module):
    Base.metadata.create_all(bind=engine)


def test_core_entity_chain_persists_and_links():
    db = TestingSession()
    try:
        user = User(email="engineer@example.com", full_name="Test Engineer")
        project = Project(name="Pilot Project")
        db.add_all([user, project])
        db.flush()

        document = Document(
            project_id=project.id,
            title="ISO 14229 Extract",
            source_type="uds_spec",
            is_approved=True,
            uploaded_by=user.id,
        )
        db.add(document)
        db.flush()

        version = DocumentVersion(
            document_id=document.id,
            version_number=1,
            file_path="/data/docs/iso14229_v1.pdf",
        )
        db.add(version)
        db.flush()

        knowledge_unit = DiagnosticKnowledgeUnit(
            document_version_id=version.id,
            unit_type="service",
            identifier="0x22",
            title="ReadDataByIdentifier",
            content="Placeholder content for schema test.",
        )
        test_case = TestCase(project_id=project.id, title="Read VIN - positive case", created_by=user.id)
        db.add_all([knowledge_unit, test_case])
        db.flush()

        validation_result = ValidationResult(
            test_case_id=test_case.id,
            validation_type="request_structure",
        )
        audit_record = AuditRecord(
            project_id=project.id,
            user_id=user.id,
            action="document_uploaded",
            entity_type="document",
            entity_id=document.id,
        )
        db.add_all([validation_result, audit_record])
        db.commit()

        assert db.query(User).count() == 1
        assert db.query(Project).count() == 1
        assert db.query(Document).count() == 1
        assert db.query(DocumentVersion).count() == 1
        assert db.query(DiagnosticKnowledgeUnit).count() == 1
        assert db.query(TestCase).count() == 1
        assert db.query(ValidationResult).count() == 1
        assert db.query(AuditRecord).count() == 1

        fetched_project = db.query(Project).first()
        assert fetched_project.documents[0].title == "ISO 14229 Extract"
        assert fetched_project.test_cases[0].title == "Read VIN - positive case"

        fetched_test_case = db.query(TestCase).first()
        assert fetched_test_case.validation_results[0].validation_type == "request_structure"
    finally:
        db.close()
