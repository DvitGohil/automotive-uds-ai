from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.db.models import Project, TestCase
from app.test_generation.negative import generate_negative_test
from app.test_generation.persistence import save_test_case
from app.test_generation.positive import generate_positive_test

engine = create_engine("sqlite:///:memory:")
TestingSession = sessionmaker(bind=engine)


def setup_module(_module):
    Base.metadata.create_all(bind=engine)


def test_save_positive_and_negative_test_cases_via_existing_table():
    db = TestingSession()
    try:
        project = Project(name="Pilot")
        db.add(project)
        db.commit()

        positive = generate_positive_test("0x22", did="0xF190").test_case
        negative = generate_negative_test("missing_required_field", "0x22").test_case

        save_test_case(db, project.id, positive)
        save_test_case(db, project.id, negative)

        rows = db.query(TestCase).filter_by(project_id=project.id).all()
        assert len(rows) == 2
        assert any(r.is_negative_case is False and r.generated_by_ai is True for r in rows)
        assert any(r.is_negative_case is True for r in rows)
    finally:
        db.close()
