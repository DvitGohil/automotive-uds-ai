from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.db.models import Document, DocumentVersion, Project
from app.uds.knowledge_model import (
    SourceReference,
    UdsDid,
    UdsNegativeResponse,
    UdsNrc,
    UdsPositiveResponse,
    UdsRequest,
    UdsRid,
    UdsService,
    UdsSubfunction,
)
from app.uds.repository import load_uds_entity, save_uds_entity

engine = create_engine("sqlite:///:memory:")
TestingSession = sessionmaker(bind=engine)


def setup_module(_module):
    Base.metadata.create_all(bind=engine)


def _source():
    return SourceReference(
        document_id="doc-1", document_name="ISO 14229", document_version=1,
        page_number=12, section_title="9.2", chunk_id="chunk-9",
    )


def test_service_with_subfunctions_and_nrcs_round_trips():
    service = UdsService(
        service_id="0x10",
        service_name="DiagnosticSessionControl",
        description="Enables a diagnostic session.",
        category="session",
        subfunctions=[UdsSubfunction("0x10", "0x01", "defaultSession", source=_source())],
        nrcs=[UdsNrc("0x12", "subFunctionNotSupported", source=_source())],
        source=_source(),
    )
    restored = UdsService.from_dict(service.to_dict())
    assert restored.service_id == "0x10"
    assert restored.subfunctions[0].subfunction_id == "0x01"
    assert restored.nrcs[0].nrc == "0x12"
    assert restored.source.chunk_id == "chunk-9"


def test_subfunction_missing_fields_are_none():
    sub = UdsSubfunction(service_id="0x22", subfunction_id="0x01")
    assert sub.name is None
    assert sub.description is None
    assert sub.source is None  # unknown, not guessed


def test_did_supports_optional_length_and_access():
    did = UdsDid(did="0xF190", name="VIN", data_length=17, access="read", source=_source())
    restored = UdsDid.from_dict(did.to_dict())
    assert restored.data_length == 17
    assert restored.access == "read"


def test_did_missing_optional_fields_stay_unknown():
    did = UdsDid(did="0xF190")
    assert did.data_length is None
    assert did.access is None
    assert did.description is None


def test_rid_round_trips():
    rid = UdsRid(rid="0x0203", name="EraseMemory", source=_source())
    restored = UdsRid.from_dict(rid.to_dict())
    assert restored.rid == "0x0203"
    assert restored.name == "EraseMemory"


def test_nrc_applicable_fields_optional():
    nrc = UdsNrc(nrc="0x31", nrc_name="requestOutOfRange")
    assert nrc.applicable_service is None
    assert nrc.applicable_conditions is None


def test_request_representation_round_trips():
    request = UdsRequest(
        service_id="0x22", did="0xF190", parameters={}, request_bytes="22 F1 90", source=_source()
    )
    restored = UdsRequest.from_dict(request.to_dict())
    assert restored.service_id == "0x22"
    assert restored.request_bytes == "22 F1 90"
    assert restored.source.section_title == "9.2"


def test_positive_response_round_trips():
    resp = UdsPositiveResponse(service_id="0x62", parameters={"did": "0xF190", "value": "abc"})
    restored = UdsPositiveResponse.from_dict(resp.to_dict())
    assert restored.service_id == "0x62"
    assert restored.parameters["value"] == "abc"


def test_negative_response_round_trips():
    neg = UdsNegativeResponse(original_service_id="0x22", nrc="0x31", description="requestOutOfRange")
    restored = UdsNegativeResponse.from_dict(neg.to_dict())
    assert restored.negative_response_sid == "0x7F"
    assert restored.nrc == "0x31"


def test_source_traceability_document_to_chunk_chain_present():
    source = _source()
    assert source.document_id and source.document_version and source.page_number and source.chunk_id


def _seed_document_version(db):
    project = Project(name="Pilot")
    db.add(project)
    db.flush()
    document = Document(project_id=project.id, title="ISO 14229 Extract", source_type="uds_spec")
    db.add(document)
    db.flush()
    version = DocumentVersion(document_id=document.id, version_number=1, file_path="/tmp/spec.pdf")
    db.add(version)
    db.commit()
    return version


def test_repository_save_and_load_service():
    db = TestingSession()
    try:
        version = _seed_document_version(db)
        service = UdsService(service_id="0x27", service_name="SecurityAccess", source=_source())
        save_uds_entity(db, version.id, "service", "0x27", service)

        loaded = load_uds_entity(db, version.id, "service", "0x27")
        assert loaded is not None
        assert loaded.service_name == "SecurityAccess"
        assert loaded.source.document_name == "ISO 14229"
    finally:
        db.close()


def test_repository_load_missing_entity_returns_none():
    db = TestingSession()
    try:
        version = _seed_document_version(db)
        assert load_uds_entity(db, version.id, "did", "0xFFFF") is None
    finally:
        db.close()
