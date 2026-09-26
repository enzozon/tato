from uuid import uuid4

from fastapi.testclient import TestClient

from app import account_routes as routes
from app.auth import Identity, current_identity
from app.main import app
from app.plans import FREE


def test_routes_require_session():
    with TestClient(app) as client:
        assert client.get("/me").status_code == 401
        assert client.post("/me/onboarding", json={"completed": True}).status_code == 401


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
