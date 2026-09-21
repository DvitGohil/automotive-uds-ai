from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.database import Base, get_db
from app.db.models import Project
from app.main import app

engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSession = sessionmaker(bind=engine)


def setup_module(_module):
    Base.metadata.create_all(bind=engine)

    def _override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_get_db


def teardown_module(_module):
    app.dependency_overrides.clear()


client = TestClient(app)


def _seed_project():
    db = TestingSession()
    project = Project(name="Pilot")
    db.add(project)
    db.commit()
    project_id = project.id
    db.close()
    return project_id


def test_1_audit_record_created_on_test_generation():
    project_id = _seed_project()
    client.post("/api/v1/uds/tests/positive", json={"service_id": "0x22", "did": "0xF190", "project_id": project_id})

    audit = client.get(f"/api/v1/uds/audit/{project_id}").json()
    assert any(a["action"] == "positive_test_generated" for a in audit)


def test_2_audit_record_retrieval_ordering_and_shape():
    project_id = _seed_project()
    client.post("/api/v1/uds/requests/construct", json={"service_id": "0x22", "did": "0xF190", "project_id": project_id})
    client.post("/api/v1/uds/requests/validate", json={"service_id": "0x22", "did": "0xF190", "project_id": project_id})

    audit = client.get(f"/api/v1/uds/audit/{project_id}").json()
    assert len(audit) == 2
    for record in audit:
        assert "id" in record and "action" in record and "created_at" in record


def test_3_traceability_preserved_document_to_test_case():
    project_id = _seed_project()
    resp = client.post(
        "/api/v1/uds/tests/positive",
        json={"service_id": "0x22", "did": "0xF190", "project_id": project_id},
    )
    row_id = resp.json()["test_case_row_id"]

    trace = client.get(f"/api/v1/uds/traceability/test-case/{row_id}").json()
    assert trace["test_case"]["id"] == row_id
    assert trace["request"]["did"] == "0xF190"


def test_4_source_to_test_traceability_with_source_reference():
    project_id = _seed_project()
    resp = client.post(
        "/api/v1/uds/tests/positive",
        json={"service_id": "0x22", "did": "0xF190", "project_id": project_id},
    )
    row_id = resp.json()["test_case_row_id"]
    trace = client.get(f"/api/v1/uds/traceability/test-case/{row_id}").json()
    # No source was supplied on construction here, so it's correctly None — not invented.
    assert trace["source"] is None


def test_5_test_to_validation_traceability():
    project_id = _seed_project()
    gen_resp = client.post(
        "/api/v1/uds/tests/positive",
        json={"service_id": "0x22", "did": "0xF190", "project_id": project_id},
    )
    row_id = gen_resp.json()["test_case_row_id"]

    val_resp = client.post(
        "/api/v1/uds/response-validation",
        json={"test_case_row_id": row_id, "actual_response": "62 F1 90 31 48 47"},
    )
    assert val_resp.status_code == 200
    assert val_resp.json()["status"] == "PASS"
    assert val_resp.json()["test_case_row_id"] == row_id

    trace = client.get(f"/api/v1/uds/traceability/test-case/{row_id}").json()
    assert len(trace["validation_results"]) == 1
    assert trace["validation_results"][0]["passed"] is True


def test_6_validation_to_template_traceability():
    project_id = _seed_project()
    gen_resp = client.post(
        "/api/v1/uds/tests/positive",
        json={"service_id": "0x22", "did": "0xF190", "project_id": project_id},
    )
    row_id = gen_resp.json()["test_case_row_id"]
    client.post("/api/v1/uds/response-validation", json={"test_case_row_id": row_id, "actual_response": "62 F1 90 31 48 47"})

    template_resp = client.post(
        "/api/v1/uds/automation-templates/from-test-case",
        json={"test_case_row_id": row_id, "project_id": project_id},
    )
    assert template_resp.status_code == 200
    assert template_resp.json()["test_case_id"] == row_id

    audit = client.get(f"/api/v1/uds/audit/{project_id}").json()
    assert any(a["action"] == "automation_template_generated" for a in audit)


def test_7_unauthorized_audit_access_when_auth_configured(monkeypatch):
    from app.core.auth import hash_password
    from app.core.config import settings
    from app.db.models import ProjectMember, User

    monkeypatch.setattr(settings, "JWT_SECRET", "test-secret")
    project_id = _seed_project()

    resp = client.get(f"/api/v1/uds/audit/{project_id}")
    assert resp.status_code == 401  # no token at all

    db = TestingSession()
    user = User(email="eng-audit-test@example.com", full_name="Engineer", password_hash=hash_password("pw123456"))
    outsider = User(email="outsider-audit-test@example.com", full_name="Outsider", password_hash=hash_password("pw123456"))
    db.add_all([user, outsider])
    db.flush()
    db.add(ProjectMember(project_id=project_id, user_id=user.id))
    db.commit()
    db.close()

    outsider_token = client.post(
        "/api/v1/auth/login", json={"email": "outsider-audit-test@example.com", "password": "pw123456"}
    ).json()["access_token"]
    resp_not_member = client.get(
        f"/api/v1/uds/audit/{project_id}", headers={"Authorization": f"Bearer {outsider_token}"}
    )
    assert resp_not_member.status_code == 403  # authenticated, but not a project member

    member_token = client.post(
        "/api/v1/auth/login", json={"email": "eng-audit-test@example.com", "password": "pw123456"}
    ).json()["access_token"]
    resp_ok = client.get(f"/api/v1/uds/audit/{project_id}", headers={"Authorization": f"Bearer {member_token}"})
    assert resp_ok.status_code == 200


def test_8_missing_invalid_traceability_reference_returns_404():
    resp = client.get("/api/v1/uds/traceability/test-case/does-not-exist")
    assert resp.status_code == 404
