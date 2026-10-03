import hashlib
import hmac
import json
import time
from datetime import date
from uuid import UUID

from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy import Engine

from app.account_service import account_session
from app.crypto import dedup_key, load_key
from app.import_parsers import CsvMapping, ParsedEntry
from app.import_service import ImportKind, active_account, authorize_import, parse_upload


class PreviewEntry(BaseModel):
    booked_on: date
    amount_cents: int
    description: str


class ImportPreview(BaseModel):
    account_id: UUID
    kind: ImportKind
    count: int
    start: date
    end: date
    credits_cents: int
    debits_cents: int
    entries: list[PreviewEntry]
    truncated: bool
    receipt: str
    warning: str = (
        "Prévia bruta: duplicatas e limites serão conferidos na confirmação. "
        "Revise sinais, datas e descrições. Arquivos diferentes sem ID bancário podem se sobrepor."
    )


def signature(
    owner: UUID,
    account: UUID,
    content: bytes,
    kind: ImportKind,
    mapping: CsvMapping | None,
    entries: list[ParsedEntry],
    expires: int,
) -> str:
    payload = json.dumps(
        {
            "file": hashlib.sha256(content).hexdigest(),
            "kind": kind,
            "mapping": mapping.model_dump() if mapping else None,
            "entries": [entry.model_dump(mode="json") for entry in entries],
            "expires": expires,
        },
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(payload.encode()).hexdigest()
    return dedup_key(load_key("DEDUP_HMAC_KEY"), owner, account, "preview:v1:" + digest)


def preview_import(
    engine: Engine,
    owner: UUID,
    account: UUID,
    content: bytes,
    kind: ImportKind,
    mapping: CsvMapping | None,
    receipt: str | None = None,
) -> ImportPreview:
    authorize_import(engine, owner, account, kind)
    _, entries = parse_upload(content, kind, mapping)
    expires = int(time.time()) + 900
    if receipt is not None:
        try:
            raw_expiry, received = receipt.split(".", 1)
            expires = int(raw_expiry)
            valid = 0 < expires - time.time() <= 900 and hmac.compare_digest(
                received, signature(owner, account, content, kind, mapping, entries, expires)
            )
        except (ValueError, OverflowError):
            valid = False
        if not valid:
            raise HTTPException(409, "Prévia expirada ou divergente. Revise o arquivo novamente.")
    token = f"{expires}.{signature(owner, account, content, kind, mapping, entries, expires)}"
    with account_session(engine, owner) as session:
        active_account(session, owner, account)
    return ImportPreview(
        account_id=account,
        kind=kind,
        count=len(entries),
        start=min(entry.booked_on for entry in entries),
        end=max(entry.booked_on for entry in entries),
        credits_cents=sum(max(0, entry.amount_cents) for entry in entries),
        debits_cents=-sum(min(0, entry.amount_cents) for entry in entries),
        entries=[PreviewEntry(**entry.model_dump()) for entry in entries[:50]],
        truncated=len(entries) > 50,
        receipt=token,
    )
