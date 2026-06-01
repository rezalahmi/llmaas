# app/security/api_keys.py

import hashlib


def hash_api_key(api_key: str) -> str:
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def api_key_prefix(api_key: str, length: int = 12) -> str:
    return api_key[:length]
