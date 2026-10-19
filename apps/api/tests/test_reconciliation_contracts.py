from datetime import date
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.account_routes import runtime_engine
from app.auth import Identity, current_identity
from app.main import app
from app.models import Transaction
from app.reconciliation import Candidates, PairConfirmation, PairSelection, PairView, verify
from app.reconciliation_rules import PairImpact
from app.transactions import TransactionView, revision


@pytest.mark.parametrize("confirmation", [1, "true", "false", None])
def test_pair_confirmation_requires_boolean(confirmation):
    with pytest.raises(ValidationError):
        PairConfirmation(debit_revision="a" * 64, credit_revision="b" * 64, confirm=confirmation)


def test_confirmation_checks_both_revisions():
    debit = Transaction(
        user_id=uuid4(),
        account_id=uuid4(),
        booked_on=date(2026, 10, 1),
        amount_cents=-4500,
        kind="expense",
        description_ciphertext=b"test",
        dedup_key="a" * 64,
    )
    credit = debit.model_copy(update={"id": uuid4(), "amount_cents": 4500, "kind": "income"})
    data = PairConfirmation(
        debit_revision=revision(debit), credit_revision=revision(credit), confirm=True
    )
    verify(data, debit, credit)
    for changed in [
        data.model_copy(update={"confirm": False}),
        data.model_copy(update={"credit_revision": "0" * 64}),
    ]:
        with pytest.raises(HTTPException) as error:
            verify(changed, debit, credit)
        assert error.value.status_code in {409, 422}


def test_http_contract_uses_session_owner_and_exact_strings(monkeypatch):
    owner, account, identifier = uuid4(), uuid4(), uuid4()
    debit = TransactionView(
        id=uuid4(),
        account_id=account,
        booked_on=date(2026, 10, 1),
        amount_cents=str(-(2**60)),
        kind="expense",
        description="Sintético",
        category=None,
        revision="a" * 64,
    )
    credit = debit.model_copy(
        update={"id": uuid4(), "amount_cents": str(2**60), "kind": "income", "revision": "b" * 64}
    )
    result = PairView(
        id=identifier,
        debit=debit,
        credit=credit,
        impact=PairImpact(
            kind="transfer",
            amount_cents=str(2**60),
            expense_reduction_cents=str(2**60),
            income_reduction_cents=str(2**60),
        ),
    )
    captured = []

    def paired(engine, user, data):
        captured.append((user, data))
        return result

    monkeypatch.setattr("app.reconciliation.reconcile", paired)
    monkeypatch.setattr(
        "app.reconciliation.candidates",
        lambda *args: Candidates(source=debit, candidates=[], truncated=False),
    )
    monkeypatch.setattr("app.reconciliation.undo", lambda *args: None)
    app.dependency_overrides[current_identity] = lambda: Identity(id=owner)
    app.dependency_overrides[runtime_engine] = lambda: None
    try:
        with TestClient(app) as client:
            data = {
                "debit_id": str(debit.id),
                "credit_id": str(credit.id),
                "debit_revision": debit.revision,
                "credit_revision": credit.revision,
                "confirm": True,
            }
            response = client.post("/reconciliations", json=data)
            assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
            assert response.json()["impact"]["amount_cents"] == str(2**60)
            assert captured[0][0] == owner and isinstance(captured[0][1], PairSelection)
            assert (
                client.post("/reconciliations", json={**data, "user_id": str(uuid4())}).status_code
                == 422
            )
            assert client.get(f"/reconciliations/candidates?debit_id={debit.id}").status_code == 200
            response = client.request(
                "DELETE",
                f"/reconciliations/{identifier}",
                json={k: v for k, v in data.items() if k not in {"debit_id", "credit_id"}},
            )
            assert response.status_code == 204 and response.headers["cache-control"] == "no-store"
    finally:
        app.dependency_overrides.clear()
