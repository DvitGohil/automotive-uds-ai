"""
REST API surface for the UDS engineering workflow. Routes are thin: they
validate input shape and delegate entirely to the existing service layer
(app.uds, app.test_generation, app.response_validation, app.automation) —
no business logic lives here.
"""
import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.audit.service import log_action
from app.automation.template_generator import generate_automation_template
from app.core.security import check_project_access, get_current_user, require_api_key, require_project_access
from app.db.database import get_db
from app.db.models import AuditRecord, TestCase, User, ValidationResult
from app.response_validation.ecu_validator import validate_ecu_response
from app.test_generation.negative import generate_negative_test
from app.test_generation.persistence import load_test_case, save_test_case
from app.test_generation.positive import generate_positive_test
from app.uds.repository import load_uds_entity
from app.uds.request_builder import build_request
from app.uds.request_validator import validate_request

router = APIRouter(prefix="/uds", tags=["uds"], dependencies=[Depends(require_api_key)])


# --- Schemas -----------------------------------------------------------

class RequestConstructIn(BaseModel):
    service_id: str = Field(max_length=8)
    subfunction_id: str | None = Field(default=None, max_length=8)
    did: str | None = Field(default=None, max_length=8)
    rid: str | None = Field(default=None, max_length=8)
    parameters: dict = {}
    project_id: str | None = Field(default=None, max_length=36)  # optional audit context


class PositiveTestIn(RequestConstructIn):
    expected_response_parameters: dict | None = None
    preconditions: list[str] = []
    project_id: str | None = Field(default=None, max_length=36)  # if set, persists the generated test case


class NegativeTestIn(BaseModel):
    category: str = Field(max_length=50)
    service_id: str = Field(max_length=8)
    subfunction_id: str | None = Field(default=None, max_length=8)
    did: str | None = Field(default=None, max_length=8)
    rid: str | None = Field(default=None, max_length=8)
    parameters: dict = {}
    invalid_condition: str | None = Field(default=None, max_length=2000)
    expected_nrc: str | None = Field(default=None, max_length=8)
    expected_nrc_name: str | None = Field(default=None, max_length=255)
    preconditions: list[str] = []
    project_id: str | None = Field(default=None, max_length=36)


class ResponseValidationIn(BaseModel):
    test_type: str | None = None  # "positive" | "negative" — required if test_case_row_id not given
    generation: PositiveTestIn | NegativeTestIn | None = None
    test_case_row_id: str | None = Field(default=None, max_length=36)
    actual_response: str = Field(max_length=1000)
    project_id: str | None = Field(default=None, max_length=36)  # if set (with test_case_row_id unset), persists the generated test case too


# --- UDS knowledge -------------------------------------------------------

@router.get("/knowledge/{document_version_id}/{unit_type}/{identifier}")
def get_uds_knowledge(document_version_id: str, unit_type: str, identifier: str, db: Session = Depends(get_db)):
    try:
        entity = load_uds_entity(db, document_version_id, unit_type, identifier)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if entity is None:
        raise HTTPException(status_code=404, detail="UDS knowledge entity not found")
    return entity.to_dict()


# --- Request construction / validation -----------------------------------

@router.post("/requests/construct")
def construct_request(payload: RequestConstructIn, db: Session = Depends(get_db)):
    result = build_request(
        payload.service_id,
        subfunction_id=payload.subfunction_id,
        did=payload.did,
        rid=payload.rid,
        parameters=payload.parameters,
    )
    log_action(
        db,
        action="request_constructed",
        project_id=payload.project_id,
        entity_type="uds_request",
        details={"service_id": payload.service_id, "success": result.success, "errors": result.errors},
    )
    return {
        "success": result.success,
        "request": result.request.to_dict() if result.request else None,
        "errors": result.errors,
        "warnings": result.warnings,
        "fields_used": result.fields_used,
    }


@router.post("/requests/validate")
def validate_uds_request(payload: RequestConstructIn, db: Session = Depends(get_db)):
    build_result = build_request(
        payload.service_id,
        subfunction_id=payload.subfunction_id,
        did=payload.did,
        rid=payload.rid,
        parameters=payload.parameters,
    )
    if not build_result.success:
        log_action(
            db, action="request_validated", project_id=payload.project_id,
            entity_type="uds_request", details={"valid": False, "errors": build_result.errors},
        )
        return {
            "valid": False,
            "errors": build_result.errors,
            "warnings": build_result.warnings,
            "service_info": None,
            "validated_fields": {},
            "request_representation": None,
            "explanation": "Request could not be constructed.",
        }
    validation = validate_request(build_result.request)
    log_action(
        db, action="request_validated", project_id=payload.project_id,
        entity_type="uds_request", details={"valid": validation.valid, "errors": validation.errors},
    )
    return {
        "valid": validation.valid,
        "errors": validation.errors,
        "warnings": validation.warnings,
        "service_info": validation.service_info,
        "validated_fields": validation.validated_fields,
        "request_representation": validation.request_representation,
        "explanation": validation.explanation,
    }


# --- Test generation / retrieval ------------------------------------------

@router.post("/tests/positive")
def create_positive_test(payload: PositiveTestIn, db: Session = Depends(get_db)):
    result = generate_positive_test(
        payload.service_id,
        subfunction_id=payload.subfunction_id,
        did=payload.did,
        rid=payload.rid,
        parameters=payload.parameters,
        expected_response_parameters=payload.expected_response_parameters,
        preconditions=payload.preconditions,
    )
    if not result.success:
        raise HTTPException(status_code=400, detail={"errors": result.errors, "warnings": result.warnings})

    row = None
    if payload.project_id:
        row = save_test_case(db, payload.project_id, result.test_case)

    log_action(
        db, action="positive_test_generated", project_id=payload.project_id,
        entity_type="test_case", entity_id=row.id if row else None,
        details={"test_case_id": result.test_case.test_case_id, "service_id": payload.service_id},
    )

    return {"test_case": result.test_case.to_dict(), "warnings": result.warnings, "test_case_row_id": row.id if row else None}


@router.post("/tests/negative")
def create_negative_test(payload: NegativeTestIn, db: Session = Depends(get_db)):
    from app.uds.knowledge_model import UdsNrc

    expected_nrc = None
    if payload.expected_nrc:
        expected_nrc = UdsNrc(nrc=payload.expected_nrc, nrc_name=payload.expected_nrc_name)

    result = generate_negative_test(
        payload.category,
        payload.service_id,
        subfunction_id=payload.subfunction_id,
        did=payload.did,
        rid=payload.rid,
        parameters=payload.parameters,
        invalid_condition=payload.invalid_condition,
        expected_nrc=expected_nrc,
        preconditions=payload.preconditions,
    )
    if not result.success:
        raise HTTPException(status_code=400, detail={"errors": result.errors})

    row = None
    if payload.project_id:
        row = save_test_case(db, payload.project_id, result.test_case)

    log_action(
        db, action="negative_test_generated", project_id=payload.project_id,
        entity_type="test_case", entity_id=row.id if row else None,
        details={"test_case_id": result.test_case.test_case_id, "category": payload.category},
    )

    return {"test_case": result.test_case.to_dict(), "test_case_row_id": row.id if row else None}


@router.get("/tests/{project_id}")
def list_tests(project_id: str, db: Session = Depends(get_db), _: None = Depends(require_project_access)):
    rows = db.query(TestCase).filter(TestCase.project_id == project_id).all()
    return [
        {
            "id": r.id,
            "title": r.title,
            "is_negative_case": r.is_negative_case,
            "review_status": r.review_status,
            "request_definition": r.request_definition,
            "preconditions": r.preconditions,
            "expected_response": r.expected_response,
        }
        for r in rows
    ]


# --- ECU response validation ----------------------------------------------

def _rebuild_test_case(payload: ResponseValidationIn, db: Session):
    if payload.test_case_row_id:
        test_case = load_test_case(db, payload.test_case_row_id)
        if test_case is None:
            raise HTTPException(status_code=404, detail="test_case_row_id not found")
        return test_case, None

    if payload.test_type == "positive":
        gen = payload.generation
        result = generate_positive_test(
            gen.service_id,
            subfunction_id=gen.subfunction_id,
            did=gen.did,
            rid=gen.rid,
            parameters=gen.parameters,
            expected_response_parameters=gen.expected_response_parameters,
            preconditions=gen.preconditions,
        )
    elif payload.test_type == "negative":
        from app.uds.knowledge_model import UdsNrc

        gen = payload.generation
        expected_nrc = UdsNrc(nrc=gen.expected_nrc, nrc_name=gen.expected_nrc_name) if gen.expected_nrc else None
        result = generate_negative_test(
            gen.category,
            gen.service_id,
            subfunction_id=gen.subfunction_id,
            did=gen.did,
            rid=gen.rid,
            parameters=gen.parameters,
            invalid_condition=gen.invalid_condition,
            expected_nrc=expected_nrc,
            preconditions=gen.preconditions,
        )
    else:
        raise HTTPException(status_code=400, detail="test_type must be 'positive' or 'negative', or supply test_case_row_id")

    if not result.success:
        raise HTTPException(status_code=400, detail={"errors": result.errors})

    row_id = None
    if payload.project_id:
        row = save_test_case(db, payload.project_id, result.test_case)
        row_id = row.id
    return result.test_case, row_id


@router.post("/response-validation")
def validate_response(payload: ResponseValidationIn, db: Session = Depends(get_db)):
    test_case, row_id = _rebuild_test_case(payload, db)
    if row_id is None:
        row_id = payload.test_case_row_id

    result = validate_ecu_response(test_case, payload.actual_response)

    validation_row = None
    if row_id:
        validation_row = ValidationResult(
            test_case_id=row_id,
            validation_type="ecu_response",
            passed=(result.status == "PASS"),
            details=json.dumps(
                {
                    "status": result.status,
                    "mismatch_details": result.mismatch_details,
                    "nrc": result.nrc,
                    "reason": result.reason,
                    "actual_response": result.actual_response,
                }
            ),
        )
        db.add(validation_row)
        db.commit()
        db.refresh(validation_row)

    log_action(
        db, action="ecu_response_validated", project_id=payload.project_id,
        entity_type="test_case", entity_id=row_id,
        details={"status": result.status, "test_case_id": result.test_case_id, "validation_result_id": validation_row.id if validation_row else None},
    )

    return {
        "status": result.status,
        "test_case_id": result.test_case_id,
        "test_case_row_id": row_id,
        "validation_result_id": validation_row.id if validation_row else None,
        "request_bytes": result.request_bytes,
        "expected_response_summary": result.expected_response_summary,
        "actual_response": result.actual_response,
        "response_type": result.response_type,
        "mismatch_details": result.mismatch_details,
        "nrc": result.nrc,
        "reason": result.reason,
    }


# --- Automation templates --------------------------------------------------

class TemplateFromRowIn(BaseModel):
    test_case_row_id: str
    project_id: str | None = None


@router.post("/automation-templates/positive")
def create_positive_template(payload: PositiveTestIn, db: Session = Depends(get_db)):
    result = generate_positive_test(
        payload.service_id,
        subfunction_id=payload.subfunction_id,
        did=payload.did,
        rid=payload.rid,
        parameters=payload.parameters,
        expected_response_parameters=payload.expected_response_parameters,
        preconditions=payload.preconditions,
    )
    if not result.success:
        raise HTTPException(status_code=400, detail={"errors": result.errors})
    template = generate_automation_template(result.test_case)
    log_action(
        db, action="automation_template_generated", project_id=payload.project_id,
        entity_type="automation_template", entity_id=None,
        details={"template_id": template.template_id, "test_case_id": template.test_case_id},
    )
    return template.to_dict()


@router.post("/automation-templates/negative")
def create_negative_template(payload: NegativeTestIn, db: Session = Depends(get_db)):
    from app.uds.knowledge_model import UdsNrc

    expected_nrc = UdsNrc(nrc=payload.expected_nrc, nrc_name=payload.expected_nrc_name) if payload.expected_nrc else None
    result = generate_negative_test(
        payload.category,
        payload.service_id,
        subfunction_id=payload.subfunction_id,
        did=payload.did,
        rid=payload.rid,
        parameters=payload.parameters,
        invalid_condition=payload.invalid_condition,
        expected_nrc=expected_nrc,
        preconditions=payload.preconditions,
    )
    if not result.success:
        raise HTTPException(status_code=400, detail={"errors": result.errors})
    template = generate_automation_template(result.test_case)
    log_action(
        db, action="automation_template_generated", project_id=payload.project_id,
        entity_type="automation_template", entity_id=None,
        details={"template_id": template.template_id, "test_case_id": template.test_case_id},
    )
    return template.to_dict()


@router.post("/automation-templates/from-test-case")
def create_template_from_saved_test_case(payload: TemplateFromRowIn, db: Session = Depends(get_db)):
    """Generates a template from an already-saved, already-validated test case row (traceability chain)."""
    test_case = load_test_case(db, payload.test_case_row_id)
    if test_case is None:
        raise HTTPException(status_code=404, detail="test_case_row_id not found")
    template = generate_automation_template(test_case)
    log_action(
        db, action="automation_template_generated", project_id=payload.project_id,
        entity_type="automation_template", entity_id=payload.test_case_row_id,
        details={"template_id": template.template_id, "test_case_row_id": payload.test_case_row_id},
    )
    return template.to_dict()


# --- Audit & traceability ---------------------------------------------------

@router.get("/audit/{project_id}")
def list_audit_records(project_id: str, db: Session = Depends(get_db), _: None = Depends(require_project_access)):
    rows = db.query(AuditRecord).filter(AuditRecord.project_id == project_id).order_by(AuditRecord.created_at.desc()).all()
    return [
        {
            "id": r.id,
            "action": r.action,
            "entity_type": r.entity_type,
            "entity_id": r.entity_id,
            "details": json.loads(r.details) if r.details else None,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]


@router.get("/traceability/test-case/{test_case_row_id}")
def get_test_case_traceability(
    test_case_row_id: str, current_user: User | None = Depends(get_current_user), db: Session = Depends(get_db)
):
    row = db.query(TestCase).filter(TestCase.id == test_case_row_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="test_case_row_id not found")

    check_project_access(db, row.project_id, current_user)

    request_data = json.loads(row.request_definition) if row.request_definition else None
    expected_data = json.loads(row.expected_response) if row.expected_response else None
    source = (request_data or {}).get("source")

    audit_trail = (
        db.query(AuditRecord)
        .filter(AuditRecord.entity_type == "test_case", AuditRecord.entity_id == test_case_row_id)
        .order_by(AuditRecord.created_at.asc())
        .all()
    )
    validation_results = (
        db.query(ValidationResult).filter(ValidationResult.test_case_id == test_case_row_id).all()
    )

    return {
        "test_case": {
            "id": row.id,
            "project_id": row.project_id,
            "title": row.title,
            "is_negative_case": row.is_negative_case,
            "review_status": row.review_status,
        },
        "source": source,  # document_id, document_name, document_version, page_number, section_title, chunk_id
        "request": request_data,
        "expected_response": expected_data,
        "audit_trail": [
            {
                "id": a.id,
                "action": a.action,
                "created_at": a.created_at.isoformat(),
                "details": json.loads(a.details) if a.details else None,
            }
            for a in audit_trail
        ],
        "validation_results": [
            {
                "id": v.id,
                "validation_type": v.validation_type,
                "passed": v.passed,
                "details": json.loads(v.details) if v.details else None,
                "created_at": v.created_at.isoformat(),
            }
            for v in validation_results
        ],
    }
