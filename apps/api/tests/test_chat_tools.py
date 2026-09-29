import json
from datetime import date
from typing import Any
from unittest.mock import Mock
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlmodel import Session

from app.chat_tools import ExpenseQuery, ExpenseResult, render_expense, run_expense_query


def test_expense_tool_uses_authenticated_owner_and_exact_sql_result(monkeypatch: Any) -> None:
    owner = uuid4()
    session = Mock(spec=Session)
    query = ExpenseQuery.model_validate_json(
        '{"tool":"expense_total","start":"2026-09-01","end":"2026-10-01"}'
    )
    total = Mock(return_value=9007199254740993)
    monkeypatch.setattr("app.chat_tools.expense_total", total)
    result = run_expense_query(session, owner, query)
    total.assert_called_once_with(session, owner, date(2026, 9, 1), date(2026, 10, 1))
    assert result.source == query
    assert render_expense(result).endswith("R$ 90.071.992.547.409,93.")
    assert "fim exclusivo" in render_expense(result)
    assert render_expense(ExpenseResult(source=query, amount_cents=0)).endswith("R$ 0,00.")


@pytest.mark.parametrize(
    "change",
    [
        {"tool": "SELECT * FROM transactions"},
        {"user_id": str(uuid4())},
        {"sql": "DROP TABLE transactions"},
        {"end": "2026-09-01"},
        {"end": "2026-08-31"},
        {"start": "ontem"},
    ],
)
def test_expense_tool_rejects_untrusted_arguments(change: dict[str, object]) -> None:
    data = {"tool": "expense_total", "start": "2026-09-01", "end": "2026-10-01"}
    with pytest.raises(ValidationError):
        ExpenseQuery.model_validate_json(json.dumps(data | change))
