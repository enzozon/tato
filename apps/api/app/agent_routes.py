import hmac
import os
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from typing import Annotated
from uuid import UUID
from zoneinfo import ZoneInfo

from cryptography.exceptions import InvalidTag
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field

from app.account_routes import CredentialsDep, EngineDep, IdentityDep
from app.agent_config import AgentInput, AgentView, GoalInput, configure, create_goal, list_agents
from app.agent_mail import deliver_pending
from app.agent_rules import AgentKind
from app.agent_runtime import run_agents
from app.import_setup import CreatedRecord
from app.insight_service import GoalView, InsightView, goals, insights, mark_read
from app.llm import LLMUnavailable


def no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


router = APIRouter(tags=["agentes"], dependencies=[Depends(no_store)])


@contextmanager
def handled() -> Iterator[None]:
    try:
        yield
    except LLMUnavailable:
        raise HTTPException(409, "Conta ausente ou com exclusão pendente.") from None
    except (KeyError, ValueError, InvalidTag):
        raise HTTPException(503, "Configuração ou armazenamento indisponível.") from None


@router.put("/agents/{kind}", response_model=AgentView)
def put_agent(
    kind: AgentKind, data: AgentInput, identity: IdentityDep, engine: EngineDep
) -> AgentView:
    with handled():
        return configure(engine, identity.id, kind, data)


@router.get("/agents", response_model=list[AgentView])
def get_agents(identity: IdentityDep, engine: EngineDep) -> list[AgentView]:
    with handled():
        return list_agents(engine, identity.id)


@router.post("/goals", response_model=CreatedRecord, status_code=201)
def post_goal(data: GoalInput, identity: IdentityDep, engine: EngineDep) -> CreatedRecord:
    with handled():
        return CreatedRecord(id=create_goal(engine, identity.id, data))


@router.get("/goals", response_model=list[GoalView])
def get_goals(identity: IdentityDep, engine: EngineDep) -> list[GoalView]:
    with handled():
        return goals(engine, identity.id)


@router.get("/insights", response_model=list[InsightView])
def get_insights(
    identity: IdentityDep, engine: EngineDep, limit: Annotated[int, Query(ge=1, le=100)] = 50
) -> list[InsightView]:
    with handled():
        return insights(engine, identity.id, limit)


@router.post("/insights/{insight_id}/read", status_code=204)
def read_insight(insight_id: UUID, identity: IdentityDep, engine: EngineDep) -> None:
    with handled():
        mark_read(engine, identity.id, insight_id)


def internal_auth(credentials: CredentialsDep) -> None:
    expected = os.environ.get("AGENTS_RUN_TOKEN", "")
    if len(expected) < 32:
        raise HTTPException(503, "Execução interna não configurada.")
    if credentials is None or not hmac.compare_digest(credentials.credentials, expected):
        raise HTTPException(401, "Credencial operacional inválida.")


class RunInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_ids: list[UUID] = Field(min_length=1, max_length=25)


class RunResult(BaseModel):
    processed: int
    inserted: int
    sent: int


@router.post("/internal/agents/run", dependencies=[Depends(internal_auth)])
def run(data: RunInput, engine: EngineDep) -> RunResult:
    today = datetime.now(ZoneInfo("America/Sao_Paulo")).date()
    with handled():
        counts = [run_agents(engine, owner, today) for owner in dict.fromkeys(data.user_ids)]
        sent = sum(deliver_pending(engine, owner) for owner in dict.fromkeys(data.user_ids))
    return RunResult(processed=len(counts), inserted=sum(counts), sent=sent)
