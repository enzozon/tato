from contextlib import suppress
from datetime import datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import Engine
from sqlmodel import select

from app.account_service import account_session
from app.categorization import normalize
from app.chat_contracts import ChatInput, ChatReply
from app.chat_history import finish_turn, recent_history, reserve_turn
from app.chat_intent import Analytical, Conceptual, Conversation, Entry, classify
from app.chat_tools import ExpenseQuery, render_expense, run_expense_query
from app.crypto import load_key
from app.llm import LLMUnavailable
from app.llm_service import require_active
from app.mascot import phrase
from app.models import Account, Category
from app.rag.embedding import embed, encoder
from app.rag.retrieval import Hit, search
from app.rag.routes import authorize


def conceptual_sources(engine: Engine, owner: UUID, question: str, key: bytes) -> list[Hit]:
    vector = embed([question], query=True)[0]
    model = encoder()[2]
    with account_session(engine, owner) as session:
        require_active(session, owner)
        hits = search(session, owner, question, vector, model, key)[:5]
        # Trechos são dados citados, nunca instruções executáveis ou cálculos.
        return [hit.model_copy(update={"content": hit.content[:1200]}) for hit in hits]


def build_reply(
    engine: Engine, owner: UUID, data: ChatInput, turn_id: UUID, key: bytes
) -> ChatReply:
    today = datetime.now(ZoneInfo("America/Sao_Paulo")).date()
    choice = classify(
        engine, owner, data.question, today, recent_history(engine, owner, key)
    ).choice
    reply = ChatReply(turn_id=turn_id, intent=choice.intent, message=phrase("clarify"))
    if isinstance(choice, Conversation):
        reply.message = phrase("clarify" if choice.clarify else "greeting")
    elif isinstance(choice, Conceptual):
        reply.sources = conceptual_sources(engine, owner, data.question, key)
        reply.message = phrase("sources" if reply.sources else "no_sources")
    else:
        with account_session(engine, owner) as session:
            require_active(session, owner)
            if isinstance(choice, Entry):
                account = session.get(Account, data.account_id) if data.account_id else None
                if account is None or account.user_id != owner:
                    reply.message = phrase("account")
                else:
                    reply.draft, reply.message, reply.mood = choice, phrase("draft"), "atento"
            elif isinstance(choice, Analytical):
                category_id = None
                if choice.category is not None:
                    categories = session.exec(
                        select(Category).where(Category.user_id == owner)
                    ).all()
                    matches = [
                        row
                        for row in categories
                        if normalize(row.name) == normalize(choice.category)
                    ]
                    if len(matches) != 1:
                        reply.message = phrase("category")
                        return reply
                    category_id = matches[0].id
                query = ExpenseQuery(
                    tool="expense_total",
                    start=choice.start,
                    end=choice.end,
                    category_id=category_id,
                )
                reply.expense = run_expense_query(session, owner, query)
                reply.message = render_expense(reply.expense)
    return reply


def respond(engine: Engine, owner: UUID, data: ChatInput) -> ChatReply:
    authorize(engine, owner, rate=True)
    key = load_key("DATA_ENCRYPTION_KEY")
    reservation = reserve_turn(engine, owner, data.request_id, data.model_dump_json(), key)
    if not reservation.created:
        if reservation.response is not None:
            authorize(engine, owner)
            return ChatReply.model_validate_json(reservation.response)
        raise HTTPException(
            409, "Pedido em processamento ou encerrado sem resposta. Consulte o histórico."
        )
    try:
        reply = build_reply(engine, owner, data, reservation.turn_id, key)
        with account_session(engine, owner) as session:
            finish_turn(session, owner, reservation.turn_id, reply.model_dump_json(), key)
        return reply
    except Exception:
        # Não armazena a exceção: pode conter texto pessoal ou parâmetros SQL.
        with suppress(HTTPException, LLMUnavailable), account_session(engine, owner) as session:
            finish_turn(session, owner, reservation.turn_id, None, key)
        raise
