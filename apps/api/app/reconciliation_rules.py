from typing import Literal

from pydantic import BaseModel

from app.models import Account, Transaction


class PairImpact(BaseModel):
    kind: Literal["transfer", "card_payment"]
    amount_cents: str
    expense_reduction_cents: str
    income_reduction_cents: str


def pair_impact(
    debit: Transaction, credit: Transaction, debit_account: Account, credit_account: Account
) -> PairImpact:
    if (
        debit.id == credit.id
        or debit.account_id == credit.account_id
        or debit.user_id != credit.user_id
        or debit.user_id != debit_account.user_id
        or debit.user_id != credit_account.user_id
        or debit.account_id != debit_account.id
        or credit.account_id != credit_account.id
        or debit_account.currency != "BRL"
        or credit_account.currency != "BRL"
        or debit_account.kind not in {"checking", "savings", "cash"}
        or credit_account.kind not in {"checking", "savings", "cash", "credit_card"}
        or debit.kind not in {"expense", "transfer"}
        or credit.kind not in {"income", "transfer"}
        or not -(2**63) <= debit.amount_cents < 0 < credit.amount_cents < 2**63
        or debit.amount_cents + credit.amount_cents != 0
        or abs((debit.booked_on - credit.booked_on).days) > 7
    ):
        raise ValueError("Escolha saída e entrada compatíveis em contas próprias distintas.")
    return PairImpact(
        kind="card_payment" if credit_account.kind == "credit_card" else "transfer",
        amount_cents=str(credit.amount_cents),
        expense_reduction_cents=str(-debit.amount_cents if debit.kind == "expense" else 0),
        income_reduction_cents=str(credit.amount_cents if credit.kind == "income" else 0),
    )
