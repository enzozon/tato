from datetime import date
from unittest.mock import Mock
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.chat_contracts import ChatInput, Confirmation
from app.chat_tools import ExpenseQuery, run_expense_query
from app.mascot import phrase


def test_chat_rejects_control_fields_and_bounds():
    for extra in [{"user_id": str(uuid4())}, {"classification": "public"}, {"question": " "}]:
        with pytest.raises(ValidationError):
            ChatInput.model_validate({"request_id": uuid4(), "question": "oi"} | extra)
    for value in [False, "true", 0, 1, 1.0]:
        with pytest.raises(ValidationError):
            Confirmation(confirm=value)
    assert Confirmation(confirm=True).confirm
    assert "Olá" in phrase("greeting")


def test_category_is_passed_to_sql_not_vector_search(monkeypatch):
    category = uuid4()
    total = Mock(return_value=4200)
    monkeypatch.setattr("app.chat_tools.expense_total", total)
    query = ExpenseQuery(
        tool="expense_total", start=date(2026, 1, 1), end=date(2026, 2, 1), category_id=category
    )
    result = run_expense_query(None, uuid4(), query)
    assert result.amount_cents == 4200
    assert total.call_args.kwargs == {"category_id": category}
