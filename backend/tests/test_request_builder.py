from app.uds.request_builder import build_request


def test_service_plus_subfunction_request_succeeds():
    result = build_request("0x10", subfunction_id="0x01")
    assert result.success is True
    assert result.request.request_bytes == "10 01"
    assert result.fields_used == {"service_id": "0x10", "subfunction_id": "0x01"}


def test_service_plus_did_request_succeeds():
    result = build_request("0x22", did="0xF190")
    assert result.success is True
    assert result.request.request_bytes == "22 F1 90"
    assert result.request.did == "0xF190"


def test_service_plus_rid_request_succeeds():
    result = build_request("0x31", subfunction_id="0x01", rid="0x0203")
    assert result.success is True
    assert "31" in result.request.request_bytes
    assert result.request.rid == "0x0203"


def test_service_only_request_succeeds_when_no_extra_fields_required():
    result = build_request("0x14")
    assert result.success is True
    assert result.request.request_bytes == "14"


def test_service_with_parameters_preserved_on_request():
    result = build_request("0x2E", did="0xF190", parameters={"value": "ABCD"})
    assert result.success is True
    assert result.request.parameters == {"value": "ABCD"}


def test_missing_required_subfunction_fails_with_clear_error():
    result = build_request("0x10")
    assert result.success is False
    assert any("subfunction" in e.lower() for e in result.errors)
    assert result.request is None


def test_missing_required_did_fails_with_clear_error():
    result = build_request("0x22")
    assert result.success is False
    assert any("DID" in e for e in result.errors)


def test_malformed_did_fails():
    result = build_request("0x22", did="not-a-did")
    assert result.success is False
    assert any("Malformed DID" in e for e in result.errors)


def test_malformed_subfunction_fails():
    result = build_request("0x10", subfunction_id="zz")
    assert result.success is False
    assert any("Malformed subfunction" in e for e in result.errors)


def test_unsupported_service_fails_clearly():
    result = build_request("0x99")
    assert result.success is False
    assert any("Unsupported service" in e for e in result.errors)


def test_invalid_service_format_fails():
    result = build_request("not-hex")
    assert result.success is False
    assert any("Invalid or malformed service ID" in e for e in result.errors)


def test_invalid_rid_format_fails():
    result = build_request("0x31", subfunction_id="0x01", rid="bad")
    assert result.success is False
    assert any("Malformed RID" in e for e in result.errors)


def test_extraneous_field_produces_warning_not_error():
    result = build_request("0x14", did="0xF190")
    assert result.success is True  # 0x14 doesn't require a DID
    assert any("does not use one" in w for w in result.warnings)


def test_hex_representation_is_deterministic_and_repeatable():
    r1 = build_request("0x22", did="0xF190")
    r2 = build_request("0x22", did="0xF190")
    assert r1.request.request_bytes == r2.request.request_bytes == "22 F1 90"


def test_source_reference_carried_through_to_request():
    from app.uds.knowledge_model import SourceReference

    source = SourceReference(document_id="doc-1", chunk_id="chunk-1")
    result = build_request("0x22", did="0xF190", source=source)
    assert result.request.source.chunk_id == "chunk-1"
