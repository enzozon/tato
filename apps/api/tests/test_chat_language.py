from uuid import uuid4

import pytest

from app import chat_language as language
from app.llm import LLMUnavailable
from app.llm_router import Routed
from app.rag.faithfulness import CitedAnswer, Claim
from app.rag.retrieval import Hit


@pytest.mark.parametrize(
    "message",
    [
        "Você tem 42 reais",
        "Invista em bitcoin",
        "Seu saldo está bom",
        "Guarde metade",
        "Rentabilidade garantida",
        "Compre ações",
    ],
)
def test_smalltalk_rejects_financial_claims(message):
    assert not language.safe_smalltalk(language.SmallTalk(message=message))


def test_conversation_uses_personal_context_and_falls_back(monkeypatch):
    def generate(engine, owner, request, model, guard):
        assert request.classification == "personal"
        value = language.SmallTalk(
            message="Podemos começar organizando suas prioridades. Como você se sente?"
        )
        assert guard(value)
        return Routed(value, ())

    monkeypatch.setattr(language, "generate", generate)
    assert "prioridades" in language.conversation(None, uuid4(), "estou preocupado", [])

    def fail(*args):
        raise LLMUnavailable()

    monkeypatch.setattr(language, "generate", fail)
    assert language.conversation(None, uuid4(), "oi", []) == language.phrase("greeting")


def test_generated_claims_must_quote_authorized_source(monkeypatch):
    hit = Hit(
        chunk_id=uuid4(),
        source="public",
        source_id="reserva",
        section="Reserva",
        content="Reserva ajuda a enfrentar imprevistos.",
    )

    def generate(engine, owner, request, model, guard):
        valid = CitedAnswer(
            abstained=False,
            claims=[Claim(text="Reserva ajuda a enfrentar imprevistos.", chunk_ids=[hit.chunk_id])],
        )
        assert guard(valid)
        assert not guard(
            CitedAnswer(abstained=False, claims=[Claim(text="Inventado", chunk_ids=[hit.chunk_id])])
        )
        assert not guard(
            CitedAnswer(abstained=False, claims=[Claim(text=hit.content, chunk_ids=[uuid4()])])
        )
        return Routed(valid, ())

    monkeypatch.setattr(language, "generate", generate)
    result = language.cited_explanation(None, uuid4(), "reserva?", [hit])
    assert result.claims[0].text == hit.content
    assert language.cited_explanation(None, uuid4(), "reserva?", []) is None
    assert (
        language.cited_explanation(
            None, uuid4(), "reserva?", [hit.model_copy(update={"source": "private"})]
        )
        is None
    )


def test_history_excludes_source_content_and_account_metadata():
    import json

    from app.chat_intent import model_history

    pairs = [
        (
            json.dumps({"question": "oi", "account_id": "private-id"}),
            json.dumps({"message": "Olá", "sources": [{"content": "extrato privado"}]}),
        )
    ]
    assert model_history(pairs) == [("oi", "Olá")]
    assert model_history([("invalid", "raw attachment")]) == []


def test_groq_schema_requires_nullable_fields_without_mutating_pydantic():
    from app.chat_intent import Decision
    from app.llm_http import strict_schema

    original = Decision.model_json_schema()
    adapted = strict_schema(original)
    analytical = adapted["$defs"]["Analytical"]
    assert set(analytical["required"]) == set(analytical["properties"])
    assert "anyOf" in adapted["properties"]["choice"]
    assert "oneOf" in original["properties"]["choice"]
    assert "category" not in original["$defs"]["Analytical"]["required"]
