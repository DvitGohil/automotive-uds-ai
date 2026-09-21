"""
Automation-ready UDS test template generation. Builds a single, consistent
template shape from already-generated Stage 11/12 test cases — templates
never invent content; they restructure what Stage 8-12 already produced.
"""
import hashlib
from dataclasses import asdict, dataclass

from app.test_generation.models import NegativeTestCase, PositiveTestCase
from app.uds.knowledge_model import SourceReference


@dataclass
class AutomationTemplate:
    template_id: str
    test_case_id: str
    test_type: str  # "positive" | "negative"
    title: str
    objective: str
    preconditions: list[str]
    request: dict  # UdsRequest.to_dict()
    expected_response: dict | None  # UdsPositiveResponse or UdsNegativeResponse .to_dict()
    expected_nrc: str | None
    validation_conditions: list[str]
    pass_criteria: list[str]
    fail_criteria: list[str]
    source: dict | None
    requires_engineering_review: bool = True

    def to_dict(self) -> dict:
        return asdict(self)


def _stable_template_id(test_case_id: str) -> str:
    return f"TPL-{hashlib.sha256(test_case_id.encode()).hexdigest()[:10]}"


def generate_automation_template(test_case: PositiveTestCase | NegativeTestCase) -> AutomationTemplate:
    is_negative = isinstance(test_case, NegativeTestCase)

    if is_negative:
        validation_conditions = [f"Scenario category: {test_case.scenario_category}", test_case.invalid_condition]
        expected_response = (
            test_case.expected_negative_response.to_dict() if test_case.expected_negative_response else None
        )
        expected_nrc = test_case.expected_negative_response.nrc if test_case.expected_negative_response else None
        request_dict = test_case.request.to_dict() if test_case.request else None
    else:
        validation_conditions = [f"Expected response structurally matches {test_case.expected_response.service_id}."]
        expected_response = test_case.expected_response.to_dict()
        expected_nrc = None
        request_dict = test_case.request.to_dict()

    source: SourceReference | None = test_case.source

    return AutomationTemplate(
        template_id=_stable_template_id(test_case.test_case_id),
        test_case_id=test_case.test_case_id,
        test_type="negative" if is_negative else "positive",
        title=test_case.title,
        objective=test_case.objective,
        preconditions=test_case.preconditions,
        request=request_dict,
        expected_response=expected_response,
        expected_nrc=expected_nrc,
        validation_conditions=validation_conditions,
        pass_criteria=test_case.pass_criteria,
        fail_criteria=test_case.fail_criteria,
        source=source.to_dict() if source else None,
    )
