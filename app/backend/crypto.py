import base64
import os
import hashlib

_SECRET = os.environ.get("SECRET_KEY", "yichian-mailer-default-secret-change-me")
_KEY = hashlib.sha256(_SECRET.encode()).digest()


def _xor(data: bytes, key: bytes) -> bytes:
    return bytes(b ^ key[i % len(key)] for i, b in enumerate(data))


def encrypt(plaintext: str) -> str:
    data = plaintext.encode()
    return base64.b64encode(_xor(data, _KEY)).decode()


def decrypt(ciphertext: str) -> str:
    data = base64.b64decode(ciphertext.encode())
    return _xor(data, _KEY).decode()
