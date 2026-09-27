import hashlib
from typing import Literal
from uuid import UUID

from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy import Engine, func
from sqlmodel import Session, col, select

from app.account_service import account_session
from app.categorization import load_rules, match_category
from app.crypto import dedup_key, encrypt_text, load_key
from app.import_parsers import CsvMapping, ParsedEntry, decode_file, parse_csv
from app.models import Account, Document, Transaction, User
from app.ofx_parser import parse_ofx
from app.pdf_extract import extract_pdf
from app.pdf_parser import parse_invoice
from app.plans import require_capacity, user_plan
from app.rate_limit import check_rate
from app.repositories import TransactionInput, add_transaction

ImportKind = Literal["csv", "ofx", "pdf"]


class ImportResult(BaseModel):
    document_id: UUID
    inserted: int
    duplicates: int
    uncategorized: int
    warning: str | None = None


def active_account(session: Session, owner: UUID, account_id: UUID) -> None:
    user = session.get(User, owner)
    if user is None or user.deletion_requested_at is not None:
        raise HTTPException(409, "Conta ausente ou com exclusão pendente.")
    account = session.get(Account, account_id)
    if account is None or account.user_id != owner:
        raise HTTPException(404, "Conta de origem não encontrada.")


def authorize_import(engine: Engine, owner: UUID, account_id: UUID) -> None:
    with account_session(engine, owner) as session:
        active_account(session, owner, account_id)
        check_rate(owner, user_plan(session, owner).requests_per_minute)


def parse_upload(
    content: bytes, kind: ImportKind, mapping: CsvMapping | None
) -> tuple[str, list[ParsedEntry]]:
    if kind == "pdf":
        text = extract_pdf(content)
        return text, parse_invoice(text, content)
    text = decode_file(content)
    return text, parse_csv(content, mapping) if kind == "csv" else parse_ofx(content)


def store_import(
    engine: Engine,
    owner: UUID,
    account_id: UUID,
    content: bytes,
    filename: str,
    kind: ImportKind,
    mapping: CsvMapping | None = None,
) -> ImportResult:
    authorize_import(engine, owner, account_id)
    text, entries = parse_upload(content, kind, mapping)
    cipher_key, identity_key = load_key("DATA_ENCRYPTION_KEY"), load_key("DEDUP_HMAC_KEY")
    digest = dedup_key(
        identity_key, owner, account_id, f"document:{kind}:" + hashlib.sha256(content).hexdigest()
    )
    warning = (
        "Sem ID bancário: arquivos diferentes podem sobrepor lançamentos; revise os períodos."
        if any(e.source_identity.startswith(("csv:", "pdf:")) for e in entries)
        else None
    )
    with account_session(engine, owner) as session:
        active_account(session, owner, account_id)
        previous = session.exec(
            select(Document).where(Document.user_id == owner, Document.digest == digest)
        ).first()
        if previous:
            return ImportResult(
                document_id=previous.id,
                inserted=0,
                duplicates=len(entries),
                uncategorized=0,
                warning=warning,
            )
        sources = session.exec(
            select(col(Document.account_id))
            .where(Document.user_id == owner, col(Document.account_id).is_not(None))
            .distinct()
        ).all()
        if account_id not in sources:
            require_capacity(user_plan(session, owner), "import_sources", len(sources))
        stored = session.scalar(
            select(
                func.coalesce(func.sum(func.octet_length(col(Document.content_ciphertext))), 0)
            ).where(Document.user_id == owner)
        )
        if int(stored or 0) + len(text.encode()) + 28 > 20 * 1024 * 1024:
            raise HTTPException(413, "Limite técnico de 20 MiB de documentos por usuário atingido.")
        document = Document(
            user_id=owner,
            account_id=account_id,
            kind=kind,
            digest=digest,
            name_ciphertext=encrypt_text(filename[:255], cipher_key, owner, "document_name"),
            content_ciphertext=encrypt_text(text, cipher_key, owner, "document"),
        )
        session.add(document)
        session.flush()
        keys = [dedup_key(identity_key, owner, account_id, e.source_identity) for e in entries]
        existing = {
            row.dedup_key: row
            for row in session.exec(
                select(Transaction).where(
                    Transaction.user_id == owner,
                    Transaction.account_id == account_id,
                    col(Transaction.dedup_key).in_(keys),
                )
            ).all()
        }
        rules = load_rules(session, owner, cipher_key)
        inserted = duplicates = uncategorized = 0
        for entry, key in zip(entries, keys, strict=True):
            entry_kind = entry.kind or ("expense" if entry.amount_cents < 0 else "income")
            if old := existing.get(key):
                if (old.amount_cents, old.booked_on, old.kind) != (
                    entry.amount_cents,
                    entry.booked_on,
                    entry_kind,
                ):
                    raise HTTPException(
                        409, "Identidade bancária existente com data ou valor divergente."
                    )
                duplicates += 1
                continue
            category = match_category(entry.description, rules)
            data = TransactionInput(
                account_id=account_id,
                category_id=category,
                booked_on=entry.booked_on,
                amount_cents=entry.amount_cents,
                kind=entry_kind,
                description=entry.description,
                source_identity=entry.source_identity,
            )
            if add_transaction(
                session, owner, data, cipher_key, identity_key, document_id=document.id
            ):
                inserted += 1
                uncategorized += int(category is None)
            else:
                duplicates += 1
        result = ImportResult(
            document_id=document.id,
            inserted=inserted,
            duplicates=duplicates,
            uncategorized=uncategorized,
            warning=warning,
        )
    return result
