"""Verificações sobre o corpo bruto; não processam pagamentos nem mudam planos."""

import base64
import hashlib
import hmac


def stripe_signature(body: bytes, header: str, secret: str, now: int) -> bool:
    if not 0 < len(body) <= 65536 or len(header) > 1024:
        return False
    if not secret.startswith("whsec_") or len(secret) < 32:
        return False
    parts = [item.strip().partition("=") for item in header.split(",")]
    timestamps = [value for name, _, value in parts if name == "t"]
    if len(timestamps) != 1 or not timestamps[0].isascii() or not timestamps[0].isdigit():
        return False
    timestamp = timestamps[0]
    if len(timestamp) > 20 or abs(now - int(timestamp)) > 300:
        return False
    expected = hmac.new(
        secret.encode(), timestamp.encode() + b"." + body, hashlib.sha256
    ).hexdigest()
    signatures = [value for name, _, value in parts if name == "v1"]
    return any(
        len(value) == 64 and value.isascii() and hmac.compare_digest(value, expected)
        for value in signatures
    )


def abacate_signature(
    body: bytes, header: str, supplied_secret: str, secret: str, public_key: str
) -> bool:
    # A chave HMAC publicada pelo provedor não autentica sozinha o remetente.
    if not 0 < len(body) <= 65536 or len(header) > 128 or not public_key:
        return False
    if len(secret) < 32 or len(supplied_secret) > 256:
        return False
    if not hmac.compare_digest(supplied_secret.encode(), secret.encode()):
        return False
    try:
        supplied = base64.b64decode(header, validate=True)
    except ValueError:
        return False
    expected = hmac.new(public_key.encode(), body, hashlib.sha256).digest()
    return hmac.compare_digest(supplied, expected)
