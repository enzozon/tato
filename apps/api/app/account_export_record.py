"""Exportação explícita dos dados pessoais armazenados pelo Tato."""

from datetime import date, datetime
from uuid import UUID

from app.crypto import decrypt_text
from app.models import (
    Account,
    Agent,
    BillingCheckout,
    Category,
    ChatTurn,
    Chunk,
    Document,
    Goal,
    Insight,
    LLMUsage,
    Rule,
    Subscription,
    Transaction,
)
from app.models.base import TenantRecord


def export_record(row: TenantRecord, key: bytes, owner: UUID) -> dict[str, object]:
    result: dict[str, object] = {"id": str(row.id), "created_at": row.created_at.isoformat()}
    match row:
        case Account():
            result.update(
                name=decrypt_text(row.name_ciphertext, key, owner, "account"),
                kind=row.kind,
                currency=row.currency,
                opening_date=row.opening_date,
                opening_balance_cents=str(row.opening_balance_cents),
            )
        case Category():
            result.update(name=row.name)
        case Transaction():
            result.update(
                account_id=row.account_id,
                document_id=row.document_id,
                category_id=row.category_id,
                booked_on=row.booked_on,
                amount_cents=str(row.amount_cents),
                kind=row.kind,
                description=decrypt_text(row.description_ciphertext, key, owner, "transaction"),
            )
        case Rule():
            result.update(
                pattern=decrypt_text(row.pattern_ciphertext, key, owner, "rule"),
                category_id=row.category_id,
                priority=row.priority,
                enabled=row.enabled,
            )
        case Goal():
            result.update(
                description=decrypt_text(row.description_ciphertext, key, owner, "goal"),
                target_cents=str(row.target_cents),
                due_on=row.due_on,
            )
        case Document():
            result.update(
                name=decrypt_text(row.name_ciphertext, key, owner, "document_name"),
                content=decrypt_text(row.content_ciphertext, key, owner, "document"),
                account_id=row.account_id,
                kind=row.kind,
            )
        case Chunk():
            result.update(
                content=decrypt_text(row.content_ciphertext, key, owner, "chunk"),
                document_id=row.document_id,
                position=row.position,
            )
        case ChatTurn():
            result.update(
                request=decrypt_text(row.request_ciphertext, key, owner, "chat_request"),
                response=decrypt_text(row.response_ciphertext, key, owner, "chat_response")
                if row.response_ciphertext is not None
                else None,
                status=row.status,
                completed_at=row.completed_at,
            )
        case Agent():
            result.update(
                kind=row.kind,
                enabled=row.enabled,
                account_id=row.account_id,
                goal_id=row.goal_id,
                email_enabled=row.email_enabled,
            )
        case Insight():
            result.update(
                content=decrypt_text(row.content_ciphertext, key, owner, "insight"),
                agent_kind=row.agent_kind,
                read_at=row.read_at,
                email_status=row.email_status,
                email_attempts=row.email_attempts,
                email_last_attempt_at=row.email_last_attempt_at,
                email_sent_at=row.email_sent_at,
            )
        case Subscription():
            result.update(
                plan=row.plan,
                status=row.status,
                provider=row.billing_provider,
                valid_until=row.valid_until,
            )
        case BillingCheckout():
            result.update(
                provider=row.provider,
                amount_cents=str(row.amount_cents),
                status=row.status,
                completed_at=row.completed_at,
            )
        case LLMUsage():
            result.update(
                provider=row.provider,
                outcome=row.outcome,
                input_tokens=row.input_tokens,
                output_tokens=row.output_tokens,
                elapsed_ms=row.elapsed_ms,
            )
        case _:
            raise ValueError("Tipo de registro não exportável.")
    return {
        name: value.isoformat()
        if isinstance(value, (date, datetime))
        else str(value)
        if isinstance(value, UUID)
        else value
        for name, value in result.items()
    }
