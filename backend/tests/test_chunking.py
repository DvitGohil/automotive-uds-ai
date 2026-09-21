import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.db.models import Document, DocumentChunk, DocumentVersion, ExtractedSegment, Project, SegmentType
from app.rag.chunking import ChunkInput, build_chunks, chunk_text
from app.rag.chunking_service import chunk_document_version

engine = create_engine("sqlite:///:memory:")
TestingSession = sessionmaker(bind=engine)


def setup_module(_module):
    Base.metadata.create_all(bind=engine)


# --- pure chunk_text ---------------------------------------------------

def test_chunk_text_short_text_single_chunk():
    result = chunk_text("Short body.", chunk_size=800, chunk_overlap=100)
    assert result == ["Short body."]


def test_chunk_text_empty_returns_nothing():
    assert chunk_text("   \n  ", chunk_size=800, chunk_overlap=100) == []
    assert chunk_text("", chunk_size=800, chunk_overlap=100) == []


def test_chunk_text_long_text_respects_chunk_size():
    text = "word " * 500  # 2500 chars
    result = chunk_text(text, chunk_size=100, chunk_overlap=20)
    assert len(result) > 1
    assert all(len(c) <= 100 for c in result)


def test_chunk_text_overlap_shares_boundary_content():
    text = "".join(f"{i:04d}" for i in range(200))  # deterministic long string
    chunks = chunk_text(text, chunk_size=100, chunk_overlap=20)
    assert len(chunks) > 1
    # end of chunk[0] should reappear at the start of chunk[1] (the overlap window)
    overlap_expected = chunks[0][-20:]
    assert chunks[1].startswith(overlap_expected[: len(chunks[1])] if len(overlap_expected) > len(chunks[1]) else overlap_expected)


def test_chunk_text_rejects_invalid_config():
    with pytest.raises(ValueError):
        chunk_text("some text", chunk_size=0, chunk_overlap=0)
    with pytest.raises(ValueError):
        chunk_text("some text", chunk_size=100, chunk_overlap=100)
    with pytest.raises(ValueError):
        chunk_text("some text", chunk_size=100, chunk_overlap=150)


# --- build_chunks (section/table aware) --------------------------------

def test_build_chunks_normal_document_multiple_sections():
    segments = [
        ChunkInput("seg-1", "doc-1", "ver-1", 1, "1 Introduction", "text", "This is the introduction body."),
        ChunkInput("seg-2", "doc-1", "ver-1", 1, "2 Diagnostic Session Control", "text", "Session control body text."),
    ]
    chunks = build_chunks(segments, chunk_size=800, chunk_overlap=100)
    assert len(chunks) == 2
    assert chunks[0].section_title == "1 Introduction"
    assert chunks[1].section_title == "2 Diagnostic Session Control"
    assert [c.chunk_index for c in chunks] == [0, 1]


def test_build_chunks_long_document_produces_multiple_chunks_per_segment():
    long_text = "The tester shall verify the response. " * 100
    segments = [ChunkInput("seg-1", "doc-1", "ver-1", 3, "3.2 Positive Response", "text", long_text)]
    chunks = build_chunks(segments, chunk_size=200, chunk_overlap=40)
    assert len(chunks) > 1
    assert all(c.page_number == 3 for c in chunks)
    assert all(c.section_title == "3.2 Positive Response" for c in chunks)
    assert all(c.char_count <= 200 for c in chunks)


def test_build_chunks_empty_document_produces_no_chunks():
    assert build_chunks([], chunk_size=800, chunk_overlap=100) == []
    segments = [ChunkInput("seg-1", "doc-1", "ver-1", 1, None, "text", "   ")]
    assert build_chunks(segments, chunk_size=800, chunk_overlap=100) == []


def test_build_chunks_table_kept_whole_never_split():
    table_json = '[["DID", "Name"], ["0xF190", "VIN"]]' * 20  # long, but must not be split
    segments = [ChunkInput("seg-3", "doc-1", "ver-1", 5, None, "table", table_json)]
    chunks = build_chunks(segments, chunk_size=50, chunk_overlap=10)  # small size on purpose
    assert len(chunks) == 1
    assert chunks[0].chunk_type == "table"
    assert chunks[0].content == table_json.strip()


def test_build_chunks_metadata_and_source_text_preserved():
    segments = [ChunkInput("seg-9", "doc-1", "ver-1", 7, "7 Security Access", "text", "Seed/key exchange text.")]
    chunks = build_chunks(segments, chunk_size=800, chunk_overlap=100)
    assert len(chunks) == 1
    chunk = chunks[0]
    assert chunk.segment_id == "seg-9"
    assert chunk.page_number == 7
    assert chunk.section_title == "7 Security Access"
    assert chunk.content == "Seed/key exchange text."  # original source text preserved verbatim


# --- DB-backed chunk_document_version -----------------------------------

def _seed_document_with_segments(db):
    project = Project(name="Pilot")
    db.add(project)
    db.flush()

    document = Document(project_id=project.id, title="Spec", source_type="uds_spec")
    db.add(document)
    db.flush()

    version = DocumentVersion(document_id=document.id, version_number=1, file_path="/tmp/spec.txt")
    db.add(version)
    db.flush()

    seg1 = ExtractedSegment(
        document_version_id=version.id,
        page_number=1,
        section_title="1 Introduction",
        segment_type=SegmentType.TEXT,
        content="Introduction body text that is reasonably descriptive.",
    )
    seg2 = ExtractedSegment(
        document_version_id=version.id,
        page_number=2,
        section_title=None,
        segment_type=SegmentType.TABLE,
        content='[["DID","Name"],["0xF190","VIN"]]',
    )
    db.add_all([seg1, seg2])
    db.commit()
    return document, version


def test_chunk_document_version_persists_traceable_chunks():
    db = TestingSession()
    try:
        document, version = _seed_document_with_segments(db)
        chunks = chunk_document_version(db, version.id)

        assert len(chunks) == 2
        for chunk in chunks:
            assert chunk.document_id == document.id
            assert chunk.document_version_id == version.id
            assert chunk.extracted_segment_id is not None
            assert chunk.content  # original source text preserved
    finally:
        db.close()


def test_chunk_document_version_reprocessing_does_not_duplicate():
    db = TestingSession()
    try:
        _, version = _seed_document_with_segments(db)

        first_pass = chunk_document_version(db, version.id)
        second_pass = chunk_document_version(db, version.id)

        total_in_db = db.query(DocumentChunk).filter_by(document_version_id=version.id).count()
        assert len(first_pass) == len(second_pass)
        assert total_in_db == len(second_pass)  # replaced, not accumulated
    finally:
        db.close()


def test_chunk_document_version_missing_version_raises():
    db = TestingSession()
    try:
        with pytest.raises(ValueError):
            chunk_document_version(db, "does-not-exist")
    finally:
        db.close()
