from datetime import date
from typing import cast
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import Engine, func
from sqlmodel import Session, col, select

from app.account_service import account_session
from app.agent_rules import AgentKind, Movement, Snapshot, evaluate, month_start
from app.crypto import decrypt_text, dedup_key, encrypt_text, load_key
from app.import_service import active_account
from app.llm_service import require_active
from app.models import Account, Agent, Goal, Insight, Transaction
from app.plans import user_plan


def load_snapshot(session: Session, owner: UUID, agent: Agent, today: date, key: bytes) -> Snapshot:
    active_account(session, owner, agent.account_id)
    account = session.get(Account, agent.account_id)
    assert account is not None
    if account.opening_date > today:
        raise HTTPException(409, "Conta ainda não iniciou seu período de acompanhamento.")
    total = session.exec(
        select(func.coalesce(func.sum(col(Transaction.amount_cents)), 0)).where(
            Transaction.user_id == owner,
            Transaction.account_id == account.id,
            Transaction.booked_on >= account.opening_date,
            Transaction.booked_on <= today,
        )
    ).one()
    rows = session.exec(
        select(Transaction)
        .where(
            Transaction.user_id == owner,
            Transaction.account_id == account.id,
            Transaction.booked_on >= month_start(today, -3),
            Transaction.booked_on <= today,
        )
        .order_by(col(Transaction.booked_on), col(Transaction.id))
        .limit(5001)
    ).all()
    if len(rows) > 5000:
        raise HTTPException(409, "Histórico excede o limite técnico da avaliação de agentes.")
    movements = [
        Movement(
            row.booked_on,
            row.amount_cents,
            row.kind,
            row.category_id,
            decrypt_text(row.description_ciphertext, key, owner, "transaction")
            if agent.kind == "subscription_watch"
            else "",
        )
        for row in rows
    ]
    return Snapshot(
        account.id,
        today,
        account.opening_date,
        account.opening_balance_cents + int(total),
        movements,
    )


def run_agents(engine: Engine, owner: UUID, today: date) -> int:
    key, identity_key = load_key("DATA_ENCRYPTION_KEY"), load_key("DEDUP_HMAC_KEY")
    inserted = 0
    with account_session(engine, owner) as session:
        require_active(session, owner)
        agents = session.exec(
            select(Agent)
            .where(
                Agent.user_id == owner,
                Agent.enabled == True,  # noqa: E712 — expressão SQL
            )
            .order_by(col(Agent.created_at), col(Agent.id))
        ).all()
        for agent in agents[: user_plan(session, owner).agents]:
            snapshot = load_snapshot(session, owner, agent, today, key)
            goal = session.get(Goal, agent.goal_id) if agent.goal_id else None
            if goal is not None and goal.user_id != owner:
                raise HTTPException(404, "Meta não encontrada.")
            signals = evaluate(
                cast(AgentKind, agent.kind), snapshot, goal.target_cents if goal else None
            )
            for signal in signals:
                # Um aviso por condição/mês; meta por alvo. Nomes não ficam em chaves em claro.
                period = str(goal.target_cents) if goal else today.strftime("%Y-%m")
                identity = f"agent:v1:{agent.id}:{agent.goal_id}:{period}:{signal.subject}"
                event_key = dedup_key(identity_key, owner, agent.account_id, identity)
                old = session.exec(
                    select(Insight.id).where(
                        Insight.user_id == owner,
                        Insight.event_key == event_key,
                    )
                ).first()
                if old is not None:
                    continue
                session.add(
                    Insight(
                        user_id=owner,
                        agent_kind=agent.kind,
                        event_key=event_key,
                        content_ciphertext=encrypt_text(
                            signal.model_dump_json(), key, owner, "insight"
                        ),
                        email_status="pending" if agent.email_enabled else "off",
                    )
                )
                session.flush()
                inserted += 1
    return inserted
