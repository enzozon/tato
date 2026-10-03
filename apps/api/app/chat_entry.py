from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import Engine
from sqlmodel import select

from app.account_service import account_session
from app.categorization import load_rules, match_category
from app.chat_contracts import ChatInput, ChatReply
from app.crypto import decrypt_text, encrypt_text, load_key
from app.llm_service import require_active
from app.mascot import phrase
from app.models import Account, ChatTurn, Transaction
from app.rag.routes import authorize
from app.repositories import TransactionInput, add_transaction


def confirm_entry(engine: Engine, owner: UUID, turn_id: UUID) -> ChatReply:
    authorize(engine, owner, rate=True)
    key = load_key("DATA_ENCRYPTION_KEY")
    identity_key = load_key("DEDUP_HMAC_KEY")
    with account_session(engine, owner) as session:
        require_active(session, owner)
        turn = session.exec(
            select(ChatTurn).where(ChatTurn.user_id == owner, ChatTurn.id == turn_id)
        ).first()
        if turn is None or turn.response_ciphertext is None:
            raise HTTPException(404, "Prévia indisponível.")
        reply = ChatReply.model_validate_json(
            decrypt_text(turn.response_ciphertext, key, owner, "chat_response")
        )
        if reply.transaction_id is not None:
            return reply
        if reply.draft is None:
            raise HTTPException(409, "Este pedido não contém prévia de lançamento.")
        request = ChatInput.model_validate_json(
            decrypt_text(turn.request_ciphertext, key, owner, "chat_request")
        )
        account = session.get(Account, request.account_id) if request.account_id else None
        if account is None or account.user_id != owner:
            raise HTTPException(404, "Conta indisponível.")
        draft = reply.draft
        transaction = TransactionInput(
            account_id=account.id,
            category_id=match_category(draft.description, load_rules(session, owner, key)),
            booked_on=draft.booked_on,
            amount_cents=draft.amount_cents * (-1 if draft.kind == "expense" else 1),
            kind=draft.kind,
            description=draft.description,
            source_identity=f"chat:{turn.id}",
        )
        identifier = add_transaction(session, owner, transaction, key, identity_key)
        if identifier is None:
            raise HTTPException(409, "Lançamento já registrado; confira o histórico.")
        stored = session.get(Transaction, identifier)
        if stored is None or stored.amount_cents != transaction.amount_cents:
            raise ValueError("Lançamento não conferido no banco.")
        reply.transaction_id, reply.message = identifier, phrase("recorded")
        reply.draft = None
        turn.response_ciphertext = encrypt_text(
            reply.model_dump_json(), key, owner, "chat_response"
        )
        session.add(turn)
        return reply
