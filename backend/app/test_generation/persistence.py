"""Persists generated positive/negative test cases through the existing TestCase table."""
import json

from sqlalchemy.orm import Session

from app.db.models import TestCase
from app.test_generation.models import NegativeTestCase, PositiveTestCase
from app.uds.knowledge_model import UdsNegativeResponse, UdsPositiveResponse, UdsRequest


def save_test_case(db: Session, project_id: str, case: PositiveTestCase | NegativeTestCase) -> TestCase:
    is_negative = isinstance(case, NegativeTestCase)
    row = TestCase(
        project_id=project_id,
        title=case.title,
        objective=case.objective,
        scenario_category=case.scenario_category if is_negative else None,
        invalid_condition=case.invalid_condition if is_negative else None,
        request_definition=json.dumps(case.request.to_dict()) if case.request else None,
        preconditions=json.dumps(case.preconditions),
        expected_response=json.dumps(
            case.expected_negative_response.to_dict() if is_negative else case.expected_response.to_dict()
        ) if (is_negative and case.expected_negative_response) or not is_negative else None,
        pass_criteria=json.dumps(case.pass_criteria),
        fail_criteria=json.dumps(case.fail_criteria),
        is_negative_case=is_negative,
        generated_by_ai=True,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def load_test_case(db: Session, test_case_row_id: str) -> PositiveTestCase | NegativeTestCase | None:
    """
    Reconstructs a PositiveTestCase/NegativeTestCase from a saved TestCase row,
    for chaining Stage 13 (response validation) / Stage 14 (templates) to an
    already-persisted, already-traceable test case rather than regenerating
    one from scratch. All fields saved by save_test_case() above — including
    objective, pass/fail criteria, and scenario_category — are restored.
    """
    row = db.query(TestCase).filter(TestCase.id == test_case_row_id).first()
    if row is None:
        return None

    request = UdsRequest.from_dict(json.loads(row.request_definition)) if row.request_definition else None
    preconditions = json.loads(row.preconditions) if row.preconditions else []
    pass_criteria = json.loads(row.pass_criteria) if row.pass_criteria else []
    fail_criteria = json.loads(row.fail_criteria) if row.fail_criteria else []
    source = request.source if request else None

    if row.is_negative_case:
        expected_negative = (
            UdsNegativeResponse.from_dict(json.loads(row.expected_response)) if row.expected_response else None
        )
        return NegativeTestCase(
            test_case_id=row.id,
            title=row.title,
            objective=row.objective or "",
            scenario_category=row.scenario_category or "",
            preconditions=preconditions,
            invalid_condition=row.invalid_condition or "",
            request=request,
            expected_negative_response=expected_negative,
            expected_nrc_known=expected_negative is not None,
            pass_criteria=pass_criteria,
            fail_criteria=fail_criteria,
            source=source,
        )

    expected_positive = (
        UdsPositiveResponse.from_dict(json.loads(row.expected_response)) if row.expected_response else None
    )
    return PositiveTestCase(
        test_case_id=row.id,
        title=row.title,
        objective=row.objective or "",
        preconditions=preconditions,
        request=request,
        expected_response=expected_positive,
        pass_criteria=pass_criteria,
        fail_criteria=fail_criteria,
        source=source,
    )

