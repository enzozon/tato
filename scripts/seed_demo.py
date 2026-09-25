"""Insere exemplo local; não altera dados existentes nem acessa provedores."""

import os
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import make_url

from app.crypto import load_key
from app.database import app_engine
from app.seed_data import demo_records

url = os.environ["DATABASE_MIGRATION_URL"]
parsed = make_url(url)
if parsed.host not in {"localhost", "127.0.0.1"} or parsed.database not in {"tato", "tato_test"}:
    raise SystemExit("Seed permitido somente no banco local tato/tato_test.")
engine = app_engine(url)
owner = uuid5(NAMESPACE_URL, "tato:demo")
records = demo_records(owner, load_key("DATA_ENCRYPTION_KEY"), load_key("DEDUP_HMAC_KEY"))
with engine.begin() as connection:
    for record in records:
        connection.execute(
            insert(type(record)).values(**record.model_dump()).on_conflict_do_nothing()
        )
engine.dispose()
print("Seed sintético concluído; registros existentes preservados.")
