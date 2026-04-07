from __future__ import annotations

import hashlib
import hmac
from pathlib import Path


def hash_bytes(payload: bytes) -> dict[str, str]:
    return {
        "sha256": hashlib.sha256(payload).hexdigest(),
        "sha512": hashlib.sha512(payload).hexdigest(),
        "blake2b": hashlib.blake2b(payload).hexdigest(),
        "md5": hashlib.md5(payload, usedforsecurity=False).hexdigest(),
    }


def hmac_sha256(key: bytes, payload: bytes) -> str:
    return hmac.new(key, payload, hashlib.sha256).hexdigest()


def build_file_manifest(paths: list[Path]) -> list[dict[str, str | int]]:
    manifest: list[dict[str, str | int]] = []
    for path in paths:
        payload = path.read_bytes()
        digests = hash_bytes(payload)
        manifest.append(
            {
                "name": path.name,
                "relative_path": str(path),
                "size_bytes": len(payload),
                **digests,
            }
        )
    return manifest
