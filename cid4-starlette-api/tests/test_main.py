from __future__ import annotations

from starlette.testclient import TestClient
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


from config import resolve_server_config # noqa: E402
from routes import create_app # noqa: E402


class StarletteServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:

        cls.data_dir = PROJECT_ROOT.parent / "data"
        cls.client = TestClient(create_app(cls.data_dir))

    def test_health_endpoint(self) -> None:
        response = self.client.get("/api/health")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["source"], "starlette")
        self.assertIn("healthy", payload["message"].lower())

    def test_health_error_mode(self) -> None:
        response = self.client.get("/api/health?mode=error")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["source"], "starlette")

    def test_conformer_route(self) -> None:
        response = self.client.get("/api/cid4/conformer/1")

        self.assertEqual(response.status_code, 200)
        self.assertIn("PC_Compounds", response.json())

    def test_unknown_conformer_returns_404(self) -> None:
        response = self.client.get("/api/cid4/conformer/99")

        self.assertEqual(response.status_code, 404)

    def test_compound_and_algorithm_routes(self) -> None:
        compound = self.client.get("/api/cid4/compound")
        structure_2d = self.client.get("/api/cid4/structure/2d")
        pathway = self.client.get("/api/algorithms/pathway")
        bioactivity = self.client.get("/api/algorithms/bioactivity")
        taxonomy = self.client.get("/api/algorithms/taxonomy")

        self.assertEqual(compound.status_code, 200)
        self.assertIn("Record", compound.json())
        self.assertEqual(structure_2d.status_code, 200)
        self.assertIn("PC_Compounds", structure_2d.json())
        self.assertEqual(pathway.status_code, 200)
        self.assertIn("graph", pathway.json())
        self.assertEqual(bioactivity.status_code, 200)
        self.assertIn("records", bioactivity.json())
        self.assertEqual(taxonomy.status_code, 200)
        self.assertIn("organisms", taxonomy.json())

    def test_server_config_falls_back_to_crypto_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)
            expected_secret = f"{data_dir.name}-tls-token"
            cert_path = data_dir / "cid4.demo.cert.pem"
            key_path = data_dir / "cid4.demo.key.pem"
            cert_path.write_text("demo-cert", encoding="utf-8")
            key_path.write_text("demo-key", encoding="utf-8")

            summary_path = data_dir / "out" / "crypto" / "cid4_crypto.summary.json"
            summary_path.parent.mkdir(parents=True, exist_ok=True)
            summary_path.write_text(
                json.dumps(
                    {
                        "demo_password": expected_secret,
                        "x509_and_pkcs12": {
                            "pem_paths": {
                                "certificate": str(cert_path),
                                "private_key": str(key_path),
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )

            with mock.patch.dict(os.environ, {}, clear=False):
                os.environ.pop("TLS_CERT_FILE", None)
                os.environ.pop("TLS_KEY_FILE", None)
                config = resolve_server_config(data_dir)

            self.assertEqual(config.cert_file, cert_path.resolve())
            self.assertEqual(config.key_file, key_path.resolve())
            self.assertEqual(config.key_password, expected_secret)


if __name__ == "__main__":
    unittest.main()
