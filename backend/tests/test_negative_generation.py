from app.test_generation.negative import generate_negative_suite, generate_negative_test
from app.uds.knowledge_model import SourceReference, UdsNrc


def _source():
    return SourceReference(document_id="doc-1", document_name="ISO 14229", chunk_id="chunk-9")


def test_1_negative_test_generation_missing_required_field():
    result = generate_negative_test("missing_required_field", "0x22")  # DID omitted
    assert result.success is True
    assert result.test_case.scenario_category == "missing_required_field"


def test_2_invalid_request_scenario_captures_deterministic_errors():
    result = generate_negative_test("missing_required_field", "0x22")
    assert "DID" in result.test_case.invalid_condition


def test_3_expected_nrc_included_when_supplied():
    nrc = UdsNrc(nrc="0x13", nrc_name="incorrectMessageLengthOrInvalidFormat", source=_source())
    result = generate_negative_test("missing_required_field", "0x22", expected_nrc=nrc)
    assert result.test_case.expected_nrc_known is True
    assert result.test_case.expected_negative_response.nrc == "0x13"


def test_4_missing_nrc_information_marked_unknown_not_guessed():
    result = generate_negative_test("missing_required_field", "0x22")
    assert result.test_case.expected_nrc_known is False
    assert result.test_case.expected_negative_response is None
    assert result.test_case.missing_info


def test_5_invalid_parameter_malformed_did():
    result = generate_negative_test("malformed_field", "0x22", did="not-a-did")
    assert result.success is True
    assert "Malformed DID" in result.test_case.invalid_condition


def test_6_invalid_did_rid_category():
    result = generate_negative_test("malformed_field", "0x31", subfunction_id="0x01", rid="bad")
    assert result.success is True
    assert "Malformed RID" in result.test_case.invalid_condition


def test_7_precondition_violation_scenario_without_deterministic_rejection():
    # Structurally valid request, but caller documents a precondition violation
    # (e.g. security access attempted without an active extended session).
    result = generate_negative_test(
        "precondition_violation", "0x27", subfunction_id="0x01",
        invalid_condition="SecurityAccess requested while ECU is in default session.",
        preconditions=["ECU in default session (not extended)"],
    )
    assert result.success is True
    assert "default session" in result.test_case.invalid_condition


def test_8_source_traceability_preserved():
    result = generate_negative_test("missing_required_field", "0x22", source=_source())
    assert result.test_case.source.chunk_id == "chunk-9"


def test_9_duplicate_prevention_in_suite():
    specs = [
        {"category": "missing_required_field", "service_id": "0x22"},
        {"category": "missing_required_field", "service_id": "0x22"},  # exact duplicate
        {"category": "malformed_field", "service_id": "0x22", "did": "bad"},
    ]
    results = generate_negative_suite(specs)
    successful_ids = [r.test_case.test_case_id for r in results if r.success]
    assert len(successful_ids) == len(set(successful_ids))  # no duplicate IDs kept
    assert len(results) == 2  # duplicate spec produced no second result entry


def test_10_integration_with_stage10_validation_category_requires_actual_rejection():
    # 0x22 with a valid DID is NOT actually rejected, so this category is invalid here.
    result = generate_negative_test("missing_required_field", "0x22", did="0xF190")
    assert result.success is False
    assert result.errors


def test_unsupported_category_rejected():
    result = generate_negative_test("not_a_real_category", "0x22")
    assert result.success is False


def test_stable_id_deterministic_across_calls():
    r1 = generate_negative_test("malformed_field", "0x22", did="bad")
    r2 = generate_negative_test("malformed_field", "0x22", did="bad")
    assert r1.test_case.test_case_id == r2.test_case.test_case_id
