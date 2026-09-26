"""Retoma somente exclusão já solicitada, sem exigir token de um login removido."""

import argparse
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError

from app.account_routes import runtime_engine
from app.account_service import finish_deletion

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("user_id", type=UUID)
    args = parser.parse_args()
    try:
        finish_deletion(runtime_engine(), args.user_id)
    except (HTTPException, SQLAlchemyError, ValueError, PermissionError):
        raise SystemExit(
            "Retomada não concluída. Confira configuração e serviços, sem expor chaves."
        ) from None
    print("Exclusão concluída ou conta já ausente.")
