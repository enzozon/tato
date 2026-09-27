from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, ConfigDict, StringConstraints

from app.account_routes import EngineDep, IdentityDep
from app.account_service import account_session
from app.crypto import load_key
from app.models import User
from app.plans import user_plan
from app.rag.embedding import embed, encoder
from app.rag.indexing import index_private
from app.rag.reranking import rerank
from app.rag.retrieval import Hit, search
from app.rate_limit import check_rate

router = APIRouter(prefix="/rag", tags=["contexto e fontes"])


class SearchInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
    rerank: bool = True


def authorize(engine: EngineDep, owner: UUID, *, rate: bool = False) -> None:
    with account_session(engine, owner) as session:
        user = session.get(User, owner)
        if user is None or user.deletion_requested_at is not None:
            raise HTTPException(409, "Conta ausente ou com exclusão pendente.")
        if rate:
            check_rate(owner, user_plan(session, owner).requests_per_minute)


@router.post("/documents/{document_id}/index")
def index_document(
    document_id: UUID, identity: IdentityDep, engine: EngineDep, response: Response
) -> dict[str, int]:
    authorize(engine, identity.id, rate=True)
    try:
        count = index_private(engine, identity.id, document_id)
    except ValueError:
        raise HTTPException(422, "Documento indisponível ou incompatível com indexação.") from None
    except (KeyError, RuntimeError, OSError):
        raise HTTPException(503, "Indexação de contexto indisponível.") from None
    response.headers["Cache-Control"] = "no-store"
    return {"chunks": count}


@router.post("/search", response_model=list[Hit])
def retrieve(
    data: SearchInput, identity: IdentityDep, engine: EngineDep, response: Response
) -> list[Hit]:
    authorize(engine, identity.id, rate=True)
    try:
        vector = embed([data.question], query=True)[0]
        model = encoder()[2]
        with account_session(engine, identity.id) as session:
            user = session.get(User, identity.id)
            if user is None or user.deletion_requested_at is not None:
                raise HTTPException(409, "Conta ausente ou com exclusão pendente.")
            hits = search(
                session, identity.id, data.question, vector, model, load_key("DATA_ENCRYPTION_KEY")
            )
        result = rerank(data.question, hits) if data.rerank else hits[:5]
        authorize(engine, identity.id)
    except (ValueError, KeyError, RuntimeError, OSError):
        raise HTTPException(503, "Recuperação de contexto indisponível.") from None
    response.headers["Cache-Control"] = "no-store"
    return result
