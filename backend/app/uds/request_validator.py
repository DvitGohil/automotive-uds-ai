"""
Deterministic validation of a UdsRequest. Reuses the Stage 9 service
registry — no LLM involved in the pass/fail decision. An LLM may later
explain a result in prose, but never decides validity.
"""
from dataclasses import dataclass, field

from app.uds.knowledge_model import SourceReference, UdsRequest
from app.uds.request_builder import KNOWN_SERVICES, _HEX_2BYTE_RE, _HEX_BYTE_RE, _hex_bytes_for, _normalize_hex


@dataclass
class ValidationResult:
    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    service_info: dict | None = None
    validated_fields: dict = field(default_factory=dict)
    request_representation: str | None = None
    source: SourceReference | None = None
    explanation: str = ""


def validate_request(request: UdsRequest) -> ValidationResult:
    errors: list[str] = []
    warnings: list[str] = []
    validated_fields: dict = {}

    # --- Service validation -------------------------------------------------
    if not request.service_id or not _HEX_BYTE_RE.match(request.service_id):
        errors.append(f"Invalid service ID format: {request.service_id!r}. Expected '0xNN'.")
        return ValidationResult(
            valid=False,
            errors=errors,
            source=request.source,
            explanation="Service ID failed basic format validation before any further checks could run.",
        )

    spec = KNOWN_SERVICES.get(_normalize_hex(request.service_id))
    if spec is None:
        errors.append(f"Service {request.service_id} is not supported by the known UDS service registry.")
        return ValidationResult(
            valid=False,
            errors=errors,
            source=request.source,
            explanation="Service is not recognized, so no further structural validation is possible.",
        )
    validated_fields["service_id"] = spec.service_id
    service_info = {"service_id": spec.service_id, "service_name": spec.name}

    # --- Subfunction validation ----------------------------------------------
    if spec.requires_subfunction:
        if not request.subfunction_id:
            errors.append(f"Missing required subfunction for service {spec.name} ({spec.service_id}).")
        elif not _HEX_BYTE_RE.match(request.subfunction_id):
            errors.append(f"Malformed subfunction ID: {request.subfunction_id!r}. Expected '0xNN'.")
        else:
            validated_fields["subfunction_id"] = _normalize_hex(request.subfunction_id)
    elif request.subfunction_id:
        warnings.append(f"Subfunction supplied but service {spec.name} does not define one for this operation.")

    # --- DID validation --------------------------------------------------------
    if spec.requires_did:
        if not request.did:
            errors.append(f"Missing required DID for service {spec.name} ({spec.service_id}).")
        elif not _HEX_2BYTE_RE.match(request.did):
            errors.append(f"Malformed DID: {request.did!r}. Expected '0xNNNN' (2 bytes).")
        else:
            validated_fields["did"] = _normalize_hex(request.did)
    elif request.did:
        warnings.append(f"DID supplied but service {spec.name} does not use one.")

    # --- RID validation --------------------------------------------------------
    if spec.requires_rid:
        if not request.rid:
            errors.append(f"Missing required RID for service {spec.name} ({spec.service_id}).")
        elif not _HEX_2BYTE_RE.match(request.rid):
            errors.append(f"Malformed RID: {request.rid!r}. Expected '0xNNNN' (2 bytes).")
        else:
            validated_fields["rid"] = _normalize_hex(request.rid)
    elif request.rid:
        warnings.append(f"RID supplied but service {spec.name} does not use one.")

    if errors:
        return ValidationResult(
            valid=False,
            errors=errors,
            warnings=warnings,
            service_info=service_info,
            validated_fields=validated_fields,
            source=request.source,
            explanation="Required fields for this service are missing or malformed.",
        )

    # --- Request structure / byte-representation consistency -------------------
    expected_parts = [_hex_bytes_for(spec.service_id)]
    if "subfunction_id" in validated_fields:
        expected_parts.append(_hex_bytes_for(validated_fields["subfunction_id"]))
    if "did" in validated_fields:
        expected_parts.append(_hex_bytes_for(validated_fields["did"]))
    if "rid" in validated_fields:
        expected_parts.append(_hex_bytes_for(validated_fields["rid"]))
    expected_bytes = " ".join(expected_parts)

    if request.request_bytes is not None and request.request_bytes != expected_bytes:
        errors.append(
            f"Request byte representation is inconsistent with its fields: "
            f"got {request.request_bytes!r}, expected {expected_bytes!r}."
        )
        return ValidationResult(
            valid=False,
            errors=errors,
            warnings=warnings,
            service_info=service_info,
            validated_fields=validated_fields,
            request_representation=request.request_bytes,
            source=request.source,
            explanation="Field ordering/content does not match the request's declared byte representation.",
        )

    if not request.source:
        warnings.append("Request has no source reference — traceability to an approved document is incomplete.")

    return ValidationResult(
        valid=True,
        errors=[],
        warnings=warnings,
        service_info=service_info,
        validated_fields=validated_fields,
        request_representation=expected_bytes,
        source=request.source,
        explanation=f"Request for {spec.name} ({spec.service_id}) is structurally valid.",
    )
