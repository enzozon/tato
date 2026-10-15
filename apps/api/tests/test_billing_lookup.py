from datetime import UTC, datetime
from uuid import uuid4

import httpx
import pytest

from app.billing_resolution import find_reserved_checkout
from app.billing_stripe import BillingUnavailable, StripeSandbox


@pytest.mark.parametrize("defect", [None, "duplicate", "cycle", "client", "live"])
def test_lookup_paginates_without_recreating_and_requires_exact_binding(defect):
    owner, request_id = uuid4(), uuid4()
    row = {
        "id": "cs_test_found",
        "livemode": False,
        "mode": "subscription",
        "currency": "brl",
        "amount_total": 3900,
        "client_reference_id": str(owner),
        "metadata": {"user_id": str(owner), "request_id": str(request_id)},
        "status": "complete",
        "payment_status": "paid",
        "customer": "cus_demo",
        "subscription": "sub_demo",
    }
    calls = []

    def transport(request):
        calls.append(request)
        assert request.method == "GET" and request.url.path == "/v1/checkout/sessions"
        assert int(request.url.params["created[gte]"]) == 1791935700
        if len(calls) == 1:
            return httpx.Response(
                200,
                json={
                    "object": "list",
                    "has_more": True,
                    "data": [{"id": "cs_test_other", "livemode": False, "metadata": {}}],
                },
            )
        assert request.url.params["starting_after"] == "cs_test_other"
        if defect == "cycle":
            return httpx.Response(
                200,
                json={
                    "object": "list",
                    "has_more": True,
                    "data": [{"id": "cs_test_other", "livemode": False}],
                },
            )
        if defect == "client":
            row["client_reference_id"] = str(uuid4())
        if defect == "live":
            row["livemode"] = True
        return httpx.Response(
            200,
            json={
                "object": "list",
                "has_more": False,
                "data": [row, row] if defect == "duplicate" else [row],
            },
        )

    with httpx.Client(transport=httpx.MockTransport(transport)) as client:
        provider = StripeSandbox("sk_test_demo", "price_demo", client, "https://tato.example/")
        if defect is None:
            assert (
                find_reserved_checkout(
                    provider, owner, request_id, datetime(2026, 10, 14, tzinfo=UTC)
                ).id
                == row["id"]
            )
        else:
            with pytest.raises(BillingUnavailable):
                find_reserved_checkout(
                    provider, owner, request_id, datetime(2026, 10, 14, tzinfo=UTC)
                )
    assert len(calls) == 2


def test_lookup_absent_reservation_returns_none_without_creation():
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200, json={"object": "list", "has_more": False, "data": []}
            )
        )
    ) as client:
        provider = StripeSandbox("sk_test_demo", "price_demo", client, "https://tato.example/")
        assert find_reserved_checkout(provider, uuid4(), uuid4(), datetime.now(UTC)) is None
