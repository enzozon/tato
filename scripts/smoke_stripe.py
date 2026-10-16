"""Consulta o preço Stripe de teste sem criar checkout, cliente ou assinatura."""

import argparse
import os

import httpx

from app.billing_stripe import BillingUnavailable, StripeSandbox


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirm-test-mode", action="store_true")
    args = parser.parse_args(argv)
    if not args.confirm_test_mode:
        print("Ensaio não executado: confirme o sandbox com --confirm-test-mode.")
        return 2
    key = os.environ.get("STRIPE_SECRET_KEY", "")
    price = os.environ.get("STRIPE_PRICE_ID", "")
    return_url = os.environ.get("BILLING_RETURN_URL", "")
    if not key or not price or not return_url:
        print("Configuração ausente: STRIPE_SECRET_KEY, STRIPE_PRICE_ID ou BILLING_RETURN_URL.")
        return 1
    try:
        with httpx.Client(trust_env=False) as client:
            StripeSandbox(key, price, client, return_url).require_price()
    except BillingUnavailable:
        print(
            "Stripe inválido ou indisponível: confira sk_test_, preço BRL 39/mês e URL de retorno."
        )
        return 1
    print("Preço sandbox validado: BRL 39/mês. Checkout, webhook e pagamento não exercitados.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
