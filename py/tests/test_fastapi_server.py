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

from cid4_observability import (  # noqa: E402
    ObservabilityConfig,
    RequestScope,
    initialize,
    resolve_observability_config,
    shutdown,
)

FASTAPI_AVAILABLE = importlib.util.find_spec("fastapi") is not None
HTTPX_AVAILABLE = importlib.util.find_spec("httpx") is not None


class FastApiObservabilityConfigTests(unittest.TestCase):
    def test_resolve_observability_config_uses_fastapi_specific_values_first(self) -> None:
        config = resolve_observability_config(
            "FASTAPI",
            "pubchem-cid4-fastapi",
            environ={
                "FASTAPI_OBSERVABILITY_ENABLED": "false",
                "OBSERVABILITY_ENABLED": "true",
                "FASTAPI_LOG_LEVEL": "debug",
                "LOG_LEVEL": "error",
            },
        )

        self.assertFalse(config.enabled)
        self.assertEqual(config.log_level, "debug")
        self.assertEqual(config.service_name, "pubchem-cid4-fastapi")

    def test_resolve_observability_config_parses_metrics_and_service_name(self) -> None:
        config = resolve_observability_config(
            "FASTAPI",
            "pubchem-cid4-fastapi",
            environ={
                "OBSERVABILITY_METRICS_PORT": "9777",
                "OTEL_SERVICE_NAME": "cid4-fastapi-test",
                "OBSERVABILITY_TRACING_ENABLED": "false",
            },
        )

        self.assertEqual(config.metrics_port, 9777)
        self.assertEqual(config.service_name, "cid4-fastapi-test")
        self.assertFalse(config.tracing_enabled)

    def test_request_scope_preserves_incoming_request_id(self) -> None:
        runtime = initialize(
            ObservabilityConfig(
                enabled=False,
                logging_enabled=False,
                metrics_enabled=False,
                tracing_enabled=False,
                service_name="cid4-fastapi-test",
            )
        )

        scope = RequestScope(
            runtime,
            "GET",
            "/api/health",
            "/api/health",
            incoming_request_id="request-123",
        )

        self.assertEqual(scope.response_headers["X-Request-Id"], "request-123")
        self.assertEqual(scope.response_headers["traceparent"], f"00-{scope.trace_id}-{scope.span_id}-01")
        scope.finish(200)
        shutdown(runtime)


@unittest.skipUnless(FASTAPI_AVAILABLE and HTTPX_AVAILABLE, "fastapi extra not installed")
class FastApiServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from fastapi.testclient import TestClient

        from fastapi_cid4.app import create_app

        cls.data_dir = PROJECT_ROOT.parent / "data"
        cls.observability = initialize(
            ObservabilityConfig(
                enabled=False,
                logging_enabled=False,
                metrics_enabled=False,
                tracing_enabled=False,
                service_name="cid4-fastapi-test",
            )
        )
        cls.client = TestClient(create_app(cls.data_dir, cls.observability))

    @classmethod
    def tearDownClass(cls) -> None:
        shutdown(cls.observability)

    def test_health_endpoint(self) -> None:
        response = self.client.get("/api/health")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["source"], "fastapi")
        self.assertIn("healthy", payload["message"].lower())
        self.assertIn("X-Request-Id", response.headers)
        self.assertIn("X-Trace-Id", response.headers)
        self.assertIn("X-Span-Id", response.headers)
        self.assertIn("traceparent", response.headers)

    def test_health_error_mode(self) -> None:
        response = self.client.get("/api/health?mode=error")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["source"], "fastapi")
        self.assertIn("X-Request-Id", response.headers)

    def test_preserves_incoming_request_id(self) -> None:
        response = self.client.get("/api/health", headers={"X-Request-Id": "request-456"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["X-Request-Id"], "request-456")

    def test_conformer_route(self) -> None:
        response = self.client.get("/api/cid4/conformer/1")

        self.assertEqual(response.status_code, 200)
        self.assertIn("PC_Compounds", response.json())
        self.assertIn("X-Request-Id", response.headers)

    def test_unknown_conformer_returns_404(self) -> None:
        response = self.client.get("/api/cid4/conformer/99")

        self.assertEqual(response.status_code, 404)
        self.assertIn("X-Request-Id", response.headers)

    def test_compound_and_algorithm_routes(self) -> None:
        compound = self.client.get("/api/cid4/compound")
        pathway = self.client.get("/api/algorithms/pathway")
        bioactivity = self.client.get("/api/algorithms/bioactivity")
        taxonomy = self.client.get("/api/algorithms/taxonomy")

        self.assertEqual(compound.status_code, 200)
        self.assertIn("Record", compound.json())
        self.assertEqual(pathway.status_code, 200)
        self.assertIn("graph", pathway.json())
        self.assertEqual(bioactivity.status_code, 200)
        self.assertIn("records", bioactivity.json())
        self.assertEqual(taxonomy.status_code, 200)
        self.assertIn("organisms", taxonomy.json())

    def test_server_config_falls_back_to_crypto_summary(self) -> None:
        from fastapi_cid4.config import resolve_server_config

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
