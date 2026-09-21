"""
Negative UDS test-case generation. Reuses Stage 9/10 to establish what a
*valid* request would look like, then documents a specific, meaningful
deviation from it. Never asserts an NRC unless the caller supplies one
(sourced from Stage 8 knowledge / the approved document) — otherwise the
NRC is explicitly marked unknown, never guessed.
"""
import hashlib

from app.test_generation.models import NegativeTestCase, TestGenerationResult
from app.uds.knowledge_model import SourceReference, UdsNegativeResponse, UdsNrc
from app.uds.request_builder import build_request
from app.uds.request_validator import validate_request

NEGATIVE_RESPONSE_SID = "0x7F"

# Categories this generator knows how to construct meaningfully. Kept as an
# explicit allow-list so callers can't ask for an arbitrary/unsupported
# scenario shape.
SCENARIO_CATEGORIES = {
    "missing_required_field",
    "malformed_field",
    "unsupported_service",
    "precondition_violation",
    "security_violation",
    "documented_nrc",
}


def _stable_id(category: str, *parts) -> str:
    key = "|".join([category] + [str(p) for p in parts if p is not None])
    return f"NEG-{hashlib.sha256(key.encode()).hexdigest()[:10]}"


def generate_negative_test(
    category: str,
    service_id: str,
    *,
    subfunction_id: str | None = None,
    did: str | None = None,
    rid: str | None = None,
    parameters: dict | None = None,
    invalid_condition: str | None = None,
    expected_nrc: UdsNrc | None = None,
    preconditions: list[str] | None = None,
    source: SourceReference | None = None,
) -> TestGenerationResult:
    if category not in SCENARIO_CATEGORIES:
        return TestGenerationResult(
            success=False,
            errors=[f"Unsupported negative scenario category: {category!r}. Supported: {sorted(SCENARIO_CATEGORIES)}"],
        )

    preconditions = preconditions or []
    missing_info: list[str] = []

    # Attempt construction/validation of the (possibly invalid) inputs. Stage
    # 9/10 rejections *are* the deterministic evidence for structural
    # negative scenarios — we don't re-derive that logic here.
    build_result = build_request(
        service_id, subfunction_id=subfunction_id, did=did, rid=rid, parameters=parameters, source=source
    )

    if build_result.success:
        validation = validate_request(build_result.request)
        request = build_result.request if validation.valid else None
        deterministic_errors = [] if validation.valid else validation.errors
    else:
        request = None
        deterministic_errors = build_result.errors

    if category in {"missing_required_field", "malformed_field"} and not deterministic_errors:
        return TestGenerationResult(
            success=False,
            errors=[
                f"Category {category!r} requires the given inputs to actually be rejected by "
                "deterministic construction/validation, but they were accepted."
            ],
        )

    condition_description = invalid_condition or (
        "; ".join(deterministic_errors) if deterministic_errors else "Documented protocol/precondition violation."
    )

    if expected_nrc is not None:
        expected_response = UdsNegativeResponse(
            original_service_id=service_id,
            nrc=expected_nrc.nrc,
            negative_response_sid=NEGATIVE_RESPONSE_SID,
            description=expected_nrc.description or expected_nrc.nrc_name,
            source=expected_nrc.source or source,
        )
        nrc_known = True
    else:
        expected_response = None
        nrc_known = False
        missing_info.append(
            "Expected NRC not available from an approved source — left unset rather than assumed."
        )

    test_case_id = _stable_id(category, service_id, subfunction_id, did, rid, invalid_condition)
    service_label = service_id
    title = f"Negative test [{category}]: {service_label}"
    objective = f"Verify the ECU correctly rejects a request under the '{category}' scenario for {service_label}."

    pass_criteria = [f"ECU returns negative response (SID {NEGATIVE_RESPONSE_SID})"]
    if nrc_known:
        pass_criteria.append(f"Returned NRC equals {expected_response.nrc}")
    else:
        pass_criteria.append("Returned NRC is recorded for later mapping against approved documentation")
    fail_criteria = [
        "ECU returns a positive response",
        "ECU accepts and executes the invalid request",
    ]
    if nrc_known:
        fail_criteria.append(f"Returned NRC does not equal {expected_response.nrc}")

    test_case = NegativeTestCase(
        test_case_id=test_case_id,
        title=title,
        objective=objective,
        scenario_category=category,
        preconditions=preconditions,
        invalid_condition=condition_description,
        request=request,
        expected_negative_response=expected_response,
        expected_nrc_known=nrc_known,
        pass_criteria=pass_criteria,
        fail_criteria=fail_criteria,
        source=source,
        missing_info=missing_info,
    )

    return TestGenerationResult(success=True, test_case=test_case)


def generate_negative_suite(specs: list[dict]) -> list[TestGenerationResult]:
    """
    Generate multiple negative scenarios, deduplicating by stable test_case_id
    so re-running the same spec list never produces duplicate test cases.
    """
    results: list[TestGenerationResult] = []
    seen_ids: set[str] = set()
    for spec in specs:
        result = generate_negative_test(**spec)
        if result.success and result.test_case.test_case_id in seen_ids:
            continue
        if result.success:
            seen_ids.add(result.test_case.test_case_id)
        results.append(result)
    return results
