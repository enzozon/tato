import json
from datetime import UTC, datetime
from uuid import uuid4, uuid5

import pytest
from cryptography.exceptions import InvalidTag

from app.account_export_record import export_record
from app.crypto import encrypt_text
from app.models import Agent, BillingCheckout, ChatTurn, LLMUsage, Reconciliation, User
from app.seed_data import demo_records

KEY = b"x" * 32


def test_reconciliation_export_preserves_both_legs_and_previous_kinds():
    owner = uuid4()
    row = Reconciliation(
        user_id=owner,
        debit_transaction_id=uuid4(),
        credit_transaction_id=uuid4(),
        kind="card_payment",
        debit_previous_kind="expense",
        credit_previous_kind="income",
    )
    assert export_record(row, KEY, owner) == {
        "id": str(row.id),
        "created_at": row.created_at.isoformat(),
        "debit_transaction_id": str(row.debit_transaction_id),
        "credit_transaction_id": str(row.credit_transaction_id),
        "kind": "card_payment",
        "debit_previous_kind": "expense",
        "credit_previous_kind": "income",
    }


def personal_records(owner):
    rows = demo_records(owner, KEY, KEY)[1:]
    rows += [
        Agent(user_id=owner, kind="runway", account_id=uuid5(owner, "account")),
        ChatTurn(
            user_id=owner,
            request_id=uuid4(),
            request_ciphertext=encrypt_text("Pergunta sintética", KEY, owner, "chat_request"),
        ),
        BillingCheckout(
            user_id=owner,
            request_id=uuid4(),
            provider="stripe",
            amount_cents=3900,
            external_id=f"cs_test_private_{owner.hex}",
        ),
        LLMUsage(user_id=owner, provider="groq", outcome="ok", elapsed_ms=12),
    ]
    return rows


@pytest.mark.parametrize("position", range(13))
def test_record_decrypts_explicit_allowlist(position):
    owner = uuid4()
    row = personal_records(owner)[position]
    payload = export_record(row, KEY, owner)
    assert payload["id"] == str(row.id)
    assert "created_at" in payload
    for forbidden in (
        "user_id",
        "embedding",
        "embedding_model",
        "dedup_key",
        "digest",
        "event_key",
        "request_id",
        "external_id",
        "external_customer_id",
    ):
        assert forbidden not in payload
    assert not any(name.endswith("ciphertext") for name in payload)
    for name, value in payload.items():
        if name.endswith("_cents"):
            assert isinstance(value, str)
    assert "cs_test_private" not in json.dumps(payload, default=str)


def test_record_uses_exact_money_and_authenticated_ciphertext():
    owner = uuid4()
    row = personal_records(owner)[2]
    row.amount_cents = -(2**63)
    assert export_record(row, KEY, owner)["amount_cents"] == "-9223372036854775808"
    with pytest.raises(InvalidTag):
        export_record(row, KEY, uuid4())
    with pytest.raises(ValueError):
        export_record(User(), KEY, owner)


def test_record_dates_are_iso_and_completed_chat_remains_original_text():
    owner = uuid4()
    turn = personal_records(owner)[10]
    turn.completed_at = datetime(2026, 10, 16, 3, 9, tzinfo=UTC)
    turn.response_ciphertext = encrypt_text("Resposta sintética", KEY, owner, "chat_response")
    payload = export_record(turn, KEY, owner)
    assert payload["completed_at"] == "2026-10-16T03:09:00+00:00"
    assert payload["response"] == "Resposta sintética"
    assert "T" in payload["created_at"]
    account = export_record(personal_records(owner)[0], KEY, owner)
    assert account["opening_date"] == "2026-01-01"
