from __future__ import annotations

import base64
import importlib
import os
from typing import Any


def symmetric_dependencies_available() -> bool:
    return importlib.util.find_spec("cryptography") is not None


def build_symmetric_examples(payload: bytes) -> dict[str, Any]:
    if not symmetric_dependencies_available():
        return {
            "status": "skipped",
            "reason": "Install the optional crypto extra to enable AES-GCM and ChaCha20-Poly1305 examples.",
        }

    from cryptography.hazmat.primitives.ciphers.aead import AESGCM, ChaCha20Poly1305  # type: ignore[import-not-found]

    aes_key = AESGCM.generate_key(bit_length=256)
    aes_nonce = os.urandom(12)
    aesgcm = AESGCM(aes_key)
    aes_ciphertext = aesgcm.encrypt(aes_nonce, payload, b"cid4:aes-gcm")
    aes_plaintext = aesgcm.decrypt(aes_nonce, aes_ciphertext, b"cid4:aes-gcm")

    chacha_key = ChaCha20Poly1305.generate_key()
    chacha_nonce = os.urandom(12)
    chacha = ChaCha20Poly1305(chacha_key)
    chacha_ciphertext = chacha.encrypt(chacha_nonce, payload, b"cid4:chacha20-poly1305")
    chacha_plaintext = chacha.decrypt(
        chacha_nonce, chacha_ciphertext, b"cid4:chacha20-poly1305"
    )

    return {
        "status": "ok",
        "aes_256_gcm": {
            "key_b64": base64.b64encode(aes_key).decode("ascii"),
            "nonce_b64": base64.b64encode(aes_nonce).decode("ascii"),
            "ciphertext_b64": base64.b64encode(aes_ciphertext).decode("ascii"),
            "roundtrip_verified": aes_plaintext == payload,
        },
        "chacha20_poly1305": {
            "key_b64": base64.b64encode(chacha_key).decode("ascii"),
            "nonce_b64": base64.b64encode(chacha_nonce).decode("ascii"),
            "ciphertext_b64": base64.b64encode(chacha_ciphertext).decode("ascii"),
            "roundtrip_verified": chacha_plaintext == payload,
        },
    }
