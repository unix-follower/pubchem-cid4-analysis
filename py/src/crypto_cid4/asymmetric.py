from __future__ import annotations

import base64
import importlib
import os
from typing import Any


def asymmetric_dependencies_available() -> bool:
    return importlib.util.find_spec("cryptography") is not None


def build_asymmetric_examples(payload: bytes) -> dict[str, Any]:
    if not asymmetric_dependencies_available():
        return {
            "status": "skipped",
            "reason": "Install the optional crypto extra to enable RSA, EC, Ed25519, and X25519 examples.",
        }

    from cryptography.hazmat.primitives import hashes, serialization  # type: ignore[import-not-found]
    from cryptography.hazmat.primitives.asymmetric import (  # type: ignore[import-not-found]
        ec,
        ed25519,
        padding,
        rsa,
        x25519,
    )
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM  # type: ignore[import-not-found]
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF  # type: ignore[import-not-found]

    rsa_private_key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    rsa_public_key = rsa_private_key.public_key()
    rsa_signature = rsa_private_key.sign(
        payload,
        padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
        hashes.SHA256(),
    )
    rsa_public_key.verify(
        rsa_signature,
        payload,
        padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
        hashes.SHA256(),
    )

    aes_key_to_wrap = os.urandom(32)
    rsa_ciphertext = rsa_public_key.encrypt(
        aes_key_to_wrap,
        padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None),
    )
    wrapped_key = rsa_private_key.decrypt(
        rsa_ciphertext,
        padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None),
    )

    ec_private_key = ec.generate_private_key(ec.SECP256R1())
    ec_public_key = ec_private_key.public_key()
    ec_signature = ec_private_key.sign(payload, ec.ECDSA(hashes.SHA256()))
    ec_public_key.verify(ec_signature, payload, ec.ECDSA(hashes.SHA256()))

    ed_private_key = ed25519.Ed25519PrivateKey.generate()
    ed_public_key = ed_private_key.public_key()
    ed_signature = ed_private_key.sign(payload)
    ed_public_key.verify(ed_signature, payload)

    x25519_sender_private = x25519.X25519PrivateKey.generate()
    x25519_receiver_private = x25519.X25519PrivateKey.generate()
    sender_shared_secret = x25519_sender_private.exchange(x25519_receiver_private.public_key())
    receiver_shared_secret = x25519_receiver_private.exchange(x25519_sender_private.public_key())
    hkdf = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=b"cid4:x25519-demo")
    sender_key = hkdf.derive(sender_shared_secret)
    receiver_key = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=b"cid4:x25519-demo").derive(
        receiver_shared_secret
    )
    x25519_nonce = os.urandom(12)
    aesgcm = AESGCM(sender_key)
    x25519_ciphertext = aesgcm.encrypt(x25519_nonce, payload, b"cid4:x25519")
    x25519_plaintext = AESGCM(receiver_key).decrypt(x25519_nonce, x25519_ciphertext, b"cid4:x25519")

    rsa_public_pem = rsa_public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")
    ed_public_raw = base64.b64encode(
        ed_public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
    ).decode("ascii")

    return {
        "status": "ok",
        "rsa_pss": {
            "signature_b64": base64.b64encode(rsa_signature).decode("ascii"),
            "verified": True,
            "public_key_pem": rsa_public_pem,
        },
        "rsa_oaep": {
            "ciphertext_b64": base64.b64encode(rsa_ciphertext).decode("ascii"),
            "roundtrip_verified": wrapped_key == aes_key_to_wrap,
        },
        "ecdsa_p256": {
            "signature_b64": base64.b64encode(ec_signature).decode("ascii"),
            "verified": True,
        },
        "ed25519": {
            "public_key_b64": ed_public_raw,
            "signature_b64": base64.b64encode(ed_signature).decode("ascii"),
            "verified": True,
        },
        "x25519_hybrid": {
            "nonce_b64": base64.b64encode(x25519_nonce).decode("ascii"),
            "ciphertext_b64": base64.b64encode(x25519_ciphertext).decode("ascii"),
            "shared_secret_match": sender_shared_secret == receiver_shared_secret,
            "roundtrip_verified": x25519_plaintext == payload,
        },
    }
