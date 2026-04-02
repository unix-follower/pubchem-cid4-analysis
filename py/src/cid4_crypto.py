from __future__ import annotations

import json
import logging as log
import os
import secrets
from pathlib import Path
from typing import Any

import env_utils
import fs_utils
import log_settings
from cid4_analysis import resolve_data_path
from crypto_cid4.asymmetric import build_asymmetric_examples
from crypto_cid4.certificates import build_certificate_examples
from crypto_cid4.hashing import build_file_manifest, hmac_sha256
from crypto_cid4.passwords import build_password_hash_examples
from crypto_cid4.symmetric import build_symmetric_examples
from ml.common import to_builtin

PAYLOAD_CANDIDATES = [
    "COMPOUND_CID_4.json",
    "Structure2D_COMPOUND_CID_4.json",
    "Conformer3D_COMPOUND_CID_4(1).json",
    "pubchem_cid_4_bioactivity.csv",
    "pubchem_cid_4_literature.csv",
]


def resolve_output_directory() -> Path:
    data_dir = Path(env_utils.get_data_dir())
    output_directory = data_dir / "out" / "crypto"
    fs_utils.create_dir_if_doesnt_exist(str(output_directory))
    return output_directory


def write_json(path: Path, payload: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as file:
        json.dump(to_builtin(payload), file, indent=2)


def select_payload_files() -> list[Path]:
    selected: list[Path] = []
    for name in PAYLOAD_CANDIDATES:
        path = resolve_data_path(name)
        if path.exists():
            selected.append(path)
    return selected


def build_crypto_summary(output_directory: Path) -> dict[str, Any]:
    payload_paths = select_payload_files()
    manifest = build_file_manifest(payload_paths)
    manifest_bytes = json.dumps(manifest, indent=2, sort_keys=True).encode("utf-8")
    manifest_path = output_directory / "cid4_crypto.manifest.json"
    manifest_path.write_bytes(manifest_bytes)

    demo_password = os.environ.get("CID4_CRYPTO_DEMO_PASSWORD") or secrets.token_urlsafe(24)
    hmac_key = b"cid4-demo-hmac-key"
    hmac_value = hmac_sha256(hmac_key, manifest_bytes)
    password_hashes = build_password_hash_examples(demo_password)
    symmetric_examples = build_symmetric_examples(manifest_bytes)
    asymmetric_examples = build_asymmetric_examples(manifest_bytes)
    certificate_examples = build_certificate_examples(output_directory, demo_password)

    return {
        "status": "ok",
        "manifest": {
            "path": str(manifest_path),
            "file_count": len(manifest),
            "files": manifest,
            "hmac_sha256": hmac_value,
        },
        "password_hashing": password_hashes,
        "symmetric": symmetric_examples,
        "asymmetric": asymmetric_examples,
        "x509_and_pkcs12": certificate_examples,
        "demo_password": demo_password,
        "demo_password_source": "environment" if "CID4_CRYPTO_DEMO_PASSWORD" in os.environ else "generated",
        "cli_examples": {
            "checksums": [
                f"sha256sum {payload_paths[0].name}" if payload_paths else "sha256sum COMPOUND_CID_4.json",
                f"md5 {payload_paths[0].name}" if payload_paths else "md5 COMPOUND_CID_4.json",
            ],
            "openssl": [
                "openssl dgst -sha256 -sign cid4_crypto.demo.key.pem -out cid4_crypto.manifest.sig "
                "cid4_crypto.manifest.json",
                "openssl x509 -pubkey -noout -in cid4_crypto.demo.cert.pem > cid4_crypto.demo.pubkey.pem",
                "openssl dgst -sha256 -verify cid4_crypto.demo.pubkey.pem -signature cid4_crypto.manifest.sig "
                "cid4_crypto.manifest.json",
            ],
            "gpg": [
                "gpg --armor --detach-sign cid4_crypto.manifest.json",
                "gpg --encrypt --recipient demo@example.invalid cid4_crypto.manifest.json",
            ],
            "age": [
                "age-keygen -o cid4-demo.agekey",
                "age -r <recipient> -o cid4_crypto.manifest.json.age cid4_crypto.manifest.json",
            ],
            "keytool": certificate_examples.get("keytool_examples", []),
        },
        "notes": [
            "Prefer Argon2id, AES-GCM, ChaCha20-Poly1305, Ed25519, X25519, and SHA-256 for new designs.",
            "MD5 is included for compatibility-only demonstrations and should not be used for security decisions.",
            "If no demo password is supplied through CID4_CRYPTO_DEMO_PASSWORD, a one-time random password "
            "is generated for local artifacts.",
            "The demo password is recorded in this summary so the generated PKCS#12 bundle "
            "can be inspected with keytool or OpenSSL.",
            "PKCS#12 and keytool examples are included so Java and Scala components "
            "can consume the same certificate material.",
        ],
    }


def write_crypto_analysis() -> None:
    output_directory = resolve_output_directory()
    summary = build_crypto_summary(output_directory)
    output_path = output_directory / "cid4_crypto.summary.json"
    write_json(output_path, summary)
    log.info("Cryptography summary written to %s", output_path)


if __name__ == "__main__":
    log_settings.configure_logging()
    write_crypto_analysis()
