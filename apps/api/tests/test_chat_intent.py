from datetime import date
from uuid import uuid4

import pytest

from app.chat_intent import Analytical, Conceptual, Conversation, Entry, classify, local_intent


def test_local_intents_preserve_exact_money_and_dates():
    today = date(2026, 1, 1)
    entry = local_intent("gastei 42,05 no Mercado ontem", today).choice
    assert isinstance(entry, Entry)
    assert (entry.amount_cents, entry.booked_on, entry.description) == (
        4205,
        date(2025, 12, 31),
        "Mercado",
    )
    query = local_intent("Quanto gastei com Alimentação no mês passado?", today).choice
    assert isinstance(query, Analytical)
    assert (query.start, query.end, query.category) == (date(2025, 12, 1), today, "alimentacao")
    assert local_intent("quanto gastei este mês", today).choice.end == date(2026, 2, 1)
    assert isinstance(local_intent("O que é CDI?", today).choice, Conceptual)
    assert not local_intent("oi", today).choice.clarify


@pytest.mark.parametrize(
    "question",
    [
        "quanto gastei com alimentação ontem",
        "gastei 0 no mercado hoje",
        "gastei 1.234,56 no mercado ontem",
        "gastei -42 no mercado hoje",
        "gastei 42 no mercado ontem e 9 hoje",
        "compre ações X",
        "meu saldo é 500?",
    ],
)
def test_unsupported_scope_needs_clarification(question):
    decision = local_intent(question, date(2026, 1, 1)).choice
    assert isinstance(decision, Conversation) and decision.clarify


def test_personal_question_does_not_reach_provider(monkeypatch):
    monkeypatch.setattr(
        "app.llm_service.runtime_router", lambda: pytest.fail("Não enviar dados pessoais")
    )
    result = classify(None, uuid4(), "gastei talvez quarenta", date(2026, 1, 1), [])
    assert isinstance(result.choice, Conversation) and result.choice.clarify


def test_explicit_period_is_inclusive_and_rejects_invalid_dates():
    today = date(2026, 10, 3)
    result = local_intent("quanto gastei de 2026-01-01 a 2026-01-31?", today).choice
    assert isinstance(result, Analytical)
    assert (result.start, result.end) == (date(2026, 1, 1), date(2026, 2, 1))
    for period in ["2026-02-30 a 2026-03-01", "2026-03-02 a 2026-03-01", "9999-12-31 a 9999-12-31"]:
        assert isinstance(local_intent(f"quanto gastei de {period}", today).choice, Conversation)
