from datetime import date, timedelta
from uuid import uuid4

import pytest

from app.models import Account, Transaction
from app.reconciliation_rules import pair_impact


def pair():
    owner = uuid4()
    outgoing = Account(
        user_id=owner, kind="checking", name_ciphertext=b"test", opening_date=date(2026, 1, 1)
    )
    incoming = Account(
        user_id=owner, kind="savings", name_ciphertext=b"test", opening_date=date(2026, 1, 1)
    )
    debit = Transaction(
        user_id=owner,
        account_id=outgoing.id,
        booked_on=date(2026, 10, 1),
        amount_cents=-(2**60),
        kind="expense",
        description_ciphertext=b"test",
        dedup_key="a" * 64,
    )
    credit = Transaction(
        user_id=owner,
        account_id=incoming.id,
        booked_on=date(2026, 10, 8),
        amount_cents=2**60,
        kind="income",
        description_ciphertext=b"test",
        dedup_key="b" * 64,
    )
    return debit, credit, outgoing, incoming


@pytest.mark.parametrize(
    "account_kind,expected", [("savings", "transfer"), ("credit_card", "card_payment")]
)
def test_pair_preserves_exact_amount_and_classifies(account_kind, expected):
    debit, credit, outgoing, incoming = pair()
    incoming.kind = account_kind
    result = pair_impact(debit, credit, outgoing, incoming)
    assert result.kind == expected and result.amount_cents == str(2**60)
    assert result.expense_reduction_cents == str(2**60)
    assert result.income_reduction_cents == str(2**60)
    assert debit.kind == "expense" and credit.kind == "income"
    debit.kind = credit.kind = "transfer"
    result = pair_impact(debit, credit, outgoing, incoming)
    assert result.expense_reduction_cents == result.income_reduction_cents == "0"


@pytest.mark.parametrize(
    "change",
    [
        "same_account",
        "foreign_owner",
        "foreign_account",
        "same_line",
        "unequal",
        "same_sign",
        "late",
        "card_outgoing",
        "currency",
        "invalid_kind",
        "overflow",
    ],
)
def test_pair_rejects_unsafe_matches(change):
    debit, credit, outgoing, incoming = pair()
    if change == "same_account":
        credit.account_id = debit.account_id
    if change == "foreign_owner":
        credit.user_id = uuid4()
    if change == "foreign_account":
        incoming.user_id = uuid4()
    if change == "same_line":
        credit.id = debit.id
    if change == "unequal":
        credit.amount_cents -= 1
    if change == "same_sign":
        credit.amount_cents = debit.amount_cents
    if change == "late":
        credit.booked_on += timedelta(days=1)
    if change == "card_outgoing":
        outgoing.kind = "credit_card"
    if change == "currency":
        incoming.currency = "USD"
    if change == "invalid_kind":
        credit.kind = "expense"
    if change == "overflow":
        debit.amount_cents, credit.amount_cents = -(2**63), 2**63
    with pytest.raises(ValueError):
        pair_impact(debit, credit, outgoing, incoming)
