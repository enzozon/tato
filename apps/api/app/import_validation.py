from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func
from sqlmodel import Session, col, select

from app.import_parsers import ParsedEntry
from app.models import Document, Transaction


def require_document_space(session: Session, owner: UUID, content_bytes: int) -> None:
    stored = session.scalar(
        select(
            func.coalesce(func.sum(func.octet_length(col(Document.content_ciphertext))), 0)
        ).where(Document.user_id == owner)
    )
    if int(stored or 0) + content_bytes + 28 > 20 * 1024 * 1024:
        raise HTTPException(413, "Limite técnico de 20 MiB de documentos por usuário atingido.")


def validate_existing(
    entry: ParsedEntry, previous: Transaction, *, original_kind: str | None = None
) -> None:
    kind = entry.kind or ("expense" if entry.amount_cents < 0 else "income")
    if (previous.amount_cents, previous.booked_on, original_kind or previous.kind) != (
        entry.amount_cents,
        entry.booked_on,
        kind,
    ):
        raise HTTPException(409, "Identidade bancária existente com data ou valor divergente.")
