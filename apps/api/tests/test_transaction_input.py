from datetime import date
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.repositories import TransactionInput


@pytest.mark.parametrize(
    "kind,amount", [("income", -1), ("expense", 1), ("transfer", 0), ("expense", -1.5)]
)
def test_transaction_input_rejects_ambiguous_money(kind: str, amount: int | float) -> None:
    with pytest.raises(ValidationError):
        TransactionInput.model_validate(
            dict(
                account_id=uuid4(),
                booked_on=date.today(),
                amount_cents=amount,
                kind=kind,
                description="Mercado sintético",
                source_identity="ofx:1",
            )
        )


def test_transaction_input_excludes_owner_and_accepts_signed_cents() -> None:
    data = dict(
        account_id=uuid4(),
        booked_on=date.today(),
        amount_cents=-4200,
        kind="expense",
        description="Mercado sintético",
        source_identity="ofx:1",
    )
    assert TransactionInput.model_validate(data).amount_cents == -4200
    with pytest.raises(ValidationError):
        TransactionInput.model_validate(data | {"user_id": uuid4()})
    with pytest.raises(ValidationError):
        TransactionInput.model_validate(data | {"source_identity": " "})
