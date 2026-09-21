from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base, get_db
from app.main import app

from sqlalchemy.pool import StaticPool

engine = create_engine(
    "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
)
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
    from app.db.models import Project

    project = Project(name="Pilot")
    db.add(project)
    db.commit()
    project_id = project.id
    db.close()
    return project_id


def test_successful_request_construction():
    resp = client.post("/api/v1/uds/requests/construct", json={"service_id": "0x22", "did": "0xF190"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["request"]["request_bytes"] == "22 F1 90"


def test_invalid_request_construction():
    resp = client.post("/api/v1/uds/requests/construct", json={"service_id": "0x22"})  # missing DID
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is False
    assert body["errors"]


def test_request_validation_endpoint():
    resp = client.post("/api/v1/uds/requests/validate", json={"service_id": "0x22", "did": "0xF190"})
    assert resp.status_code == 200
    assert resp.json()["valid"] is True


def test_positive_test_generation_endpoint():
    project_id = _seed_project()
    resp = client.post(
        "/api/v1/uds/tests/positive",
        json={"service_id": "0x22", "did": "0xF190", "project_id": project_id},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["test_case"]["request"]["did"] == "0xF190"
    assert body["test_case_row_id"] is not None

    listed = client.get(f"/api/v1/uds/tests/{project_id}")
    assert listed.status_code == 200
    assert len(listed.json()) == 1


def test_negative_test_generation_endpoint():
    resp = client.post(
        "/api/v1/uds/tests/negative",
        json={"category": "missing_required_field", "service_id": "0x22"},
    )
    assert resp.status_code == 200
    assert resp.json()["test_case"]["scenario_category"] == "missing_required_field"


def test_response_validation_endpoint():
    resp = client.post(
        "/api/v1/uds/response-validation",
        json={
            "test_type": "positive",
            "generation": {"service_id": "0x22", "did": "0xF190"},
            "actual_response": "62 F1 90 31 48 47",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "PASS"


def test_automation_template_generation_endpoint():
    resp = client.post(
        "/api/v1/uds/automation-templates/positive",
        json={"service_id": "0x22", "did": "0xF190"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["expected_response"]["service_id"] == "0x62"
    assert body["requires_engineering_review"] is True


def test_authentication_failure_when_api_key_configured(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "API_KEY", "secret-key")
    resp = client.post("/api/v1/uds/requests/construct", json={"service_id": "0x22", "did": "0xF190"})
    assert resp.status_code == 401

    resp_ok = client.post(
        "/api/v1/uds/requests/construct",
        json={"service_id": "0x22", "did": "0xF190"},
        headers={"X-API-Key": "secret-key"},
    )
    assert resp_ok.status_code == 200


def test_invalid_input_missing_required_field_returns_422():
    resp = client.post("/api/v1/uds/requests/construct", json={})  # service_id is required by schema
    assert resp.status_code == 422


def test_negative_test_unsupported_category_returns_400():
    resp = client.post(
        "/api/v1/uds/tests/negative",
        json={"category": "not_a_real_category", "service_id": "0x22"},
    )
    assert resp.status_code == 400
