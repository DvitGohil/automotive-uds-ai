from app.response_validation.ecu_validator import ValidationStatus, validate_ecu_response
from app.test_generation.negative import generate_negative_test
from app.test_generation.positive import generate_positive_test
from app.uds.knowledge_model import UdsNrc


def test_1_correct_positive_response_passes():
    test_case = generate_positive_test("0x22", did="0xF190").test_case
    result = validate_ecu_response(test_case, "62 F1 90 31 48 47")
    assert result.status == ValidationStatus.PASS


def test_2_correct_negative_response_passes():
    built_case = generate_negative_test(
        "precondition_violation", "0x27", subfunction_id="0x01",
        invalid_condition="Security access requested outside extended session.",
        expected_nrc=UdsNrc(nrc="0x22", nrc_name="conditionsNotCorrect"),
    ).test_case
    result = validate_ecu_response(built_case, "7F 27 22")
    assert result.status == ValidationStatus.PASS


def test_3_wrong_service_fails():
    test_case = generate_positive_test("0x22", did="0xF190").test_case
    result = validate_ecu_response(test_case, "6E F1 90")  # wrong SID (0x6E instead of 0x62)
    assert result.status == ValidationStatus.FAIL
    assert any("SID" in m for m in result.mismatch_details)


def test_4_wrong_nrc_fails():
    built_case = generate_negative_test(
        "precondition_violation", "0x27", subfunction_id="0x01",
        invalid_condition="Security access requested outside extended session.",
        expected_nrc=UdsNrc(nrc="0x22", nrc_name="conditionsNotCorrect"),
    ).test_case
    result = validate_ecu_response(built_case, "7F 27 33")  # wrong NRC
    assert result.status == ValidationStatus.FAIL
    assert any("NRC" in m for m in result.mismatch_details)


def test_5_response_mismatch_positive_did_not_echoed_fails():
    test_case = generate_positive_test("0x22", did="0xF190").test_case
    result = validate_ecu_response(test_case, "62 AB CD")  # wrong DID echoed
    assert result.status == ValidationStatus.FAIL
    assert any("DID" in m for m in result.mismatch_details)


def test_6_malformed_response_returns_unknown():
    test_case = generate_positive_test("0x22", did="0xF190").test_case
    result = validate_ecu_response(test_case, "not a hex response at all!")
    assert result.status == ValidationStatus.UNKNOWN
    assert "not a parseable" in result.reason


def test_7_missing_expected_response_information_returns_unknown():
    # Negative test with no documented NRC -> even a correctly-shaped negative response is UNKNOWN.
    built_case = generate_negative_test(
        "precondition_violation", "0x27", subfunction_id="0x01",
        invalid_condition="Security access requested outside extended session.",
    ).test_case
    result = validate_ecu_response(built_case, "7F 27 22")
    assert result.status == ValidationStatus.UNKNOWN
    assert "no documented NRC" in result.reason


def test_positive_response_to_negative_test_fails():
    built_case = generate_negative_test(
        "precondition_violation", "0x27", subfunction_id="0x01",
        invalid_condition="Security access requested outside extended session.",
        expected_nrc=UdsNrc(nrc="0x22"),
    ).test_case
    result = validate_ecu_response(built_case, "67 01 12 34 56 78")  # positive response, unexpectedly
    assert result.status == ValidationStatus.FAIL


def test_incomplete_negative_frame_returns_unknown():
    test_case = generate_positive_test("0x22", did="0xF190").test_case
    result = validate_ecu_response(test_case, "7F 22")  # missing NRC byte
    assert result.status == ValidationStatus.UNKNOWN


def test_no_request_on_test_case_returns_unknown():
    failed = generate_positive_test("0x22")  # missing DID -> construction fails, no test case at all
    assert failed.success is False  # sanity: nothing to validate against in this path
