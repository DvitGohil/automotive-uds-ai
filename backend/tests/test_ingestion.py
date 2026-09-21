import json

import pytest
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.db.models import Document, DocumentStatus, DocumentVersion, ExtractedSegment, Project
from app.ingestion.extractors import extract, extract_pdf, extract_txt
from app.ingestion.service import ingest_document

engine = create_engine("sqlite:///:memory:")
TestingSession = sessionmaker(bind=engine)


def setup_module(_module):
    Base.metadata.create_all(bind=engine)


@pytest.fixture
def txt_file(tmp_path):
    content = (
        "1 Introduction\n"
        "This is the introduction section body text.\n"
        "2.1 Diagnostic Session Control\n"
        "Body text describing the diagnostic session control service.\n"
    )
    path = tmp_path / "sample_spec.txt"
    path.write_text(content, encoding="utf-8")
    return str(path)


@pytest.fixture
def pdf_file(tmp_path):
    path = tmp_path / "sample_spec.pdf"
    c = canvas.Canvas(str(path), pagesize=letter)
    c.drawString(72, 720, "3.2 Diagnostic Session Control")
    c.drawString(72, 700, "Positive response requires a supported session type.")
    c.showPage()
    c.drawString(72, 720, "3.3 Security Access")
    c.drawString(72, 700, "Seed and key exchange precedes protected services.")
    c.showPage()
    c.save()
    return str(path)


def test_extract_txt_splits_sections_with_page_1(txt_file):
    units = extract_txt(txt_file)
    assert len(units) == 2
    assert units[0].page_number == 1
    assert units[0].section_title == "1 Introduction"
    assert "introduction section" in units[0].content
    assert units[1].section_title == "2.1 Diagnostic Session Control"


def test_extract_pdf_tracks_page_and_section(pdf_file):
    units = extract_pdf(pdf_file)
    text_units = [u for u in units if u.segment_type == "text"]
    pages = {u.page_number for u in text_units}
    assert pages == {1, 2}

    page1 = next(u for u in text_units if u.page_number == 1)
    assert page1.section_title == "3.2 Diagnostic Session Control"
    assert "supported session type" in page1.content

    page2 = next(u for u in text_units if u.page_number == 2)
    assert page2.section_title == "3.3 Security Access"


def test_extract_dispatches_by_extension(txt_file, pdf_file):
    assert extract(txt_file)  # .txt
    assert extract(pdf_file)  # .pdf


def test_extract_rejects_unsupported_format(tmp_path):
    bad_file = tmp_path / "spec.docx"
    bad_file.write_text("irrelevant")
    with pytest.raises(ValueError):
        extract(str(bad_file))


def test_ingest_document_persists_traceable_segments(txt_file):
    db = TestingSession()
    try:
        project = Project(name="Pilot Project")
        db.add(project)
        db.flush()

        document = ingest_document(
            db,
            project_id=project.id,
            title="Sample UDS Spec",
            source_type="uds_spec",
            original_file_path=txt_file,
            original_filename="sample_spec.txt",
            is_approved=True,
        )

        assert document.status == DocumentStatus.INGESTED

        version = db.query(DocumentVersion).filter_by(document_id=document.id).first()
        assert version is not None
        assert version.version_number == 1
        assert version.extracted_text_path is not None

        segments = db.query(ExtractedSegment).filter_by(document_version_id=version.id).all()
        assert len(segments) == 2
        for segment in segments:
            # Full traceability: Document -> Version -> Page -> Section
            assert segment.document_version.document_id == document.id
            assert segment.page_number == 1
            assert segment.section_title is not None
            metadata = json.loads(segment.extra_metadata)
            assert metadata["source_format"] == "txt"
    finally:
        db.close()


def test_ingest_document_rejects_unsupported_format(tmp_path):
    db = TestingSession()
    try:
        project = Project(name="Pilot Project 2")
        db.add(project)
        db.flush()

        bad_file = tmp_path / "spec.docx"
        bad_file.write_text("irrelevant")

        with pytest.raises(ValueError):
            ingest_document(
                db,
                project_id=project.id,
                title="Bad Spec",
                source_type="uds_spec",
                original_file_path=str(bad_file),
                original_filename="spec.docx",
            )
        # No orphaned Document row should be committed for the rejected format
        assert db.query(Document).filter_by(title="Bad Spec").count() == 0
    finally:
        db.close()
