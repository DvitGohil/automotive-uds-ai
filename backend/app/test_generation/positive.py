"""
Positive UDS test-case generation. Reuses Stage 9 (request_builder) and
Stage 10 (request_validator) rather than duplicating their logic — a
positive test can only be generated from a request that construction and
deterministic validation both accept. Expected-response data values are
never guessed: supply them via `expected_response_parameters` when the
approved source documents them, otherwise they're marked missing/unknown.
"""
import hashlib

from app.test_generation.models import PositiveTestCase, TestGenerationResult
from app.uds.knowledge_model import SourceReference, UdsPositiveResponse
from app.uds.request_builder import build_request
from app.uds.request_validator import validate_request


def _positive_response_sid(service_id: str) -> str:
    """Generic ISO 14229 rule: positive response SID = request SID + 0x40."""
    return f"0x{int(service_id, 16) + 0x40:02X}"


def _stable_id(*parts) -> str:
    key = "|".join(str(p) for p in parts if p is not None)
    return f"POS-{hashlib.sha256(key.encode()).hexdigest()[:10]}"


def generate_positive_test(
    service_id: str,
    *,
    subfunction_id: str | None = None,
    did: str | None = None,
    rid: str | None = None,
    parameters: dict | None = None,
    expected_response_parameters: dict | None = None,
    preconditions: list[str] | None = None,
    requirement_reference: str | None = None,
    source: SourceReference | None = None,
) -> TestGenerationResult:
    preconditions = preconditions or []

    # Stage 9: deterministic request construction — never let this generator invent bytes.
    build_result = build_request(
        service_id,
        subfunction_id=subfunction_id,
        did=did,
        rid=rid,
        parameters=parameters,
        source=source,
    )
    if not build_result.success:
        return TestGenerationResult(success=False, errors=build_result.errors, warnings=build_result.warnings)

    # Stage 10: deterministic validation — authoritative gate before a test case exists.
    validation = validate_request(build_result.request)
    if not validation.valid:
        return TestGenerationResult(success=False, errors=validation.errors, warnings=validation.warnings)

    missing_info: list[str] = []
    response_parameters = dict(expected_response_parameters or {})

    # Echo structural fields into the expected response only when the service defines them.
    if build_result.request.subfunction_id:
        response_parameters.setdefault("subfunction_id", build_result.request.subfunction_id)
    if build_result.request.did:
        response_parameters.setdefault("did", build_result.request.did)
    if build_result.request.rid:
        response_parameters.setdefault("rid", build_result.request.rid)

    if expected_response_parameters is None:
        missing_info.append(
            "Expected response data value not available from an approved source — left unset rather than guessed."
        )

    expected_response = UdsPositiveResponse(
        service_id=_positive_response_sid(build_result.request.service_id),
        parameters=response_parameters,
        response_bytes=None,  # only the request byte layout is deterministic here; response payload is data-dependent
        source=source,
    )

    test_case_id = _stable_id(service_id, subfunction_id, did, rid)
    title = f"Positive test: {validation.service_info['service_name']} ({service_id})"
    objective = (
        f"Verify the ECU returns a positive response ({expected_response.service_id}) "
        f"for a well-formed {validation.service_info['service_name']} request."
    )

    pass_criteria = [
        f"ECU returns response with SID {expected_response.service_id}",
        f"Request transmitted matches constructed bytes: {build_result.request.request_bytes}",
    ]
    fail_criteria = [
        "ECU returns a negative response (0x7F)",
        "ECU returns no response within the diagnostic timeout",
        f"Response SID does not equal {expected_response.service_id}",
    ]

    test_case = PositiveTestCase(
        test_case_id=test_case_id,
        title=title,
        objective=objective,
        preconditions=preconditions,
        request=build_result.request,
        expected_response=expected_response,
        pass_criteria=pass_criteria,
        fail_criteria=fail_criteria,
        source=source,
        is_complete=expected_response_parameters is not None,
        missing_info=missing_info,
    )

    return TestGenerationResult(success=True, test_case=test_case, warnings=build_result.warnings)
