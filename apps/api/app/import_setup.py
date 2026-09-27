from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from sqlalchemy import Engine
from sqlmodel import select

from app.account_routes import EngineDep, IdentityDep
from app.account_service import account_session
from app.crypto import encrypt_text, load_key
from app.models import Account, Category, Rule, User
from app.plans import user_plan
from app.rate_limit import check_rate

router = APIRouter(tags=["configuração de importação"])
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
Pattern = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class AccountInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Name
    kind: Literal["checking", "savings", "credit_card", "cash"]
    opening_date: date
    opening_balance_cents: int = Field(default=0, strict=True, ge=-(2**63), lt=2**63)


class RuleInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    category: Name
    pattern: Pattern
    priority: int = Field(default=0, strict=True, ge=0, le=2**31 - 1)


class CreatedRecord(BaseModel):
    id: UUID


def create_record(engine: Engine, owner: UUID, data: AccountInput | RuleInput) -> CreatedRecord:
    with account_session(engine, owner) as session:
        user = session.get(User, owner)
        if user is None or user.deletion_requested_at is not None:
            raise HTTPException(409, "Inicialize /me antes; exclusão pendente bloqueia alterações.")
        check_rate(owner, user_plan(session, owner).requests_per_minute)
        try:
            key = load_key("DATA_ENCRYPTION_KEY")
        except (KeyError, ValueError):
            raise HTTPException(503, "Criptografia não configurada.") from None
        record: Account | Rule
        if isinstance(data, AccountInput):
            record = Account(
                user_id=owner,
                name_ciphertext=encrypt_text(data.name, key, owner, "account"),
                kind=data.kind,
                opening_date=data.opening_date,
                opening_balance_cents=data.opening_balance_cents,
            )
        else:
            count = session.exec(select(Rule.id).where(Rule.user_id == owner).limit(1000)).all()
            if len(count) >= 1000:
                raise HTTPException(409, "Limite técnico de 1000 regras atingido.")
            category = session.exec(
                select(Category).where(Category.user_id == owner, Category.name == data.category)
            ).first()
            if category is None:
                category = Category(user_id=owner, name=data.category)
                session.add(category)
                session.flush()
            record = Rule(
                user_id=owner,
                category_id=category.id,
                pattern_ciphertext=encrypt_text(data.pattern, key, owner, "rule"),
                priority=data.priority,
            )
        session.add(record)
        session.flush()
        result = CreatedRecord(id=record.id)
    return result


@router.post("/accounts", status_code=201, response_model=CreatedRecord)
def create_account(
    data: AccountInput, identity: IdentityDep, engine: EngineDep, response: Response
) -> CreatedRecord:
    response.headers["Cache-Control"] = "no-store"
    return create_record(engine, identity.id, data)


@router.post("/rules", status_code=201, response_model=CreatedRecord)
def create_rule(
    data: RuleInput, identity: IdentityDep, engine: EngineDep, response: Response
) -> CreatedRecord:
    response.headers["Cache-Control"] = "no-store"
    return create_record(engine, identity.id, data)
