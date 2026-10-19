"""Download completo, limitado e sem persistir uma cópia em disco."""

import json
from datetime import UTC, datetime
from uuid import UUID

from cryptography.exceptions import InvalidTag
from fastapi import APIRouter, HTTPException, Response
from sqlalchemy import Engine
from sqlmodel import col, select

from app.account_export_record import export_record
from app.account_routes import EngineDep, IdentityDep
from app.account_service import account_session
from app.crypto import load_key
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
    Reconciliation,
    Rule,
    Subscription,
    Transaction,
    User,
)
from app.plans import user_plan
from app.rate_limit import check_rate

router = APIRouter(prefix="/me", tags=["conta"])
MAX_EXPORT_BYTES = 64 * 1024 * 1024
MAX_EXPORT_ROWS = 100_000


def export_account(engine: Engine, owner: UUID) -> bytes:
    key = load_key("DATA_ENCRYPTION_KEY")
    body = bytearray()

    def append(value: str) -> None:
        encoded = value.encode("utf-8")
        if len(body) + len(encoded) > MAX_EXPORT_BYTES:
            raise HTTPException(
                409, "Exportação excede o limite técnico; solicite suporte operacional."
            )
        body.extend(encoded)

    with account_session(engine, owner) as session:
        user = session.get(User, owner)
        if user is None or user.deletion_requested_at is not None:
            raise HTTPException(409, "Conta ausente ou com exclusão pendente.")
        check_rate(owner, user_plan(session, owner).requests_per_minute)
        header = {
            "version": 1,
            "exported_at": datetime.now(UTC).isoformat(),
            "user": {
                "id": str(user.id),
                "created_at": user.created_at.isoformat(),
                "onboarding_completed_at": user.onboarding_completed_at.isoformat()
                if user.onboarding_completed_at is not None
                else None,
            },
        }
        append(json.dumps(header, ensure_ascii=False)[:-1])
        count = 0
        for name, model in (
            ("accounts", Account),
            ("categories", Category),
            ("transactions", Transaction),
            ("rules", Rule),
            ("goals", Goal),
            ("documents", Document),
            ("chunks", Chunk),
            ("chat_turns", ChatTurn),
            ("agents", Agent),
            ("insights", Insight),
            ("subscriptions", Subscription),
            ("billing_checkouts", BillingCheckout),
            ("llm_usage", LLMUsage),
            ("reconciliations", Reconciliation),
        ):
            append(f',"{name}":[')
            rows = session.exec(
                select(model)
                .where(model.user_id == owner)
                .order_by(col(model.id))
                .execution_options(yield_per=128)
            )
            first = True
            for row in rows:
                count += 1
                if count > MAX_EXPORT_ROWS:
                    raise HTTPException(
                        409, "Exportação excede o limite técnico; solicite suporte operacional."
                    )
                if not first:
                    append(",")
                append(
                    json.dumps(
                        export_record(row, key, owner),
                        ensure_ascii=False,
                        separators=(",", ":"),
                        allow_nan=False,
                    )
                )
                first = False
            append("]")
        append("}")
    return bytes(body)


@router.get("/export", response_class=Response)
def download_export(identity: IdentityDep, engine: EngineDep) -> Response:
    headers = {
        "Cache-Control": "no-store",
        "Content-Disposition": 'attachment; filename="tato-dados.json"',
    }
    try:
        content = export_account(engine, identity.id)
    except (InvalidTag, ValueError, KeyError):
        raise HTTPException(
            503, "Exportação temporariamente indisponível.", headers={"Cache-Control": "no-store"}
        ) from None
    except HTTPException as error:
        error.headers = {**(error.headers or {}), "Cache-Control": "no-store"}
        raise
    return Response(content, media_type="application/json", headers=headers)
