from uuid import uuid4

from fastapi.testclient import TestClient

from app import account_routes as routes
from app.auth import Identity, current_identity
from app.main import app
from app.plans import FREE


def test_storage_error_does_not_expose_query_or_parameters(monkeypatch):
    from sqlalchemy.exc import OperationalError

    app.dependency_overrides[current_identity] = lambda: Identity(id=uuid4())
    app.dependency_overrides[routes.runtime_engine] = lambda: None

    def fail(*args, **kwargs):
        raise OperationalError("private query", {"secret": "never expose"}, Exception("private"))

    monkeypatch.setattr(routes, "profile", fail)
    try:
        with TestClient(app) as client:
            response = client.get("/me")
            assert response.status_code == 503
            assert "private" not in response.text and "never expose" not in response.text
    finally:
        app.dependency_overrides.clear()


def test_routes_require_session():
    with TestClient(app) as client:
        assert client.get("/me").status_code == 401
        assert client.post("/me/onboarding", json={"completed": True}).status_code == 401
        assert client.request("DELETE", "/me", json={"confirm": True}).status_code == 401


def test_account_openapi_contract():
    schema = app.openapi()
    for path, method in [("/me", "get"), ("/me", "delete"), ("/me/onboarding", "post")]:
        assert schema["paths"][path][method]["security"] == [{"HTTPBearer": []}]
    assert schema["components"]["schemas"]["DeletionInput"]["additionalProperties"] is False
    assert schema["components"]["schemas"]["OnboardingInput"]["additionalProperties"] is False
    assert "204" in schema["paths"]["/me"]["delete"]["responses"]


def test_profile_contract_rejects_internal_fields(monkeypatch):
    owner = uuid4()
    app.dependency_overrides[current_identity] = lambda: Identity(id=owner)
    app.dependency_overrides[routes.runtime_engine] = lambda: None
    monkeypatch.setattr(
        routes,
        "profile",
        lambda *args, **kwargs: routes.Profile(id=owner, onboarding_completed=True, plan=FREE),
    )
    try:
        with TestClient(app) as client:
            response = client.get("/me")
            assert response.headers["cache-control"] == "no-store"
            assert set(response.json()) == {"id", "onboarding_completed", "plan"}
            assert client.post("/me/onboarding", json={"completed": True}).status_code == 200
            for extra in ["user_id", "plan", "cpf", "deletion_requested_at"]:
                assert (
                    client.post("/me/onboarding", json={"completed": True, extra: "x"}).status_code
                    == 422
                )
    finally:
        app.dependency_overrides.clear()
