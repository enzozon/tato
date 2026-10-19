import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from threading import Event

import pytest
from fastapi import HTTPException
from sqlmodel import Session

from app import account_export as export
from app.account_service import account_session
from app.models import Account, User
from tests.test_account_export_record import KEY, personal_records

pytestmark = pytest.mark.integration


@pytest.fixture
def export_data(admin_engine, owners, monkeypatch):
    import base64

    monkeypatch.setenv("DATA_ENCRYPTION_KEY", base64.b64encode(KEY).decode())
    monkeypatch.setattr(export, "check_rate", lambda *args: None)
    identifiers = {}
    for owner in owners:
        rows = personal_records(owner)
        identifiers[owner] = [str(row.id) for row in rows]
        # Dependências são confirmadas em ordem; sem duplicar users da fixture.
        for row in rows:
            with Session(admin_engine) as session, session.begin():
                session.add(row)
    return owners, identifiers


def test_export_decrypts_all_tables_without_cross_tenant_leak(runtime_engine, export_data):
    (first, second), identifiers = export_data
    raw = export.export_account(runtime_engine, first)
    payload = json.loads(raw)
    other_ids = identifiers[second]
    assert all(identifier.encode() not in raw for identifier in [str(second), *other_ids])
    assert payload["user"]["id"] == str(first)
    assert payload["transactions"][0]["description"] == "Compra sintética"
    assert payload["accounts"][0]["name"] == "Carteira demonstrativa"
    assert payload["documents"][0]["content"] == "Texto sintético"
    assert payload["chunks"][0]["content"] == "Texto sintético"
    assert payload["rules"][0]["pattern"] == "mercado"
    assert payload["goals"][0]["target_cents"] == "100000"
    assert payload["insights"][0]["content"] == "Aviso demonstrativo"
    assert payload["chat_turns"][0]["request"] == "Pergunta sintética"
    assert payload["chat_turns"][0]["response"] is None
    assert payload["billing_checkouts"][0]["amount_cents"] == "3900"
    assert all(
        len(value) == 1
        for name, value in payload.items()
        if name not in {"version", "exported_at", "user", "reconciliations"}
    )
    assert payload["reconciliations"] == []
    for forbidden in ("ciphertext", "dedup_key", "digest", "embedding", "cs_test_private"):
        assert forbidden.encode() not in raw


@pytest.mark.parametrize("state", ["deletion", "corrupt"])
def test_export_aborts_whole_download(runtime_engine, admin_engine, export_data, state):
    owner = export_data[0][0]
    with Session(admin_engine) as session, session.begin():
        if state == "deletion":
            row = session.get(User, owner)
            row.deletion_requested_at = datetime.now(UTC)
        else:
            row = session.get(Account, personal_records(owner)[0].id)
            row.name_ciphertext = b"corrupt synthetic ciphertext"
        session.add(row)
    if state == "deletion":
        with pytest.raises(HTTPException) as error:
            export.export_account(runtime_engine, owner)
        assert error.value.status_code == 409
    else:
        from cryptography.exceptions import InvalidTag

        with pytest.raises(InvalidTag):
            export.export_account(runtime_engine, owner)


def test_export_holds_account_lock_then_returns_materialized_bytes(
    runtime_engine, export_data, monkeypatch
):
    owner = export_data[0][0]
    reading, attempted, acquired = Event(), Event(), Event()
    original = export.export_record

    def competing_change():
        assert reading.wait(5)
        attempted.set()
        with account_session(runtime_engine, owner) as session:
            acquired.set()
            user = session.get(User, owner)
            user.deletion_requested_at = datetime.now(UTC)
            session.add(user)

    def serialize(row, key, user):
        reading.set()
        assert attempted.wait(5)
        assert not acquired.is_set()
        return original(row, key, user)

    monkeypatch.setattr(export, "export_record", serialize)
    with ThreadPoolExecutor(max_workers=1) as pool:
        mutation = pool.submit(competing_change)
        raw = export.export_account(runtime_engine, owner)
        mutation.result(timeout=10)
    assert acquired.is_set()
    assert json.loads(raw)["user"]["id"] == str(owner)
    with pytest.raises(HTTPException) as error:
        export.export_account(runtime_engine, owner)
    assert error.value.status_code == 409
