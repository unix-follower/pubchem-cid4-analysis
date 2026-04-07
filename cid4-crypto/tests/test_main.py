from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from hashing import build_file_manifest, hmac_sha256  # noqa: E402

CRYPTO_AVAILABLE = importlib.util.find_spec("cryptography") is not None
BCRYPT_AVAILABLE = importlib.util.find_spec("bcrypt") is not None
ARGON2_AVAILABLE = importlib.util.find_spec("argon2") is not None


class CryptoWorkflowTests(unittest.TestCase):
    def test_hash_manifest_includes_common_algorithms(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            sample_path = Path(temp_dir) / "sample.txt"
            sample_path.write_text("cid4 demo payload", encoding="utf-8")

            manifest = build_file_manifest([sample_path])

            self.assertEqual(len(manifest), 1)
            self.assertIn("sha256", manifest[0])
            self.assertIn("sha512", manifest[0])
            self.assertIn("blake2b", manifest[0])
            self.assertIn("md5", manifest[0])

    def test_hmac_sha256_is_stable(self) -> None:
        value = hmac_sha256(b"demo-key", b"demo-payload")
        self.assertEqual(len(value), 64)

    @unittest.skipUnless(CRYPTO_AVAILABLE, "cryptography extra not installed")
    def test_symmetric_roundtrip_examples(self) -> None:
        from symmetric import build_symmetric_examples  # noqa: E402

        result = build_symmetric_examples(b"cid4 symmetric payload")

        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["aes_256_gcm"]["roundtrip_verified"])
        self.assertTrue(result["chacha20_poly1305"]["roundtrip_verified"])

    @unittest.skipUnless(CRYPTO_AVAILABLE, "cryptography extra not installed")
    def test_asymmetric_examples_verify(self) -> None:
        from asymmetric import build_asymmetric_examples  # noqa: E402

        result = build_asymmetric_examples(b"cid4 asymmetric payload")

        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["rsa_pss"]["verified"])
        self.assertTrue(result["ecdsa_p256"]["verified"])
        self.assertTrue(result["ed25519"]["verified"])
        self.assertTrue(result["rsa_oaep"]["roundtrip_verified"])
        self.assertTrue(result["x25519_hybrid"]["roundtrip_verified"])

    @unittest.skipUnless(CRYPTO_AVAILABLE, "cryptography extra not installed")
    def test_certificate_and_pkcs12_examples(self) -> None:
        from certificates import build_certificate_examples  # noqa: E402

        with tempfile.TemporaryDirectory() as temp_dir:
            result = build_certificate_examples(Path(temp_dir), "changeit")

            self.assertEqual(result["status"], "ok")
            self.assertTrue(result["private_key_loaded"])
            self.assertTrue(Path(result["pem_paths"]["private_key"]).exists())
            self.assertTrue(Path(result["pkcs12"]["path"]).exists())

    @unittest.skipUnless(
        CRYPTO_AVAILABLE and BCRYPT_AVAILABLE and ARGON2_AVAILABLE,
        "crypto password extras not installed",
    )
    def test_password_hash_examples_verify(self) -> None:
        from passwords import build_password_hash_examples  # noqa: E402

        result = build_password_hash_examples("cid4-password")

        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["algorithms"]["argon2id"]["verified"])
        self.assertTrue(result["algorithms"]["bcrypt"]["verified"])
        self.assertTrue(result["algorithms"]["scrypt"]["verified"])
        self.assertTrue(result["algorithms"]["pbkdf2_hmac_sha256"]["verified"])


if __name__ == "__main__":
    unittest.main()
