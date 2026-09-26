from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from threading import Event

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert
from sqlmodel import Session

from app import account_service as service
from app.account_routes import runtime_engine as api_engine
from app.auth import Identity, current_identity
from app.main import app
from app.models import User
from app.seed_data import demo_records

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def local_limits(monkeypatch):
    monkeypatch.setenv("TATO_ENV", "development")
    monkeypatch.setenv("RATE_LIMIT_BACKEND", "memory")
    monkeypatch.setenv("DEDUP_HMAC_KEY", "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=")


def test_http_profile_onboarding_and_delete(runtime_engine, admin_engine, owners, monkeypatch):
    owner, other = owners
    app.dependency_overrides[api_engine] = lambda: runtime_engine
    app.dependency_overrides[current_identity] = lambda: Identity(id=owner)
    monkeypatch.setattr(service, "delete_identity", lambda identity: None)
    try:
        with TestClient(app) as client:
            profile = client.get(f"/me?user_id={other}&plan=pro")
            assert profile.json()["id"] == str(owner)
            assert profile.json()["plan"]["name"] == "free"
            assert not profile.json()["onboarding_completed"]
            for _ in range(2):
                assert client.post("/me/onboarding", json={"completed": True}).json()[
                    "onboarding_completed"
                ]
            assert client.request("DELETE", "/me", json={"confirm": False}).status_code == 422
            assert client.request("DELETE", "/me", json={"confirm": True}).status_code == 204
        with Session(admin_engine) as session:
            assert session.get(User, owner) is None
            assert session.get(User, other).onboarding_completed_at is None
    finally:
        app.dependency_overrides.clear()


def test_provisioning_is_serialized(runtime_engine, admin_engine, owners):
    owner = owners[0]
    with admin_engine.begin() as conn:
        conn.execute(delete(User).where(User.id == owner))

    def first_visit():
        return service.profile(runtime_engine, owner, lambda: Identity(id=owner), complete=True)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: first_visit(), range(2)))
    assert all(result.onboarding_completed for result in results)
    with Session(admin_engine) as session:
        assert session.get(User, owner).onboarding_completed_at is not None


def test_failed_deletion_persists_and_retry_cascades(
    runtime_engine, admin_engine, owners, monkeypatch
):
    rows = []
    with admin_engine.begin() as conn:
        for owner in owners:
            data = demo_records(owner, b"a" * 32, b"b" * 32)
            for row in data[1:]:
                conn.execute(insert(type(row)).values(**row.model_dump()))
            rows.append(data)
    owner = owners[0]

    def unavailable(identity):
        raise HTTPException(503)

    monkeypatch.setattr(service, "delete_identity", unavailable)
    with pytest.raises(HTTPException):
        service.request_deletion(runtime_engine, owner, lambda: Identity(id=owner))
    with Session(admin_engine) as session:
        assert session.get(User, owner).deletion_requested_at is not None
    with pytest.raises(HTTPException) as error:
        service.profile(runtime_engine, owner, lambda: Identity(id=owner))
    assert error.value.status_code == 409
    monkeypatch.setattr(service, "delete_identity", lambda identity: None)
    service.finish_deletion(runtime_engine, owner)
    service.finish_deletion(runtime_engine, owner)
    with Session(admin_engine) as session:
        assert all(session.get(type(row), row.id) is None for row in rows[0])
        assert all(session.get(type(row), row.id) is not None for row in rows[1])


def test_failure_after_auth_removal_is_retryable(runtime_engine, admin_engine, owners, monkeypatch):
    owner = owners[0]
    with Session(admin_engine) as session, session.begin():
        user = session.get(User, owner)
        user.deletion_requested_at = datetime.now(UTC)
        session.add(user)
    deleted = []
    monkeypatch.setattr(service, "delete_identity", lambda identity: deleted.append(identity))

    def unavailable(identity):
        raise HTTPException(503)

    monkeypatch.setattr(service, "clear_rate", unavailable)
    with pytest.raises(HTTPException):
        service.finish_deletion(runtime_engine, owner)
    with Session(admin_engine) as session:
        assert session.get(User, owner).deletion_requested_at is not None
    monkeypatch.setattr(service, "clear_rate", lambda identity: None)
    service.finish_deletion(runtime_engine, owner)
    assert deleted == [owner, owner]


def test_stale_request_cannot_recreate_deleted_account(
    runtime_engine, admin_engine, owners, monkeypatch
):
    owner = owners[0]
    entered, release, started = Event(), Event(), Event()

    def remove_identity(identity):
        entered.set()
        assert release.wait(4)

    def revoked():
        raise HTTPException(401)

    def stale_request():
        started.set()
        return service.profile(runtime_engine, owner, revoked)

    monkeypatch.setattr(service, "delete_identity", remove_identity)
    with ThreadPoolExecutor(max_workers=2) as pool:
        deletion = pool.submit(
            service.request_deletion, runtime_engine, owner, lambda: Identity(id=owner)
        )
        assert entered.wait(4)
        stale = pool.submit(stale_request)
        assert started.wait(4)
        release.set()
        deletion.result(timeout=5)
        with pytest.raises(HTTPException) as error:
            stale.result(timeout=5)
        assert error.value.status_code == 401
    with Session(admin_engine) as session:
        assert session.get(User, owner) is None
