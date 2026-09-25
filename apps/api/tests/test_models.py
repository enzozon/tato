from datetime import date
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlmodel import SQLModel

from app.models import Account, Category, Chunk, Goal, Transaction, User


def test_records_have_independent_ids_and_aware_timestamps() -> None:
    first, second = User(), User()
    assert first.id != second.id
    assert first.created_at.utcoffset().total_seconds() == 0


def test_money_preserves_cents_above_float_precision() -> None:
    account = Account.model_validate(
        dict(user_id=uuid4(), name_ciphertext=b"cifrado", kind="cash", opening_date=date.today())
    )
    entry = Transaction.model_validate(
        dict(
            user_id=account.user_id,
            account_id=account.id,
            booked_on=date.today(),
            amount_cents=9_007_199_254_740_993,
            kind="income",
            description_ciphertext=b"cifrado",
            dedup_key="a" * 64,
        )
    )
    assert entry.amount_cents == 9_007_199_254_740_993


def test_category_rejects_empty_name_when_validating_input() -> None:
    with pytest.raises(ValidationError):
        Category.model_validate(dict(user_id=uuid4(), name=""))


def test_goal_and_chunk_reject_invalid_boundaries() -> None:
    with pytest.raises(ValidationError):
        Goal.model_validate(dict(user_id=uuid4(), description_ciphertext=b"x", target_cents=0))
    with pytest.raises(ValidationError):
        Chunk.model_validate(
            dict(user_id=uuid4(), document_id=uuid4(), position=-1, content_ciphertext=b"x")
        )


def test_constraints_have_distinct_names_per_table() -> None:
    for table in SQLModel.metadata.sorted_tables:
        names = [constraint.name for constraint in table.constraints]
        assert None not in names
        assert len(names) == len(set(names)), table.name
