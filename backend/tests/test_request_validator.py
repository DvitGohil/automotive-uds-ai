from app.uds.knowledge_model import SourceReference, UdsRequest
from app.uds.request_validator import validate_request


def test_1_valid_service():
    result = validate_request(UdsRequest(service_id="0x14"))
    assert result.valid is True
    assert result.service_info["service_name"] == "ClearDiagnosticInformation"


def test_2_invalid_service():
    result = validate_request(UdsRequest(service_id="0x99"))
    assert result.valid is False
    assert any("not supported" in e for e in result.errors)


def test_3_valid_subfunction():
    result = validate_request(UdsRequest(service_id="0x10", subfunction_id="0x01"))
    assert result.valid is True
    assert result.validated_fields["subfunction_id"] == "0x01"


def test_4_invalid_subfunction():
    result = validate_request(UdsRequest(service_id="0x10", subfunction_id="zz"))
    assert result.valid is False
    assert any("Malformed subfunction" in e for e in result.errors)


def test_5_valid_did():
    result = validate_request(UdsRequest(service_id="0x22", did="0xF190"))
    assert result.valid is True
    assert result.validated_fields["did"] == "0xF190"


def test_6_invalid_did():
    result = validate_request(UdsRequest(service_id="0x22", did="bad"))
    assert result.valid is False
    assert any("Malformed DID" in e for e in result.errors)


def test_7_valid_rid():
    result = validate_request(UdsRequest(service_id="0x31", subfunction_id="0x01", rid="0x0203"))
    assert result.valid is True
    assert result.validated_fields["rid"] == "0x0203"


def test_8_invalid_rid():
    result = validate_request(UdsRequest(service_id="0x31", subfunction_id="0x01", rid="bad"))
    assert result.valid is False
    assert any("Malformed RID" in e for e in result.errors)


def test_9_missing_parameter_reported_as_missing_did():
    result = validate_request(UdsRequest(service_id="0x22"))
    assert result.valid is False
    assert any("Missing required DID" in e for e in result.errors)


def test_10_malformed_parameter_service_id():
    result = validate_request(UdsRequest(service_id="not-hex"))
    assert result.valid is False
    assert any("Invalid service ID format" in e for e in result.errors)


def test_11_invalid_request_structure_byte_mismatch():
    request = UdsRequest(service_id="0x22", did="0xF190", request_bytes="AA BB CC")
    result = validate_request(request)
    assert result.valid is False
    assert any("inconsistent" in e for e in result.errors)


def test_12_valid_request_full_pipeline():
    request = UdsRequest(service_id="0x22", did="0xF190", request_bytes="22 F1 90")
    result = validate_request(request)
    assert result.valid is True
    assert result.request_representation == "22 F1 90"
    assert result.errors == []


def test_13_invalid_request_missing_required_subfunction():
    result = validate_request(UdsRequest(service_id="0x27"))
    assert result.valid is False
    assert any("subfunction" in e.lower() for e in result.errors)


def test_14_traceability_source_carried_into_result():
    source = SourceReference(document_id="doc-1", document_name="ISO 14229", chunk_id="chunk-1")
    request = UdsRequest(service_id="0x22", did="0xF190", source=source)
    result = validate_request(request)
    assert result.valid is True
    assert result.source.chunk_id == "chunk-1"


def test_14b_missing_source_produces_warning_not_error():
    request = UdsRequest(service_id="0x22", did="0xF190")
    result = validate_request(request)
    assert result.valid is True
    assert any("traceability" in w.lower() for w in result.warnings)


def test_15_deterministic_repeated_validation():
    request = UdsRequest(service_id="0x22", did="0xF190")
    r1 = validate_request(request)
    r2 = validate_request(request)
    assert r1.valid == r2.valid
    assert r1.request_representation == r2.request_representation
    assert r1.validated_fields == r2.validated_fields
