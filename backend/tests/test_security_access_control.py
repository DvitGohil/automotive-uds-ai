import uuid

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.auth import hash_password
from app.db.database import Base, get_db
from app.db.models import Project, ProjectMember, TestCase, User
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


def _create_user(password="correct-horse-battery"):
    db = TestingSession()
    email = f"eng-{uuid.uuid4()}@example.com"
    user = User(email=email, full_name="Engineer", password_hash=hash_password(password))
    db.add(user)
    db.commit()
    user_id = user.id
    db.close()
    return user_id, email, password


def _login(email, password):
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return resp


def _bearer(token):
    return {"Authorization": f"Bearer {token}"}


def _seed_project_with_member(user_id=None):
    db = TestingSession()
    project = Project(name="Pilot")
    db.add(project)
    db.flush()
    if user_id:
        db.add(ProjectMember(project_id=project.id, user_id=user_id))
    db.commit()
    project_id = project.id
    db.close()
    return project_id


def _seed_test_case(project_id):
    db = TestingSession()
    row = TestCase(project_id=project_id, title="t", request_definition=None, preconditions="[]", is_negative_case=False)
    db.add(row)
    db.commit()
    row_id = row.id
    db.close()
    return row_id


# --- Login itself ------------------------------------------------------

def test_successful_login_returns_token():
    user_id, email, password = _create_user()
    resp = _login(email, password)
    assert resp.status_code == 200
    body = resp.json()
    assert body["user_id"] == user_id
    assert body["access_token"]


def test_invalid_login_wrong_password_rejected():
    _, email, _ = _create_user()
    resp = _login(email, "wrong-password")
    assert resp.status_code == 401


def test_invalid_login_unknown_email_rejected():
    resp = _login("nobody@example.com", "whatever")
    assert resp.status_code == 401


# --- Authorization built on real tokens ---------------------------------

def test_missing_authentication_rejected(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "JWT_SECRET", "test-secret")
    project_id = _seed_project_with_member()
    resp = client.get(f"/api/v1/uds/tests/{project_id}")
    assert resp.status_code == 401


def test_valid_authenticated_request_succeeds(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "JWT_SECRET", "test-secret")
    user_id, email, password = _create_user()
    project_id = _seed_project_with_member(user_id)
    token = _login(email, password).json()["access_token"]

    resp = client.get(f"/api/v1/uds/tests/{project_id}", headers=_bearer(token))
    assert resp.status_code == 200


def test_unauthorized_resource_access_non_member_rejected(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "JWT_SECRET", "test-secret")
    outsider_id, email, password = _create_user()
    project_id = _seed_project_with_member()  # outsider is NOT a member
    token = _login(email, password).json()["access_token"]

    resp = client.get(f"/api/v1/uds/tests/{project_id}", headers=_bearer(token))
    assert resp.status_code == 403


def test_cross_user_access_attempt_rejected(monkeypatch):
    """A token with a user id that doesn't exist (e.g. a forged/stale token) is rejected, not trusted blindly."""
    from app.core.auth import create_access_token
    from app.core.config import settings

    monkeypatch.setattr(settings, "JWT_SECRET", "test-secret")
    token = create_access_token("does-not-exist", "ghost@example.com")

    resp = client.get("/api/v1/uds/tests/some-project", headers=_bearer(token))
    assert resp.status_code == 401


def test_cross_project_access_attempt_rejected(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "JWT_SECRET", "test-secret")
    user_a_id, email_a, password_a = _create_user()
    project_a = _seed_project_with_member(user_a_id)
    project_b = _seed_project_with_member()  # user_a is not a member of project_b
    token_a = _login(email_a, password_a).json()["access_token"]

    resp = client.get(f"/api/v1/uds/tests/{project_b}", headers=_bearer(token_a))
    assert resp.status_code == 403
    # same user CAN access their own project
    ok = client.get(f"/api/v1/uds/tests/{project_a}", headers=_bearer(token_a))
    assert ok.status_code == 200


def test_token_validation_rejects_garbage_token(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "JWT_SECRET", "test-secret")
    project_id = _seed_project_with_member()
    resp = client.get(f"/api/v1/uds/tests/{project_id}", headers=_bearer("not-a-real-jwt"))
    assert resp.status_code == 401


def test_logout_endpoint_available():
    resp = client.post("/api/v1/auth/logout")
    assert resp.status_code == 200


# --- Input validation / safe errors (unchanged behavior, still verified) --

def test_invalid_input_rejected_with_safe_error(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "JWT_SECRET", "")  # auth off, focus on input validation
    oversized_service_id = "0x" + "F" * 500
    resp = client.post("/api/v1/uds/requests/construct", json={"service_id": oversized_service_id})
    assert resp.status_code == 422
    assert "Traceback" not in str(resp.json())


def test_missing_required_field_returns_422(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "JWT_SECRET", "")
    resp = client.post("/api/v1/uds/requests/construct", json={})
    assert resp.status_code == 422


# --- Protected resource classes -----------------------------------------

def test_protected_audit_access(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "JWT_SECRET", "test-secret")
    user_id, email, password = _create_user()
    project_id = _seed_project_with_member(user_id)
    token = _login(email, password).json()["access_token"]

    denied = client.get(f"/api/v1/uds/audit/{project_id}")
    assert denied.status_code == 401

    allowed = client.get(f"/api/v1/uds/audit/{project_id}", headers=_bearer(token))
    assert allowed.status_code == 200


def test_protected_document_access(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "API_KEY", "secret-key")
    resp = client.post(
        "/api/v1/documents/ingest",
        data={"project_id": "x", "title": "t", "source_type": "uds_spec"},
        files={"file": ("t.txt", b"content", "text/plain")},
    )
    assert resp.status_code == 401  # documents router protected by require_api_key


def test_protected_test_and_validation_access(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "JWT_SECRET", "test-secret")
    user_id, email, password = _create_user()
    project_id = _seed_project_with_member(user_id)
    row_id = _seed_test_case(project_id)
    token = _login(email, password).json()["access_token"]

    denied = client.get(f"/api/v1/uds/traceability/test-case/{row_id}")
    assert denied.status_code == 401

    allowed = client.get(f"/api/v1/uds/traceability/test-case/{row_id}", headers=_bearer(token))
    assert allowed.status_code == 200
