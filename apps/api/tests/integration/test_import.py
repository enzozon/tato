import base64
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import update
from sqlmodel import Session, select

from app.account_routes import runtime_engine as engine_dependency
from app.auth import Identity, current_identity
from app.crypto import decrypt_text, encrypt_text
from app.database import tenant_session
from app.import_service import store_import
from app.main import app
from app.models import Account, Category, Document, Rule, Subscription, Transaction, User

pytestmark = pytest.mark.integration
CSV = b"date,title,amount\n2026-09-01,Mercado sintetico,42.00\n2026-09-01,Mercado sintetico,42.00\n"


@pytest.fixture
def accounts(runtime_engine, owners, monkeypatch):
    for name, key in [("DATA_ENCRYPTION_KEY", b"x" * 32), ("DEDUP_HMAC_KEY", b"y" * 32)]:
        monkeypatch.setenv(name, base64.b64encode(key).decode())
    monkeypatch.setenv("TATO_ENV", "development")
    monkeypatch.setenv("RATE_LIMIT_BACKEND", "memory")
    result = []
    for owner in owners:
        with tenant_session(runtime_engine, owner) as session:
            for _ in range(2):
                account = Account(
                    user_id=owner,
                    kind="checking",
                    name_ciphertext=b"sintetico",
                    opening_date=date(2026, 1, 1),
                )
                session.add(account)
                session.flush()
                result.append(account.id)
    return result


def test_concurrent_reimport_preserves_equal_purchases(runtime_engine, owners, accounts):
    owner = owners[0]

    def upload():
        return store_import(runtime_engine, owner, accounts[0], CSV, "teste.csv", "csv")

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: upload(), range(2)))
    assert sorted(r.inserted for r in results) == [0, 2]
    assert sorted(r.duplicates for r in results) == [0, 2]
    assert results[0].document_id == results[1].document_id
    with tenant_session(runtime_engine, owner) as session:
        documents = session.exec(select(Document)).all()
        rows = session.exec(select(Transaction)).all()
        assert len(documents) == 1 and len(rows) == 2
        assert documents[0].account_id == accounts[0]
        assert b"Mercado" not in documents[0].content_ciphertext
        for row in rows:
            assert row.amount_cents == -4200
            assert row.document_id == documents[0].id
            assert decrypt_text(row.description_ciphertext, b"x" * 32, owner, "transaction")
    with tenant_session(runtime_engine, owners[1]) as session:
        assert not session.exec(select(Document)).all()
        assert not session.exec(select(Transaction)).all()


def test_source_quota_is_atomic_and_pro_allows_second_source(
    runtime_engine, admin_engine, owners, accounts
):
    owner = owners[0]

    def upload(account):
        try:
            return store_import(runtime_engine, owner, account, CSV, "teste.csv", "csv").inserted
        except HTTPException as error:
            return error.status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(upload, accounts[:2])) == [2, 403]
    with Session(admin_engine) as session, session.begin():
        session.add(Subscription(user_id=owner, plan="pro", status="active"))
    assert sorted(upload(account) for account in accounts[:2]) == [0, 2]


def test_owner_and_deletion_checks_precede_writes(runtime_engine, admin_engine, owners, accounts):
    with pytest.raises(HTTPException) as error:
        store_import(runtime_engine, owners[1], accounts[0], CSV, "teste.csv", "csv")
    assert error.value.status_code == 404
    with admin_engine.begin() as connection:
        connection.execute(
            update(User).where(User.id == owners[0]).values(deletion_requested_at=datetime.now(UTC))
        )
    with pytest.raises(HTTPException) as error:
        store_import(runtime_engine, owners[0], accounts[0], CSV, "teste.csv", "csv")
    assert error.value.status_code == 409


def test_bank_identity_conflict_rolls_back_document(runtime_engine, owners, accounts):
    content = "Data,Valor,Identificador,Descrição\n01/09/2026,-42,bank-1,Mercado\n".encode()
    owner, account = owners[0], accounts[0]
    first = store_import(runtime_engine, owner, account, content, "teste.csv", "csv")
    revised = content.replace(b"Mercado", b"Mercado revisado")
    assert store_import(runtime_engine, owner, account, revised, "novo.csv", "csv").duplicates == 1
    with pytest.raises(HTTPException) as error:
        store_import(
            runtime_engine, owner, account, content.replace(b"-42", b"-43"), "x.csv", "csv"
        )
    assert error.value.status_code == 409
    with tenant_session(runtime_engine, owner) as session:
        assert len(session.exec(select(Document)).all()) == 2
        rows = session.exec(select(Transaction)).all()
        assert len(rows) == 1
        assert rows[0].amount_cents == -4200 and rows[0].document_id == first.document_id


def test_rules_never_cross_owners(runtime_engine, owners, accounts):
    for owner in owners:
        with tenant_session(runtime_engine, owner) as session:
            category = Category(user_id=owner, name="Compras")
            session.add(category)
            session.flush()
            session.add(
                Rule(
                    user_id=owner,
                    category_id=category.id,
                    pattern_ciphertext=encrypt_text("mercado", b"x" * 32, owner, "rule"),
                    enabled=owner == owners[1],
                )
            )
    first = store_import(runtime_engine, owners[0], accounts[0], CSV, "a.csv", "csv")
    second = store_import(runtime_engine, owners[1], accounts[2], CSV, "a.csv", "csv")
    assert first.uncategorized == 2
    assert second.uncategorized == 0


def test_http_setup_to_import(runtime_engine, owners, accounts):
    owner = owners[0]
    app.dependency_overrides[current_identity] = lambda: Identity(id=owner)
    app.dependency_overrides[engine_dependency] = lambda: runtime_engine
    try:
        with TestClient(app) as client:
            account = client.post(
                "/accounts",
                json={"name": "Conta teste", "kind": "checking", "opening_date": "2026-01-01"},
            )
            assert account.status_code == 201
            for pattern in ["mercado", "padaria"]:
                assert (
                    client.post(
                        "/rules", json={"category": "Compras", "pattern": pattern}
                    ).status_code
                    == 201
                )
            response = client.post(
                "/import",
                data={"account_id": account.json()["id"], "kind": "csv"},
                files={"file": ("teste.csv", CSV)},
            )
            assert response.status_code == 200
            assert response.json()["inserted"] == 2
            assert response.json()["uncategorized"] == 0
        with tenant_session(runtime_engine, owner) as session:
            assert len(session.exec(select(Category)).all()) == 1
            assert len(session.exec(select(Rule)).all()) == 2
    finally:
        app.dependency_overrides.clear()
