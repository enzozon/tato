from datetime import date
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.account_routes import runtime_engine
from app.auth import Identity, current_identity
from app.crypto import encrypt_text
from app.main import app
from app.models import Transaction
from app.transactions import (
    TransactionDeletion,
    TransactionEdit,
    TransactionFilter,
    TransactionPage,
    revision,
    view,
)


@pytest.mark.parametrize("confirmation", [1, "true", "false", None])
def test_deletion_requires_boolean(confirmation):
    with pytest.raises(ValidationError):
        TransactionDeletion(revision="a" * 64, confirm=confirmation)


@pytest.mark.parametrize(
    "query",
    [
        {"start": "2026-10-02", "end": "2026-10-01"},
        {"limit": 101},
        {"cursor": "invalid"},
        {"cursor": "2026-10-01:invalid"},
        {"kind": "sql"},
    ],
)
def test_filters_reject_invalid_requests(query):
    with pytest.raises(ValidationError):
        TransactionFilter.model_validate(query)


@pytest.mark.parametrize(
    "amount,kind",
    [
        ("0", "income"),
        ("-1", "income"),
        ("1", "expense"),
        (str(2**63), "income"),
        ("1.5", "income"),
        (1.5, "income"),
    ],
)
def test_edits_reject_unsafe_money(amount, kind):
    with pytest.raises(ValidationError):
        TransactionEdit(
            revision="a" * 64,
            booked_on=date.today(),
            amount_cents=amount,
            kind=kind,
            description="Sintético",
        )


def test_revision_and_public_view_preserve_encrypted_money():
    owner = uuid4()
    record = Transaction(
        user_id=owner,
        account_id=uuid4(),
        booked_on=date(2026, 10, 1),
        kind="expense",
        amount_cents=-(2**60),
        dedup_key="a" * 64,
        description_ciphertext=encrypt_text("Sintético", b"x" * 32, owner, "transaction"),
    )
    result = view(record, None, b"x" * 32, owner)
    assert result.amount_cents == str(-(2**60)) and result.description == "Sintético"
    assert "dedup_key" not in result.model_dump() and "user_id" not in result.model_dump()
    assert result.revision == revision(record)
    record.kind = "transfer"
    assert result.revision != revision(record)


def test_http_filters_and_owner_are_not_client_controlled(monkeypatch):
    owner = uuid4()
    calls = []

    def listed(engine, identity, filters):
        calls.append((identity, filters))
        return TransactionPage(items=[], next_cursor=None)

    monkeypatch.setattr("app.transactions.list_transactions", listed)
    app.dependency_overrides[current_identity] = lambda: Identity(id=owner)
    app.dependency_overrides[runtime_engine] = lambda: None
    try:
        with TestClient(app) as client:
            response = client.get("/transactions?start=2026-10-01&limit=10")
            assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
            assert calls[0][0] == owner and calls[0][1].start == date(2026, 10, 1)
            assert client.get(f"/transactions?user_id={uuid4()}").status_code == 422
            assert client.put(f"/transactions/{uuid4()}", json={}).status_code == 422
    finally:
        app.dependency_overrides.clear()
