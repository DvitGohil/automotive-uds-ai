"""
Deterministic UDS request construction. Uses only a fixed, generic ISO 14229
service-ID registry (standardized service structure, not OEM-specific data)
plus caller-supplied input — never lets an LLM invent request bytes.

Any DID/RID/parameter semantics beyond "is this the right shape" must come
from the Stage 8 knowledge model / approved documents; this module does not
assert what a given DID means, only whether the request is well-formed for
the given service.
"""
import re
from dataclasses import dataclass, field

from app.uds.knowledge_model import SourceReference, UdsRequest

_HEX_BYTE_RE = re.compile(r"^0x[0-9A-Fa-f]{2}$")
_HEX_2BYTE_RE = re.compile(r"^0x[0-9A-Fa-f]{4}$")


@dataclass
class UdsServiceSpec:
    """Generic ISO 14229 service structure — not OEM-specific data."""

    service_id: str
    name: str
    requires_subfunction: bool = False
    requires_did: bool = False
    requires_rid: bool = False


# Standardized ISO 14229-1 service IDs. Structural shape only (which fields a
# request needs) — no OEM DID/RID/NRC values are represented here.
KNOWN_SERVICES: dict[str, UdsServiceSpec] = {
    "0x10": UdsServiceSpec("0x10", "DiagnosticSessionControl", requires_subfunction=True),
    "0x11": UdsServiceSpec("0x11", "ECUReset", requires_subfunction=True),
    "0x14": UdsServiceSpec("0x14", "ClearDiagnosticInformation"),
    "0x19": UdsServiceSpec("0x19", "ReadDTCInformation", requires_subfunction=True),
    "0x22": UdsServiceSpec("0x22", "ReadDataByIdentifier", requires_did=True),
    "0x27": UdsServiceSpec("0x27", "SecurityAccess", requires_subfunction=True),
    "0x2E": UdsServiceSpec("0x2E", "WriteDataByIdentifier", requires_did=True),
    "0x31": UdsServiceSpec("0x31", "RoutineControl", requires_subfunction=True, requires_rid=True),
    "0x3E": UdsServiceSpec("0x3E", "TesterPresent", requires_subfunction=True),
}


@dataclass
class RequestBuildResult:
    success: bool
    request: UdsRequest | None = None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    fields_used: dict = field(default_factory=dict)


def _hex_bytes_for(value: str) -> str:
    """Strip '0x'/spacing and return upper-case bytes, e.g. '0xF190' -> 'F1 90'."""
    digits = value[2:] if value.lower().startswith("0x") else value
    digits = digits.upper()
    return " ".join(digits[i : i + 2] for i in range(0, len(digits), 2))


def build_request(
    service_id: str,
    *,
    subfunction_id: str | None = None,
    did: str | None = None,
    rid: str | None = None,
    parameters: dict | None = None,
    source: SourceReference | None = None,
) -> RequestBuildResult:
    parameters = parameters or {}
    errors: list[str] = []
    warnings: list[str] = []

    if not service_id or not _HEX_BYTE_RE.match(service_id):
        errors.append(f"Invalid or malformed service ID: {service_id!r}. Expected format '0xNN'.")
        return RequestBuildResult(success=False, errors=errors)

    # Normalize case (e.g. "0x22" vs "0X22") without breaking the format check above.
    spec = KNOWN_SERVICES.get(_normalize_hex(service_id))
    if spec is None:
        errors.append(f"Unsupported service ID: {service_id}. Not present in the known UDS service registry.")
        return RequestBuildResult(success=False, errors=errors)

    fields_used = {"service_id": spec.service_id}

    if spec.requires_subfunction:
        if not subfunction_id:
            errors.append(f"Missing required subfunction for service {spec.name} ({spec.service_id}).")
        elif not _HEX_BYTE_RE.match(subfunction_id):
            errors.append(f"Malformed subfunction ID: {subfunction_id!r}. Expected format '0xNN'.")
        else:
            fields_used["subfunction_id"] = _normalize_hex(subfunction_id)
    elif subfunction_id:
        warnings.append(f"Subfunction {subfunction_id!r} supplied but service {spec.name} does not use one.")

    if spec.requires_did:
        if not did:
            errors.append(f"Missing required DID for service {spec.name} ({spec.service_id}).")
        elif not _HEX_2BYTE_RE.match(did):
            errors.append(f"Malformed DID: {did!r}. Expected format '0xNNNN'.")
        else:
            fields_used["did"] = _normalize_hex(did)
    elif did:
        warnings.append(f"DID {did!r} supplied but service {spec.name} does not use one.")

    if spec.requires_rid:
        if not rid:
            errors.append(f"Missing required RID for service {spec.name} ({spec.service_id}).")
        elif not _HEX_2BYTE_RE.match(rid):
            errors.append(f"Malformed RID: {rid!r}. Expected format '0xNNNN'.")
        else:
            fields_used["rid"] = _normalize_hex(rid)
    elif rid:
        warnings.append(f"RID {rid!r} supplied but service {spec.name} does not use one.")

    if errors:
        return RequestBuildResult(success=False, errors=errors, warnings=warnings, fields_used=fields_used)

    byte_parts = [_hex_bytes_for(spec.service_id)]
    if "subfunction_id" in fields_used:
        byte_parts.append(_hex_bytes_for(fields_used["subfunction_id"]))
    if "did" in fields_used:
        byte_parts.append(_hex_bytes_for(fields_used["did"]))
    if "rid" in fields_used:
        byte_parts.append(_hex_bytes_for(fields_used["rid"]))
    request_bytes = " ".join(byte_parts)

    request = UdsRequest(
        service_id=spec.service_id,
        subfunction_id=fields_used.get("subfunction_id"),
        did=fields_used.get("did"),
        rid=fields_used.get("rid"),
        parameters=parameters,
        request_bytes=request_bytes,
        source=source,
    )
    return RequestBuildResult(success=True, request=request, warnings=warnings, fields_used=fields_used)


def _normalize_hex(value: str) -> str:
    return "0x" + value[2:].upper() if value.lower().startswith("0x") else value
