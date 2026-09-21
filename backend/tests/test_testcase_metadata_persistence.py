from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.db.models import Project
from app.test_generation.negative import generate_negative_test
from app.test_generation.persistence import load_test_case, save_test_case
from app.test_generation.positive import generate_positive_test
from app.uds.knowledge_model import SourceReference, UdsNrc

engine = create_engine("sqlite:///:memory:")
TestingSession = sessionmaker(bind=engine)


def setup_module(_module):
    Base.metadata.create_all(bind=engine)


def _seed_project(db):
    project = Project(name="Pilot")
    db.add(project)
    db.commit()
    return project.id


def test_1_create_positive_test_case():
    result = generate_positive_test("0x22", did="0xF190")
    assert result.success is True


def test_2_save_positive_test_case():
    db = TestingSession()
    try:
        project_id = _seed_project(db)
        case = generate_positive_test("0x22", did="0xF190").test_case
        row = save_test_case(db, project_id, case)
        assert row.id is not None
        assert row.objective == case.objective
    finally:
        db.close()


def test_3_reload_positive_test_case_preserves_all_fields():
    db = TestingSession()
    try:
        project_id = _seed_project(db)
        source = SourceReference(document_id="doc-1", document_name="ISO 14229", chunk_id="chunk-1")
        original = generate_positive_test(
            "0x22", did="0xF190", preconditions=["Default session active"], source=source
        ).test_case
        row = save_test_case(db, project_id, original)

        reloaded = load_test_case(db, row.id)
        assert reloaded is not None
        assert reloaded.title == original.title
        assert reloaded.objective == original.objective
        assert reloaded.preconditions == original.preconditions
        assert reloaded.pass_criteria == original.pass_criteria
        assert reloaded.fail_criteria == original.fail_criteria
        assert reloaded.request.did == original.request.did
        assert reloaded.expected_response.service_id == original.expected_response.service_id
        assert reloaded.source.chunk_id == "chunk-1"
    finally:
        db.close()


def test_4_verify_objective_preserved():
    db = TestingSession()
    try:
        project_id = _seed_project(db)
        case = generate_positive_test("0x10", subfunction_id="0x01").test_case
        row = save_test_case(db, project_id, case)
        reloaded = load_test_case(db, row.id)
        assert reloaded.objective == case.objective
        assert reloaded.objective != ""
    finally:
        db.close()


def test_5_verify_pass_criteria_preserved():
    db = TestingSession()
    try:
        project_id = _seed_project(db)
        case = generate_positive_test("0x22", did="0xF190").test_case
        row = save_test_case(db, project_id, case)
        reloaded = load_test_case(db, row.id)
        assert reloaded.pass_criteria == case.pass_criteria
        assert len(reloaded.pass_criteria) > 0
    finally:
        db.close()


def test_6_verify_fail_criteria_preserved():
    db = TestingSession()
    try:
        project_id = _seed_project(db)
        case = generate_positive_test("0x22", did="0xF190").test_case
        row = save_test_case(db, project_id, case)
        reloaded = load_test_case(db, row.id)
        assert reloaded.fail_criteria == case.fail_criteria
        assert len(reloaded.fail_criteria) > 0
    finally:
        db.close()


def test_7_verify_scenario_category_and_invalid_condition_preserved_for_negative():
    db = TestingSession()
    try:
        project_id = _seed_project(db)
        nrc = UdsNrc(nrc="0x22", nrc_name="conditionsNotCorrect")
        case = generate_negative_test(
            "precondition_violation", "0x27", subfunction_id="0x01",
            invalid_condition="Security access requested outside extended session.",
            expected_nrc=nrc,
        ).test_case
        row = save_test_case(db, project_id, case)
        assert row.scenario_category == "precondition_violation"
        assert "extended session" in row.invalid_condition

        reloaded = load_test_case(db, row.id)
        assert reloaded.scenario_category == "precondition_violation"
        assert "extended session" in reloaded.invalid_condition
        assert reloaded.expected_nrc_known is True
        assert reloaded.expected_negative_response.nrc == "0x22"
    finally:
        db.close()


def test_8_verify_traceability_fields_preserved():
    db = TestingSession()
    try:
        project_id = _seed_project(db)
        source = SourceReference(
            document_id="doc-9", document_name="ISO 14229", document_version=2,
            page_number=5, section_title="3.2", chunk_id="chunk-77",
        )
        case = generate_positive_test("0x22", did="0xF190", source=source).test_case
        row = save_test_case(db, project_id, case)
        reloaded = load_test_case(db, row.id)

        assert reloaded.source.document_id == "doc-9"
        assert reloaded.source.document_version == 2
        assert reloaded.source.page_number == 5
        assert reloaded.source.section_title == "3.2"
        assert reloaded.source.chunk_id == "chunk-77"
    finally:
        db.close()
