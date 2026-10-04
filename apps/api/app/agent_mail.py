import os
from datetime import UTC, datetime, timedelta
from uuid import UUID

import httpx
from fastapi import HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import Engine
from sqlmodel import col, select

from app.account_service import account_session
from app.auth import service_key, service_url
from app.llm_service import require_active
from app.mascot import identity
from app.models import Agent, Insight
from app.plans import user_plan


class VerifiedContact(BaseModel):
    id: UUID
    email: str = Field(min_length=3, max_length=254, repr=False)
    email_confirmed_at: datetime


def send_notice(owner: UUID, insight_id: UUID) -> bool:
    """Só envia assunto genérico ao endereço confirmado da identidade correta."""
    if (
        os.environ.get("AGENT_EMAIL_ENABLED") != "true"
        or os.environ.get("RESEND_FREE_TIER_CONFIRMED") != "true"
    ):
        return False
    try:
        with httpx.Client(timeout=5, follow_redirects=False, trust_env=False) as client:
            key = service_key("SUPABASE_SECRET_KEY")
            response = client.get(
                f"{service_url('SUPABASE_URL')}/auth/v1/admin/users/{owner}",
                headers={"apikey": key, "Authorization": f"Bearer {key}"},
            )
            response.raise_for_status()
            contact = VerifiedContact.model_validate(response.json())
            if (
                contact.id != owner
                or "@" not in contact.email
                or any(character in contact.email for character in "\r\n,;<> ")
            ):
                return False
            name = str(identity()["name"])
            response = client.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {service_key('RESEND_API_KEY')}",
                    "Idempotency-Key": f"agent-notice/{insight_id}",
                },
                json={
                    "from": service_key("RESEND_FROM"),
                    "to": [contact.email],
                    "subject": f"Novo aviso de {name}",
                    "text": f"Há um novo aviso disponível na sua conta de {name}.",
                },
            )
            response.raise_for_status()
            UUID(response.json()["id"])
            return True
    except (httpx.HTTPError, HTTPException, ValueError, KeyError, TypeError):
        return False


def eligible(row: Insight, now: datetime) -> bool:
    if row.email_status != "pending" or row.email_attempts >= 3:
        return False
    # Retenção da chave Resend é 24h. Usar criação é conservador após timeout/crash.
    if row.email_attempts and now - row.created_at >= timedelta(hours=23):
        return False
    return row.email_last_attempt_at is None or now - row.email_last_attempt_at >= timedelta(
        minutes=2
    )


def deliver_pending(engine: Engine, owner: UUID) -> int:
    if (
        os.environ.get("AGENT_EMAIL_ENABLED") != "true"
        or os.environ.get("RESEND_FREE_TIER_CONFIRMED") != "true"
    ):
        return 0
    now = datetime.now(UTC)
    with account_session(engine, owner) as session:
        require_active(session, owner)
        rows = session.exec(
            select(Insight)
            .where(
                Insight.user_id == owner,
                Insight.email_status == "pending",
                Insight.email_attempts < 3,
            )
            .order_by(col(Insight.created_at), col(Insight.id))
            .limit(100)
        ).all()
        claimed = []
        for row in rows:
            if eligible(row, now):
                row.email_attempts += 1
                row.email_last_attempt_at = now
                session.add(row)
                claimed.append(row.id)
                if len(claimed) == 5:
                    break
    sent = 0
    for insight_id in claimed:
        with account_session(engine, owner) as session:
            require_active(session, owner)
            claimed_row = session.get(Insight, insight_id)
            if (
                claimed_row is None
                or claimed_row.user_id != owner
                or claimed_row.email_status != "pending"
            ):
                continue
            active = session.exec(
                select(Agent)
                .where(Agent.user_id == owner, col(Agent.enabled).is_(True))
                .order_by(col(Agent.created_at), col(Agent.id))
                .limit(user_plan(session, owner).agents)
            ).all()
            agent = next((item for item in active if item.kind == claimed_row.agent_kind), None)
            if agent is None or not agent.email_enabled:
                claimed_row.email_status = "off"
            elif send_notice(owner, insight_id):
                claimed_row.email_status, claimed_row.email_sent_at = "sent", datetime.now(UTC)
                sent += 1
            session.add(claimed_row)
    return sent
