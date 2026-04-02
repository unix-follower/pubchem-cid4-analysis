from __future__ import annotations

import importlib.util
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

FLASK_AVAILABLE = importlib.util.find_spec("flask") is not None


@unittest.skipUnless(FLASK_AVAILABLE, "flask extra not installed")
class FlaskServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        create_app = __import__("flask_cid4.app", fromlist=["create_app"]).create_app

        cls.data_dir = PROJECT_ROOT.parent / "data"
        app = create_app(cls.data_dir)
        app.config["TESTING"] = True
        cls.client = app.test_client()

    def test_health_endpoint(self) -> None:
        response = self.client.get("/api/health")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIsNotNone(payload)
        self.assertEqual(payload["source"], "flask")
        self.assertIn("healthy", payload["message"].lower())

    def test_health_error_mode(self) -> None:
        response = self.client.get("/api/health?mode=error")

        self.assertEqual(response.status_code, 503)
        payload = response.get_json()
        self.assertIsNotNone(payload)
        self.assertEqual(payload["source"], "flask")

    def test_conformer_route(self) -> None:
        response = self.client.get("/api/cid4/conformer/1")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIsNotNone(payload)
        self.assertIn("PC_Compounds", payload)

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
        self.assertIn("Record", compound.get_json())
        self.assertEqual(structure_2d.status_code, 200)
        self.assertIn("PC_Compounds", structure_2d.get_json())
        self.assertEqual(pathway.status_code, 200)
        self.assertIn("graph", pathway.get_json())
        self.assertEqual(bioactivity.status_code, 200)
        self.assertIn("records", bioactivity.get_json())
        self.assertEqual(taxonomy.status_code, 200)
        self.assertIn("organisms", taxonomy.get_json())

    def test_server_config_falls_back_to_crypto_summary(self) -> None:
        resolve_server_config = __import__(
            "fastapi_cid4.config", fromlist=["resolve_server_config"]
        ).resolve_server_config

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
