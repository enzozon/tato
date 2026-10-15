from unittest.mock import Mock
from uuid import uuid4

import httpx
import pytest

from app.billing_cleanup import cleanup, customer_request, expire_checkout
from app.billing_stripe import API_VERSION, BillingUnavailable, StripeSandbox
from app.models import BillingCheckout, Subscription


def provider(client):
    return StripeSandbox("sk_test_synthetic", "price_test", client, "https://tato.example/app/")


def checkout_payload(owner, request_id, **changes):
    return {
        "id": "cs_test_demo",
        "livemode": False,
        "mode": "subscription",
        "currency": "brl",
        "amount_total": 3900,
        "client_reference_id": str(owner),
        "metadata": {"user_id": str(owner), "request_id": str(request_id)},
        "status": "open",
        "payment_status": "unpaid",
        "url": "https://checkout.stripe.com/c/pay/demo",
        **changes,
    }


@pytest.mark.parametrize("deleted", [False, True])
def test_customer_supports_alive_and_deleted_without_generic_relaxation(deleted):
    calls = []

    def transport(request):
        calls.append(request)
        assert request.headers["Stripe-Version"] == API_VERSION
        assert request.url.path == "/v1/customers/cus_demo"
        payload = {"id": "cus_demo", "object": "customer"}
        payload.update(
            {"deleted": True} if deleted or request.method == "DELETE" else {"livemode": False}
        )
        return httpx.Response(200, json=payload)

    with httpx.Client(transport=httpx.MockTransport(transport)) as client:
        stripe = provider(client)
        assert customer_request(stripe, "GET", "cus_demo") is deleted
        if not deleted:
            assert customer_request(stripe, "DELETE", "cus_demo")
        with pytest.raises(BillingUnavailable):
            stripe.request("DELETE", "customers/cus_demo")
    assert len(calls) == (2 if deleted else 3)


@pytest.mark.parametrize(
    "payload",
    [
        {"id": "cus_other", "object": "customer", "deleted": True},
        {"id": "cus_demo", "object": "subscription", "deleted": True},
        {"id": "cus_demo", "object": "customer", "deleted": 1},
        {"id": "cus_demo", "object": "customer", "livemode": True},
        {"id": "cus_demo", "object": "customer", "livemode": 0},
        {"id": "cus_demo", "object": "customer"},
        {"id": "cus_demo", "object": "customer", "deleted": True, "livemode": True},
        [],
    ],
)
def test_invalid_customer_never_passes(payload):
    with (
        httpx.Client(
            transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload))
        ) as client,
        pytest.raises(BillingUnavailable),
    ):
        customer_request(provider(client), "GET", "cus_demo")


def test_customer_request_rejects_bad_mode_reference_redirect_and_private_error():
    calls = []

    def transport(request):
        calls.append(request)
        return httpx.Response(307, text="privado", headers={"Location": "https://evil.example"})

    with httpx.Client(transport=httpx.MockTransport(transport), follow_redirects=True) as client:
        stripe = provider(client)
        for method, reference in [("POST", "cus_demo"), ("GET", "cus_demo/other")]:
            with pytest.raises(BillingUnavailable):
                customer_request(stripe, method, reference)
        with pytest.raises(BillingUnavailable) as error:
            customer_request(stripe, "GET", "cus_demo")
        assert "privado" not in str(error.value)
        stripe.key = "sk_live_synthetic"
        with pytest.raises(BillingUnavailable):
            customer_request(stripe, "GET", "cus_demo")
    assert len(calls) == 1


@pytest.mark.parametrize("status", ["expired", "complete", "open"])
def test_expire_handles_race_but_preserves_open_failure(status):
    owner, request_id = uuid4(), uuid4()
    calls = []

    def transport(request):
        calls.append(request.method)
        if request.method == "POST":
            return httpx.Response(400, text="privado")
        return httpx.Response(200, json=checkout_payload(owner, request_id, status=status))

    with httpx.Client(transport=httpx.MockTransport(transport)) as client:
        stripe = provider(client)
        remote = stripe.validate_checkout(checkout_payload(owner, request_id), owner, request_id)
        if status == "open":
            with pytest.raises(BillingUnavailable):
                expire_checkout(stripe, remote, owner, request_id)
        else:
            assert expire_checkout(stripe, remote, owner, request_id).status == status
    assert calls == ["POST", "GET"]


def test_expire_requires_expected_id_and_expired_response():
    owner, request_id = uuid4(), uuid4()
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda _: httpx.Response(
                200, json=checkout_payload(owner, request_id, id="cs_test_other", status="expired")
            )
        )
    ) as client:
        stripe = provider(client)
        remote = stripe.validate_checkout(checkout_payload(owner, request_id), owner, request_id)
        with pytest.raises(BillingUnavailable):
            expire_checkout(stripe, remote, owner, request_id)


def local_session(owner, rows, subscription=None):
    session = Mock()
    session.exec.side_effect = [Mock(first=lambda: subscription), Mock(all=lambda: rows)]
    return session


def assert_read_only_owner(session, owner):
    assert session.exec.call_count == 2
    for call in session.exec.call_args_list:
        statement = call.args[0]
        assert list(statement.compile().params.values()) == [owner]
    session.delete.assert_not_called()
    session.add.assert_not_called()
    session.commit.assert_not_called()
    session.close.assert_not_called()


@pytest.mark.parametrize("tombstone", [False, True])
def test_cleanup_discovers_completed_customer_deduplicates_and_preserves_sql(tombstone):
    owner = uuid4()
    rows = [
        BillingCheckout(
            user_id=owner,
            provider="stripe",
            request_id=uuid4(),
            external_id=f"cs_test_{index}",
            amount_cents=3900,
        )
        for index in range(2)
    ]
    subscription = Subscription(
        user_id=owner,
        billing_provider="stripe",
        external_id="sub_demo",
        external_customer_id="cus_demo",
    )
    session = local_session(owner, rows, subscription)
    calls = []

    def transport(request):
        calls.append((request.method, request.url.path))
        if "checkout/sessions/" in request.url.path:
            row = next(row for row in rows if request.url.path.endswith(row.external_id))
            return httpx.Response(
                200,
                json=checkout_payload(
                    owner,
                    row.request_id,
                    id=row.external_id,
                    status="complete",
                    customer="cus_demo",
                    subscription="sub_demo",
                ),
            )
        payload = {"id": "cus_demo", "object": "customer"}
        payload.update(
            {"deleted": True} if tombstone or request.method == "DELETE" else {"livemode": False}
        )
        return httpx.Response(200, json=payload)

    with httpx.Client(transport=httpx.MockTransport(transport)) as client:
        cleanup(session, owner, provider(client))
    assert calls.count(("GET", "/v1/customers/cus_demo")) == 1
    assert calls.count(("DELETE", "/v1/customers/cus_demo")) == (0 if tombstone else 1)
    assert_read_only_owner(session, owner)


@pytest.mark.parametrize("found", [False, True])
def test_cleanup_reservation_without_id_never_creates_and_fails_closed_if_missing(found):
    owner, request_id = uuid4(), uuid4()
    row = BillingCheckout(
        user_id=owner, provider="stripe", request_id=request_id, amount_cents=3900
    )
    session = local_session(owner, [row])
    remote = checkout_payload(owner, request_id, status="complete", customer="cus_demo")
    calls = []

    def transport(request):
        calls.append((request.method, request.url.path))
        if request.url.path == "/v1/checkout/sessions":
            return httpx.Response(
                200, json={"object": "list", "has_more": False, "data": [remote] if found else []}
            )
        if request.url.path == "/v1/checkout/sessions/cs_test_demo":
            return httpx.Response(200, json=remote)
        return httpx.Response(200, json={"id": "cus_demo", "object": "customer", "deleted": True})

    with httpx.Client(transport=httpx.MockTransport(transport)) as client:
        if found:
            cleanup(session, owner, provider(client))
        else:
            with pytest.raises(BillingUnavailable):
                cleanup(session, owner, provider(client))
    assert all(method == "GET" for method, _ in calls)
    assert row.external_id is None and row.status == "pending"
    assert_read_only_owner(session, owner)


@pytest.mark.parametrize("invalid", ["owner", "subscription", "live", "customer", "delete"])
def test_cleanup_failures_preserve_references_and_sanitize_error(invalid):
    owner, request_id = uuid4(), uuid4()
    row = BillingCheckout(
        user_id=owner,
        provider="stripe",
        request_id=request_id,
        external_id="cs_test_demo",
        amount_cents=3900,
    )
    subscription = Subscription(
        user_id=owner,
        billing_provider="stripe",
        external_id="sub_demo",
        external_customer_id="cus_demo",
    )
    session = local_session(owner, [row], subscription)
    calls = []

    def transport(request):
        calls.append(request)
        if "checkout/sessions" in request.url.path:
            remote = checkout_payload(
                owner,
                request_id,
                status="complete",
                customer="cus_demo",
                subscription="sub_other" if invalid == "subscription" else "sub_demo",
            )
            if invalid == "owner":
                remote["client_reference_id"] = str(uuid4())
            if invalid == "live":
                remote["livemode"] = True
            return httpx.Response(200, json=remote)
        if request.method == "DELETE":
            return httpx.Response(503, text="privado")
        return httpx.Response(
            200, json={"id": "cus_demo", "object": "customer", "livemode": invalid == "customer"}
        )

    with (
        httpx.Client(transport=httpx.MockTransport(transport)) as client,
        pytest.raises(BillingUnavailable) as error,
    ):
        cleanup(session, owner, provider(client))
    assert "privado" not in str(error.value)
    assert row.external_id == "cs_test_demo" and subscription.external_customer_id == "cus_demo"
    assert sum(request.method == "DELETE" for request in calls) == (1 if invalid == "delete" else 0)
    assert_read_only_owner(session, owner)


def test_cleanup_free_synthetic_account_uses_no_remote_provider():
    owner = uuid4()
    session = local_session(owner, [], Subscription(user_id=owner))
    with httpx.Client(
        transport=httpx.MockTransport(lambda _: pytest.fail("Chamada inesperada"))
    ) as client:
        cleanup(session, owner, provider(client))
    assert_read_only_owner(session, owner)


@pytest.mark.parametrize("race", [False, True])
def test_cleanup_expires_open_checkout_before_customer_removal(race):
    owner, request_id = uuid4(), uuid4()
    row = BillingCheckout(
        user_id=owner,
        provider="stripe",
        request_id=request_id,
        external_id="cs_test_demo",
        amount_cents=3900,
    )
    session = local_session(owner, [row])
    calls = []

    def transport(request):
        calls.append((request.method, request.url.path))
        if "customers/" in request.url.path:
            assert race and len(calls) == 4
            return httpx.Response(
                200, json={"id": "cus_demo", "object": "customer", "deleted": True}
            )
        if request.method == "POST" and race:
            return httpx.Response(400)
        status = "open" if len(calls) == 1 else "complete" if race else "expired"
        return httpx.Response(
            200,
            json=checkout_payload(
                owner,
                request_id,
                status=status,
                customer="cus_demo" if status == "complete" else None,
            ),
        )

    with httpx.Client(transport=httpx.MockTransport(transport)) as client:
        cleanup(session, owner, provider(client))
    assert calls[1] == ("POST", "/v1/checkout/sessions/cs_test_demo/expire")
    assert len(calls) == (4 if race else 2)
    assert_read_only_owner(session, owner)


@pytest.mark.parametrize("missing", ["customer", "binding", "provider"])
def test_cleanup_rejects_unresolved_links_before_deleting_customer(missing):
    owner, request_id = uuid4(), uuid4()
    row = BillingCheckout(
        user_id=owner,
        provider="stripe",
        request_id=request_id,
        external_id="cs_test_demo",
        amount_cents=3900,
    )
    subscription = Subscription(user_id=owner, billing_provider="stripe")
    if missing == "provider":
        row.provider = "abacatepay"
    session = local_session(owner, [row], subscription)

    def transport(request):
        assert request.method == "GET" and "checkout/sessions/" in request.url.path
        return httpx.Response(
            200,
            json=checkout_payload(
                owner,
                request_id,
                status="complete",
                customer=None if missing == "customer" else "cus_demo",
            ),
        )

    with (
        httpx.Client(transport=httpx.MockTransport(transport)) as client,
        pytest.raises(BillingUnavailable),
    ):
        cleanup(session, owner, provider(client))
    assert_read_only_owner(session, owner)


@pytest.mark.parametrize("initial_status", ["open", "expired"])
def test_cleanup_removes_customer_left_by_incomplete_confirmation(initial_status):
    owner, request_id = uuid4(), uuid4()
    row = BillingCheckout(
        user_id=owner,
        provider="stripe",
        request_id=request_id,
        external_id="cs_test_demo",
        amount_cents=3900,
    )
    session = local_session(owner, [row])
    calls = []

    def transport(request):
        calls.append((request.method, request.url.path))
        if "checkout/sessions/" in request.url.path:
            status = initial_status if request.method == "GET" else "expired"
            return httpx.Response(
                200,
                json=checkout_payload(
                    owner,
                    request_id,
                    status=status,
                    customer="cus_incomplete",
                ),
            )
        assert request.url.path == "/v1/customers/cus_incomplete"
        return httpx.Response(
            200,
            json={
                "id": "cus_incomplete",
                "object": "customer",
                **({"deleted": True} if request.method == "DELETE" else {"livemode": False}),
            },
        )

    with httpx.Client(transport=httpx.MockTransport(transport)) as client:
        cleanup(session, owner, provider(client))
    assert calls[-2:] == [
        ("GET", "/v1/customers/cus_incomplete"),
        ("DELETE", "/v1/customers/cus_incomplete"),
    ]
    assert sum(method == "POST" for method, _ in calls) == (initial_status == "open")
    assert row.external_id == "cs_test_demo" and row.status == "pending"
    assert_read_only_owner(session, owner)
