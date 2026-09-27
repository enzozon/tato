from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app import import_routes as routes
from app.account_routes import runtime_engine
from app.auth import Identity, current_identity
from app.import_parsers import ImportErrorDetail
from app.import_service import ImportResult
from app.main import app


@pytest.fixture
def client():
    app.dependency_overrides[current_identity] = lambda: Identity(id=uuid4())
    app.dependency_overrides[runtime_engine] = lambda: None
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


def test_upload_contract_and_no_store(client, monkeypatch):
    monkeypatch.setattr(
        routes,
        "store_import",
        lambda *args: ImportResult(document_id=uuid4(), inserted=2, duplicates=0, uncategorized=2),
    )
    response = client.post(
        "/import",
        data={"account_id": str(uuid4()), "kind": "csv"},
        files={"file": ("sample.csv", b"synthetic")},
    )
    assert response.status_code == 200
    assert response.json()["inserted"] == 2
    assert response.headers["cache-control"] == "no-store"


def test_errors_and_body_limits(client, monkeypatch):
    def reject(*args):
        raise ImportErrorDetail("Layout não reconhecido.")

    monkeypatch.setattr(routes, "store_import", reject)
    payload = {"account_id": str(uuid4()), "kind": "csv"}
    assert (
        client.post("/import", data=payload, files={"file": ("x", b"invalid")}).status_code == 422
    )
    assert (
        client.post("/import", content=b"x", headers={"content-length": "4000000"}).status_code
        == 413
    )
    assert (
        client.post(
            "/import",
            content=iter([b"x" * 2_000_000, b"x" * 2_000_000]),
            headers={"content-type": "multipart/form-data; boundary=x"},
        ).status_code
        == 413
    )


def test_import_requires_authentication():
    with TestClient(app) as client:
        response = client.post(
            "/import",
            data={"account_id": str(uuid4()), "kind": "csv"},
            files={"file": ("x.csv", b"synthetic")},
        )
    assert response.status_code == 401
