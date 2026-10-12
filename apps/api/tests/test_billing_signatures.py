import base64
import hashlib
import hmac

import pytest

from app.billing_signatures import abacate_signature, stripe_signature

BODY = b'{"id":"synthetic-event","livemode":false}'
SECRET = "whsec_" + "s" * 32
NOW = 1791374400


def signed(timestamp=NOW):
    signature = hmac.new(
        SECRET.encode(), str(timestamp).encode() + b"." + BODY, hashlib.sha256
    ).hexdigest()
    return f"t={timestamp},v1={signature}"


def test_stripe_accepts_rotation_and_requires_exact_body():
    header = signed() + ",v1=" + "0" * 64
    assert stripe_signature(BODY, header, SECRET, NOW)
    assert not stripe_signature(BODY + b" ", header, SECRET, NOW)
    assert not stripe_signature(BODY, header, "whsec_" + "x" * 32, NOW)
    assert not stripe_signature(BODY, header, "", NOW)


@pytest.mark.parametrize("delta", [-301, 301, 3600])
def test_stripe_rejects_replay_or_future_signature(delta):
    assert not stripe_signature(BODY, signed(NOW + delta), SECRET, NOW)


@pytest.mark.parametrize(
    "header",
    [
        "",
        "v1=" + "0" * 64,
        "t=x,v1=abc",
        "t=1,t=2,v1=abc",
        "t=" + "1" * 21,
        "t=٣,v1=abc",
        "x" * 1025,
    ],
)
def test_stripe_rejects_malformed_headers(header):
    assert not stripe_signature(BODY, header, SECRET, NOW)


def test_webhooks_limit_body_size():
    assert not stripe_signature(BODY * 2000, signed(), SECRET, NOW)
    assert not abacate_signature(BODY * 2000, "", SECRET, SECRET, "public")


def test_abacate_requires_private_secret_in_addition_to_public_hmac():
    public = "synthetic-public-signing-key"
    header = base64.b64encode(hmac.new(public.encode(), BODY, hashlib.sha256).digest()).decode()
    assert abacate_signature(BODY, header, SECRET, SECRET, public)
    assert not abacate_signature(BODY, header, "forged", SECRET, public)
    assert not abacate_signature(BODY, header, "não autorizado", SECRET, public)
    assert not abacate_signature(BODY + b" ", header, SECRET, SECRET, public)
    assert not abacate_signature(BODY, header, "", "", public)
    assert not abacate_signature(BODY, "malformed!", SECRET, SECRET, public)
    assert not abacate_signature(BODY, header, SECRET, SECRET, "")
