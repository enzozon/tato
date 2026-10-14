"""Reconciliação administrativa explícita, sem criar cobranças remotas."""

import argparse
from uuid import UUID

import httpx
from sqlalchemy.exc import SQLAlchemyError

from app.billing_database import billing_engine
from app.billing_events import reconcile
from app.billing_routes import provider_for
from app.billing_stripe import BillingUnavailable


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Reconcilia reserva Stripe de teste existente.")
    parser.add_argument("--owner", type=UUID, required=True)
    parser.add_argument("--request-id", type=UUID, required=True)
    parser.add_argument("--confirm-sandbox", action="store_true")
    args = parser.parse_args(argv)
    if not args.confirm_sandbox:
        parser.error("Confirme explicitamente o uso do sandbox.")
    try:
        with httpx.Client(trust_env=False) as client:
            reconcile(billing_engine(), provider_for(client), args.owner, args.request_id)
    except (BillingUnavailable, PermissionError, SQLAlchemyError):
        raise SystemExit("Reconciliação não concluída; referências locais preservadas.") from None
    print("Reconciliação de teste concluída.")


if __name__ == "__main__":
    main()
