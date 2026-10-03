import json
from collections.abc import AsyncIterator
from uuid import UUID

from cryptography.exceptions import InvalidTag
from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from app.account_routes import EngineDep, IdentityDep
from app.chat_contracts import ChatInput, ChatReply, Confirmation
from app.chat_entry import confirm_entry
from app.chat_history import recent_history
from app.chat_service import respond
from app.crypto import load_key
from app.llm import LLMUnavailable
from app.rag.routes import authorize

router = APIRouter(prefix="/chat", tags=["conversa financeira"])
HEADERS = {"Cache-Control": "no-store", "X-Accel-Buffering": "no"}
UNAVAILABLE = (KeyError, ValueError, OSError, RuntimeError, LLMUnavailable, InvalidTag)


@router.post("", response_model=ChatReply)
def send(
    data: ChatInput, identity: IdentityDep, engine: EngineDep, response: Response
) -> ChatReply:
    response.headers.update(HEADERS)
    try:
        result = respond(engine, identity.id, data)
        authorize(engine, identity.id)
        return result
    except UNAVAILABLE:
        raise HTTPException(
            503, "Conversa temporariamente indisponível.", headers=HEADERS
        ) from None


@router.post("/{turn_id}/confirm", response_model=ChatReply)
def confirm(
    turn_id: UUID, data: Confirmation, identity: IdentityDep, engine: EngineDep, response: Response
) -> ChatReply:
    response.headers.update(HEADERS)
    try:
        result = confirm_entry(engine, identity.id, turn_id)
        authorize(engine, identity.id)
        return result
    except UNAVAILABLE:
        raise HTTPException(
            503, "Confirmação temporariamente indisponível.", headers=HEADERS
        ) from None


class HistoryItem(BaseModel):
    request: ChatInput
    response: ChatReply


@router.get("", response_model=list[HistoryItem])
def history(identity: IdentityDep, engine: EngineDep, response: Response) -> list[HistoryItem]:
    response.headers.update(HEADERS)
    authorize(engine, identity.id, rate=True)
    try:
        pairs = recent_history(engine, identity.id, load_key("DATA_ENCRYPTION_KEY"))
        result = [
            HistoryItem(
                request=ChatInput.model_validate_json(q), response=ChatReply.model_validate_json(a)
            )
            for q, a in pairs
        ]
        authorize(engine, identity.id)
        return result
    except UNAVAILABLE:
        raise HTTPException(
            503, "Histórico temporariamente indisponível.", headers=HEADERS
        ) from None


@router.post(
    "/stream",
    response_class=StreamingResponse,
    responses={200: {"content": {"text/event-stream": {}}}},
)
def stream(data: ChatInput, identity: IdentityDep, engine: EngineDep) -> StreamingResponse:
    authorize(engine, identity.id)

    async def events() -> AsyncIterator[str]:
        yield 'event: status\ndata: {"state":"processing"}\n\n'
        try:
            result = await run_in_threadpool(respond, engine, identity.id, data)
            await run_in_threadpool(authorize, engine, identity.id)
            # Só transmite conteúdo validado e já persistido; nunca tokens crus do modelo.
            yield f"event: reply\ndata: {result.model_dump_json()}\n\n"
        except Exception as error:
            code = error.status_code if isinstance(error, HTTPException) else 503
            payload = json.dumps(
                {"status": code, "detail": "Não foi possível concluir a conversa."}
            )
            yield f"event: error\ndata: {payload}\n\n"
        yield "event: done\ndata: {}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream", headers=HEADERS)
