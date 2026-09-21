"""
Deterministic ECU response validation. Compares a UDS request + its expected
response (Stage 11/12 output) against an actual raw ECU response, and
produces a structured PASS/FAIL/UNKNOWN result. The pass/fail decision is
pure application logic — no LLM involved. Never invents NRC meanings or ECU
behavior: anything not already known from the project (Stage 8/9/10/11/12)
is reported as UNKNOWN with a clear reason, not guessed.
"""
import re
from dataclasses import dataclass, field
from enum import Enum

from app.test_generation.models import NegativeTestCase, PositiveTestCase
from app.uds.knowledge_model import SourceReference

_HEX_TOKEN_RE = re.compile(r"^[0-9A-Fa-f]{2}$")


class ValidationStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"


class ResponseType(str, Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    MALFORMED = "malformed"
    INCOMPLETE = "incomplete"
    UNEXPECTED = "unexpected"


@dataclass
class ParsedResponse:
    raw: str
    response_type: ResponseType
    service_id: str | None = None  # SID byte, e.g. "0x62" or "0x7F"
    original_service_id: str | None = None  # for negative responses, the echoed original SID
    nrc: str | None = None
    data_bytes: list[str] = field(default_factory=list)  # remaining bytes after SID (+orig SID/NRC)


@dataclass
class EcuValidationResult:
    status: ValidationStatus
    test_case_id: str | None
    request_bytes: str | None
    expected_response_summary: str | None
    actual_response: str | None
    parsed_response: ParsedResponse | None
    response_type: ResponseType | None
    mismatch_details: list[str] = field(default_factory=list)
    nrc: str | None = None
    reason: str = ""
    source: SourceReference | None = None


def parse_ecu_response(raw_response: str) -> ParsedResponse | None:
    """
    Parse a raw hex ECU response (e.g. "62 F1 90 31 48 47"). Returns None if
    the input isn't parseable as a byte sequence at all (caller reports
    MALFORMED in that case) — this function never guesses meaning beyond
    generic ISO 14229 response-frame structure (SID byte, optional negative
    0x7F + original SID + NRC).
    """
    if not raw_response or not raw_response.strip():
        return None

    tokens = raw_response.strip().split()
    if not tokens or not all(_HEX_TOKEN_RE.match(t) for t in tokens):
        return None

    upper = [t.upper() for t in tokens]
    sid = f"0x{upper[0]}"

    if upper[0] == "7F":
        if len(upper) < 3:
            return ParsedResponse(raw=raw_response, response_type=ResponseType.INCOMPLETE, service_id=sid)
        return ParsedResponse(
            raw=raw_response,
            response_type=ResponseType.NEGATIVE,
            service_id=sid,
            original_service_id=f"0x{upper[1]}",
            nrc=f"0x{upper[2]}",
            data_bytes=upper[3:],
        )

    return ParsedResponse(
        raw=raw_response,
        response_type=ResponseType.POSITIVE,
        service_id=sid,
        data_bytes=upper[1:],
    )


def validate_ecu_response(
    test_case: PositiveTestCase | NegativeTestCase,
    actual_response: str,
) -> EcuValidationResult:
    request = test_case.request
    request_bytes = request.request_bytes if request else None
    source = test_case.source

    if request is None:
        return EcuValidationResult(
            status=ValidationStatus.UNKNOWN,
            test_case_id=test_case.test_case_id,
            request_bytes=None,
            expected_response_summary=None,
            actual_response=actual_response,
            parsed_response=None,
            response_type=None,
            reason="Test case has no constructed request (construction/validation failed upstream); "
            "cannot compare an actual response against nothing.",
            source=source,
        )

    parsed = parse_ecu_response(actual_response)
    if parsed is None:
        return EcuValidationResult(
            status=ValidationStatus.UNKNOWN,
            test_case_id=test_case.test_case_id,
            request_bytes=request_bytes,
            expected_response_summary=_expected_summary(test_case),
            actual_response=actual_response,
            parsed_response=None,
            response_type=ResponseType.MALFORMED,
            reason="Actual response is not a parseable hex byte sequence.",
            source=source,
        )

    if parsed.response_type == ResponseType.INCOMPLETE:
        return EcuValidationResult(
            status=ValidationStatus.UNKNOWN,
            test_case_id=test_case.test_case_id,
            request_bytes=request_bytes,
            expected_response_summary=_expected_summary(test_case),
            actual_response=actual_response,
            parsed_response=parsed,
            response_type=ResponseType.INCOMPLETE,
            reason="Negative response frame (0x7F) is missing its original-SID and/or NRC bytes.",
            source=source,
        )

    if isinstance(test_case, PositiveTestCase):
        return _validate_against_positive(test_case, parsed, actual_response, source)
    return _validate_against_negative(test_case, parsed, actual_response, source)


def _expected_summary(test_case: PositiveTestCase | NegativeTestCase) -> str | None:
    if isinstance(test_case, PositiveTestCase):
        return f"Positive response {test_case.expected_response.service_id}"
    if test_case.expected_negative_response:
        return f"Negative response 0x7F, original SID {test_case.request.service_id}, NRC {test_case.expected_negative_response.nrc}"
    return "Negative response expected (exact NRC not documented)"


def _validate_against_positive(
    test_case: PositiveTestCase, parsed: ParsedResponse, raw: str, source: SourceReference | None
) -> EcuValidationResult:
    expected = test_case.expected_response
    mismatches: list[str] = []

    if parsed.response_type == ResponseType.NEGATIVE:
        return EcuValidationResult(
            status=ValidationStatus.FAIL,
            test_case_id=test_case.test_case_id,
            request_bytes=test_case.request.request_bytes,
            expected_response_summary=_expected_summary(test_case),
            actual_response=raw,
            parsed_response=parsed,
            response_type=ResponseType.NEGATIVE,
            nrc=parsed.nrc,
            mismatch_details=[f"Expected positive response {expected.service_id}, got negative response (NRC {parsed.nrc})."],
            reason="ECU rejected a request that was expected to succeed.",
            source=source,
        )

    if parsed.service_id != expected.service_id:
        mismatches.append(f"Expected SID {expected.service_id}, got {parsed.service_id}.")

    # Structural echo checks only for fields we actually have an expectation for.
    if "did" in expected.parameters:
        expected_did_bytes = expected.parameters["did"][2:].upper()
        if len(parsed.data_bytes) < 2 or "".join(parsed.data_bytes[:2]) != expected_did_bytes:
            mismatches.append(f"Expected DID {expected.parameters['did']} not echoed in response data.")

    if mismatches:
        return EcuValidationResult(
            status=ValidationStatus.FAIL,
            test_case_id=test_case.test_case_id,
            request_bytes=test_case.request.request_bytes,
            expected_response_summary=_expected_summary(test_case),
            actual_response=raw,
            parsed_response=parsed,
            response_type=ResponseType.UNEXPECTED,
            mismatch_details=mismatches,
            reason="Actual response does not structurally match the expected positive response.",
            source=source,
        )

    return EcuValidationResult(
        status=ValidationStatus.PASS,
        test_case_id=test_case.test_case_id,
        request_bytes=test_case.request.request_bytes,
        expected_response_summary=_expected_summary(test_case),
        actual_response=raw,
        parsed_response=parsed,
        response_type=ResponseType.POSITIVE,
        reason="Actual response matches the expected positive response structure.",
        source=source,
    )


def _validate_against_negative(
    test_case: NegativeTestCase, parsed: ParsedResponse, raw: str, source: SourceReference | None
) -> EcuValidationResult:
    if parsed.response_type == ResponseType.POSITIVE:
        return EcuValidationResult(
            status=ValidationStatus.FAIL,
            test_case_id=test_case.test_case_id,
            request_bytes=test_case.request.request_bytes if test_case.request else None,
            expected_response_summary=_expected_summary(test_case),
            actual_response=raw,
            parsed_response=parsed,
            response_type=ResponseType.POSITIVE,
            mismatch_details=["Expected a negative response (0x7F), but ECU returned a positive response."],
            reason="ECU accepted a request that was expected to be rejected.",
            source=source,
        )

    mismatches: list[str] = []
    expected_original_sid = test_case.request.service_id if test_case.request else None
    if expected_original_sid and parsed.original_service_id != expected_original_sid:
        mismatches.append(
            f"Negative response echoes original SID {parsed.original_service_id}, expected {expected_original_sid}."
        )

    if not test_case.expected_nrc_known:
        # We never documented the expected NRC — can't judge correctness beyond "it was negative".
        return EcuValidationResult(
            status=ValidationStatus.UNKNOWN,
            test_case_id=test_case.test_case_id,
            request_bytes=test_case.request.request_bytes if test_case.request else None,
            expected_response_summary=_expected_summary(test_case),
            actual_response=raw,
            parsed_response=parsed,
            response_type=ResponseType.NEGATIVE,
            nrc=parsed.nrc,
            mismatch_details=mismatches,
            reason="ECU returned a negative response as expected, but no documented NRC was available to "
            "confirm it is the *correct* NRC for this condition.",
            source=source,
        )

    expected_nrc = test_case.expected_negative_response.nrc
    if parsed.nrc != expected_nrc:
        mismatches.append(f"Expected NRC {expected_nrc}, got {parsed.nrc}.")

    if mismatches:
        return EcuValidationResult(
            status=ValidationStatus.FAIL,
            test_case_id=test_case.test_case_id,
            request_bytes=test_case.request.request_bytes if test_case.request else None,
            expected_response_summary=_expected_summary(test_case),
            actual_response=raw,
            parsed_response=parsed,
            response_type=ResponseType.NEGATIVE,
            nrc=parsed.nrc,
            mismatch_details=mismatches,
            reason="Negative response received, but does not match the documented expected NRC/original SID.",
            source=source,
        )

    return EcuValidationResult(
        status=ValidationStatus.PASS,
        test_case_id=test_case.test_case_id,
        request_bytes=test_case.request.request_bytes if test_case.request else None,
        expected_response_summary=_expected_summary(test_case),
        actual_response=raw,
        parsed_response=parsed,
        response_type=ResponseType.NEGATIVE,
        nrc=parsed.nrc,
        reason="Actual negative response matches the documented expected NRC and original SID.",
        source=source,
    )
