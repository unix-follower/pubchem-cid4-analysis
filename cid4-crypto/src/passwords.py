from __future__ import annotations

import base64
import hashlib
import importlib
import os
from typing import Any


def password_dependencies_available() -> bool:
    return (
        importlib.util.find_spec("argon2") is not None
        and importlib.util.find_spec("bcrypt") is not None
    )


def build_password_hash_examples(password: str) -> dict[str, Any]:
    if not password_dependencies_available():
        return {
            "status": "skipped",
            "reason": "Install the optional crypto extra to enable Argon2id and bcrypt examples.",
        }

    import bcrypt  # type: ignore[import-not-found]
    from argon2 import PasswordHasher  # type: ignore[import-not-found]

    password_bytes = password.encode("utf-8")
    argon2_hasher = PasswordHasher()
    argon2_hash = argon2_hasher.hash(password)
    bcrypt_hash = bcrypt.hashpw(password_bytes, bcrypt.gensalt(rounds=12)).decode(
        "utf-8"
    )
    scrypt_salt = os.urandom(16)
    pbkdf2_salt = os.urandom(16)
    scrypt_hash = hashlib.scrypt(
        password_bytes, salt=scrypt_salt, n=2**14, r=8, p=1
    ).hex()
    pbkdf2_hash = hashlib.pbkdf2_hmac(
        "sha256", password_bytes, pbkdf2_salt, 600_000
    ).hex()

    return {
        "status": "ok",
        "algorithms": {
            "argon2id": {
                "hash": argon2_hash,
                "verified": bool(argon2_hasher.verify(argon2_hash, password)),
            },
            "bcrypt": {
                "hash": bcrypt_hash,
                "verified": bool(
                    bcrypt.checkpw(password_bytes, bcrypt_hash.encode("utf-8"))
                ),
            },
            "scrypt": {
                "salt_b64": base64.b64encode(scrypt_salt).decode("ascii"),
                "hash": scrypt_hash,
                "verified": hashlib.scrypt(
                    password_bytes, salt=scrypt_salt, n=2**14, r=8, p=1
                ).hex()
                == scrypt_hash,
            },
            "pbkdf2_hmac_sha256": {
                "salt_b64": base64.b64encode(pbkdf2_salt).decode("ascii"),
                "iterations": 600_000,
                "hash": pbkdf2_hash,
                "verified": hashlib.pbkdf2_hmac(
                    "sha256", password_bytes, pbkdf2_salt, 600_000
                ).hex()
                == pbkdf2_hash,
            },
        },
        "notes": [
            "Argon2id is the preferred default for new password hashing examples.",
            "bcrypt is included because it remains widely deployed, but it is password hashing rather than encryption.",
        ],
    }
