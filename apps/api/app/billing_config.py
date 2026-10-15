import os

import httpx

from app.billing_stripe import StripeSandbox


def provider_for(client: httpx.Client) -> StripeSandbox:
    return StripeSandbox(
        os.environ.get("STRIPE_SECRET_KEY", ""),
        os.environ.get("STRIPE_PRICE_ID", ""),
        client,
        os.environ.get("BILLING_RETURN_URL", ""),
    )
