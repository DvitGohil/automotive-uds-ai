"""Structured test-case representations shared by positive/negative generation."""
from dataclasses import asdict, dataclass, field

from app.uds.knowledge_model import SourceReference, UdsNegativeResponse, UdsPositiveResponse, UdsRequest


@dataclass
class PositiveTestCase:
    test_case_id: str
    title: str
    objective: str
    preconditions: list[str]
    request: UdsRequest
    expected_response: UdsPositiveResponse
    pass_criteria: list[str]
    fail_criteria: list[str]
    source: SourceReference | None = None
    is_complete: bool = True
    missing_info: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["request"] = self.request.to_dict()
        d["expected_response"] = self.expected_response.to_dict()
        d["source"] = self.source.to_dict() if self.source else None
        return d


@dataclass
class NegativeTestCase:
    test_case_id: str
    title: str
    objective: str
    scenario_category: str
    preconditions: list[str]
    invalid_condition: str
    request: UdsRequest | None
    expected_negative_response: UdsNegativeResponse | None
    expected_nrc_known: bool
    pass_criteria: list[str]
    fail_criteria: list[str]
    source: SourceReference | None = None
    missing_info: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["request"] = self.request.to_dict() if self.request else None
        d["expected_negative_response"] = (
            self.expected_negative_response.to_dict() if self.expected_negative_response else None
        )
        d["source"] = self.source.to_dict() if self.source else None
        return d


@dataclass
class TestGenerationResult:
    success: bool
    test_case: PositiveTestCase | NegativeTestCase | None = None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
