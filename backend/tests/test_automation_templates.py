from app.automation.template_generator import generate_automation_template
from app.test_generation.negative import generate_negative_test
from app.test_generation.positive import generate_positive_test
from app.uds.knowledge_model import SourceReference, UdsNrc


def test_positive_template_generation_required_fields():
    test_case = generate_positive_test(
        "0x22", did="0xF190", source=SourceReference(document_id="doc-1", chunk_id="chunk-1")
    ).test_case
    template = generate_automation_template(test_case)

    assert template.test_type == "positive"
    assert template.test_case_id == test_case.test_case_id
    assert template.request["service_id"] == "0x22"
    assert template.expected_response["service_id"] == "0x62"
    assert template.pass_criteria
    assert template.fail_criteria
    assert template.requires_engineering_review is True


def test_negative_template_generation_required_fields():
    nrc = UdsNrc(nrc="0x22", nrc_name="conditionsNotCorrect")
    test_case = generate_negative_test(
        "precondition_violation", "0x27", subfunction_id="0x01",
        invalid_condition="Security access without extended session.",
        expected_nrc=nrc,
    ).test_case
    template = generate_automation_template(test_case)

    assert template.test_type == "negative"
    assert template.expected_nrc == "0x22"
    assert "Security access without extended session." in template.validation_conditions


def test_template_traceability_preserved():
    source = SourceReference(document_id="doc-1", document_name="ISO 14229", chunk_id="chunk-9")
    test_case = generate_positive_test("0x22", did="0xF190", source=source).test_case
    template = generate_automation_template(test_case)
    assert template.source["chunk_id"] == "chunk-9"


def test_template_deterministic_structure_stable_id():
    test_case = generate_positive_test("0x22", did="0xF190").test_case
    t1 = generate_automation_template(test_case)
    t2 = generate_automation_template(test_case)
    assert t1.template_id == t2.template_id


def test_negative_template_with_unknown_nrc_leaves_it_none():
    test_case = generate_negative_test(
        "precondition_violation", "0x27", subfunction_id="0x01",
        invalid_condition="Security access without extended session.",
    ).test_case
    template = generate_automation_template(test_case)
    assert template.expected_nrc is None
    assert template.expected_response is None
