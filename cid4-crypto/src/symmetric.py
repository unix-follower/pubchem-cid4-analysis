from __future__ import annotations

import base64
import os
from typing import Any
from cryptography.hazmat.primitives.ciphers.aead import AESGCM, ChaCha20Poly1305
import constants


def encrypt_aes_256_gcm(input_file_path: str) -> dict[str, Any]:
    with open(input_file_path, "rb") as f:
        payload = f.read()

    aes_key = AESGCM.generate_key(bit_length=256)
    aes_nonce = os.urandom(12)
    aesgcm = AESGCM(aes_key)
    aes_ciphertext = aesgcm.encrypt(aes_nonce, payload, b"cid4:aes-gcm")
    # aes_plaintext = aesgcm.decrypt(aes_nonce, aes_ciphertext, b"cid4:aes-gcm")

    return {
        "key_b64": base64.b64encode(aes_key).decode(constants.ASCII),
        "nonce_b64": base64.b64encode(aes_nonce).decode(constants.ASCII),
        "ciphertext_b64": base64.b64encode(aes_ciphertext).decode(constants.ASCII),
        # verify: aes_plaintext == payload
    }


def encrypt_chacha20_poly1305(input_file_path: str) -> dict[str, Any]:
    with open(input_file_path, "rb") as f:
        payload = f.read()

    chacha_key = ChaCha20Poly1305.generate_key()
    chacha_nonce = os.urandom(12)
    chacha = ChaCha20Poly1305(chacha_key)
    chacha_ciphertext = chacha.encrypt(
        chacha_nonce, payload, b"cid4:chacha20-poly1305"
    )
    # chacha_plaintext = chacha.decrypt(
    #     chacha_nonce, chacha_ciphertext, b"crypto:chacha20-poly1305"
    # )

    return {
        "key_b64": base64.b64encode(chacha_key).decode(constants.ASCII),
        "nonce_b64": base64.b64encode(chacha_nonce).decode(constants.ASCII),
        "ciphertext_b64": base64.b64encode(chacha_ciphertext).decode(constants.ASCII),
        # verified: chacha_plaintext == payload,
    }
