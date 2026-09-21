from app.test_generation.positive import generate_positive_test
from app.uds.knowledge_model import SourceReference


def _source():
    return SourceReference(document_id="doc-1", document_name="ISO 14229", document_version=1,
                            page_number=12, section_title="9.2", chunk_id="chunk-9")


def test_1_valid_positive_test_generation():
    result = generate_positive_test("0x22", did="0xF190", source=_source())
    assert result.success is True
    assert result.test_case.request.did == "0xF190"


def test_2_preconditions_preserved_verbatim():
    result = generate_positive_test("0x22", did="0xF190", preconditions=["Default session active"])
    assert result.test_case.preconditions == ["Default session active"]


def test_3_validated_request_integration():
    result = generate_positive_test("0x10", subfunction_id="0x01")
    assert result.success is True
    assert result.test_case.request.request_bytes == "10 01"


def test_4_expected_positive_response_sid_is_generic_iso_rule():
    result = generate_positive_test("0x22", did="0xF190")
    assert result.test_case.expected_response.service_id == "0x62"
    assert result.test_case.expected_response.parameters["did"] == "0xF190"


def test_5_pass_criteria_present_and_reference_response_sid():
    result = generate_positive_test("0x22", did="0xF190")
    assert any("0x62" in c for c in result.test_case.pass_criteria)


def test_6_fail_criteria_present():
    result = generate_positive_test("0x22", did="0xF190")
    assert any("negative response" in c.lower() for c in result.test_case.fail_criteria)


def test_7_source_traceability_preserved():
    result = generate_positive_test("0x22", did="0xF190", source=_source())
    assert result.test_case.source.chunk_id == "chunk-9"


def test_8_insufficient_source_information_marks_incomplete_not_guessed():
    result = generate_positive_test("0x22", did="0xF190")  # no expected_response_parameters supplied
    assert result.success is True
    assert result.test_case.is_complete is False
    assert result.test_case.missing_info  # explicitly flagged, not silently filled in
    assert "value" not in result.test_case.expected_response.parameters


def test_8b_documented_response_data_marks_complete():
    result = generate_positive_test("0x22", did="0xF190", expected_response_parameters={"value": "1HGCM82633A004352"})
    assert result.test_case.is_complete is True
    assert result.test_case.expected_response.parameters["value"] == "1HGCM82633A004352"


def test_9_unsupported_diagnostic_combination_fails_cleanly():
    result = generate_positive_test("0x99")  # not in the known service registry
    assert result.success is False
    assert result.test_case is None
    assert result.errors


def test_10_deterministic_validation_integration_rejects_missing_required_field():
    result = generate_positive_test("0x22")  # missing required DID
    assert result.success is False
    assert any("DID" in e for e in result.errors)


def test_stable_test_case_id_is_deterministic():
    r1 = generate_positive_test("0x22", did="0xF190")
    r2 = generate_positive_test("0x22", did="0xF190")
    assert r1.test_case.test_case_id == r2.test_case.test_case_id
