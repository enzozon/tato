import base64
import hashlib
import hmac
import json
import os
from uuid import UUID

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def load_key(variable: str) -> bytes:
    key = base64.b64decode(os.environ[variable], validate=True)
    if len(key) != 32:
        raise ValueError("A chave deve conter exatamente 32 bytes em base64.")
    return key


def encrypt_text(value: str, key: bytes, user_id: UUID, purpose: str) -> bytes:
    if len(key) != 32:
        raise ValueError("AES-256 exige chave de 32 bytes.")
    nonce = os.urandom(12)
    context = f"{user_id}:{purpose}".encode()
    return nonce + AESGCM(key).encrypt(nonce, value.encode(), context)


def decrypt_text(value: bytes, key: bytes, user_id: UUID, purpose: str) -> str:
    if len(key) != 32:
        raise ValueError("AES-256 exige chave de 32 bytes.")
    context = f"{user_id}:{purpose}".encode()
    return AESGCM(key).decrypt(value[:12], value[12:], context).decode()


def dedup_key(key: bytes, user_id: UUID, account_id: UUID, source_identity: str) -> str:
    if len(key) != 32 or not source_identity.strip():
        raise ValueError("Deduplicação exige chave de 32 bytes e identidade de origem.")
    message = json.dumps([str(user_id), str(account_id), source_identity]).encode()
    return hmac.new(key, message, hashlib.sha256).hexdigest()
