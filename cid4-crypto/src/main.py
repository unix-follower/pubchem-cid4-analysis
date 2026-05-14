from __future__ import annotations

import argparse
import json
import logging as log
import os
from typing import Any
import numpy as np
import pandas as pd

import fs_utils
import log_settings
from asymmetric import (
    encrypt_ecdsa_p256,
    encrypt_ed25519,
    encrypt_rsa,
    encrypt_x25519_hybrid,
)
from certificates import make_certificate
from hashing import hash_file, hmac_sha256
from passwords import (
    make_argon2_hash,
    make_bcrypt_hash,
    make_scrypt_hash,
    make_pbkdf2_hmac_sha256_hash,
)
from symmetric import encrypt_aes_256_gcm, encrypt_chacha20_poly1305


def to_builtin(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): to_builtin(item) for key, item in value.items()}
    if isinstance(value, list):
        return [to_builtin(item) for item in value]
    if isinstance(value, tuple):
        return [to_builtin(item) for item in value]
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, pd.Series):
        return value.to_list()
    return value


def make_cert(password: str) -> None:
    output_directory = fs_utils.resolve_output_directory()
    payload = {"x509_and_pkcs12": make_certificate(output_directory, password)}
    output_path = output_directory / "cid4_crypto.summary.json"
    with output_path.open("w", encoding="utf-8") as file:
        json.dump(to_builtin(payload), file, indent=2)


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Cryptography")
    parser.add_argument("--alg", help="Specify the cryptography algorithm to use.")
    parser.add_argument("--in-file", help="Specify the input file for encryption.")
    return parser


def main() -> None:
    log_settings.configure_logging()
    parser = build_argument_parser()
    args = parser.parse_args()
    if args.alg:
        password = os.environ.get("CRYPTO_PASSWORD")
        ops_map = {
            "argon2": lambda: make_argon2_hash(password),
            "bcrypt": lambda: make_bcrypt_hash(password),
            "scrypt": lambda: make_scrypt_hash(password),
            "pbkdf2_hmac_sha256": lambda: make_pbkdf2_hmac_sha256_hash(password),
            "aes_256_gcm": lambda: encrypt_aes_256_gcm(args.in_file),
            "chacha20_poly1305": lambda: encrypt_chacha20_poly1305(args.in_file),
            "x25519_hybrid": lambda: encrypt_x25519_hybrid(args.in_file),
            "ecdsa_p256": lambda: encrypt_ecdsa_p256(args.in_file),
            "ed25519": lambda: encrypt_ed25519(args.in_file),
            "rsa": lambda: encrypt_rsa(args.in_file),
            "hash_file": lambda: hash_file(args.in_file),
            "hmac_sha256": lambda: hmac_sha256(bytes(password, "utf-8"), args.in_file),
            "x509": lambda: make_cert(password),
        }
        result = ops_map[args.alg]()
        log.info("Result='%s'", result)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
