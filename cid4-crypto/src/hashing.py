from __future__ import annotations

import hashlib
import hmac


def hash_file(input_file_path: str) -> dict[str, str]:
    with open(input_file_path, "rb") as f:
        payload = f.read()

    return {
        "sha256": hashlib.sha256(payload).hexdigest(),
        "sha512": hashlib.sha512(payload).hexdigest(),
        "blake2b": hashlib.blake2b(payload).hexdigest(),
        "md5": hashlib.md5(payload, usedforsecurity=False).hexdigest(),
    }


def hmac_sha256(key: bytes, input_file_path: str) -> str:
    with open(input_file_path, "rb") as f:
        payload = f.read()
    return hmac.new(key, payload, hashlib.sha256).hexdigest()
