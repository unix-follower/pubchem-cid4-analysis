from __future__ import annotations

import asyncio
import base64
import hashlib
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
MCP_AVAILABLE = importlib.util.find_spec("mcp") is not None


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

    def setUp(self) -> None:
        self.client.cookies.clear()

    def _login_basic(self, username: str = "analyst", password: str = "cid4-basic-password") -> dict[str, str]:
        encoded = base64.b64encode(f"{username}:{password}".encode()).decode("ascii")
        response = self.client.get(
            "/api/auth/session",
            headers={
                "Authorization": f"Basic {encoded}",
                "X-CID4-Auth-Method": "basic",
            },
        )
        self.assertEqual(response.status_code, 200)
        return {"X-CSRF-Token": response.json()["csrf_token"]}

    def _login_digest(self, username: str = "digestor", password: str = "cid4-digest-password") -> dict[str, str]:
        challenge = self.client.get("/api/auth/session", headers={"X-CID4-Auth-Method": "digest"})
        self.assertEqual(challenge.status_code, 401)
        digest_header = self._build_digest_header(
            challenge.headers["WWW-Authenticate"],
            username,
            password,
            method="GET",
            uri="/api/auth/session",
        )
        response = self.client.get(
            "/api/auth/session",
            headers={
                "Authorization": digest_header,
                "X-CID4-Auth-Method": "digest",
            },
        )
        self.assertEqual(response.status_code, 200)
        return {"X-CSRF-Token": response.json()["csrf_token"]}

    def _build_digest_header(
        self,
        challenge_value: str,
        username: str,
        password: str,
        method: str,
        uri: str,
    ) -> str:
        fields = {}
        for chunk in challenge_value.removeprefix("Digest ").split(","):
            key, _, value = chunk.strip().partition("=")
            fields[key] = value.strip().strip('"')
        nonce = fields["nonce"]
        realm = fields["realm"]
        opaque = fields["opaque"]
        qop = fields["qop"]
        nc = "00000001"
        cnonce = "cid4-test-cnonce"
        ha1 = hashlib.md5(f"{username}:{realm}:{password}".encode(), usedforsecurity=False).hexdigest()
        ha2 = hashlib.md5(f"{method}:{uri}".encode(), usedforsecurity=False).hexdigest()
        response_hash = hashlib.md5(
            f"{ha1}:{nonce}:{nc}:{cnonce}:{qop}:{ha2}".encode(),
            usedforsecurity=False,
        ).hexdigest()
        return (
            "Digest "
            f'username="{username}", '
            f'realm="{realm}", '
            f'nonce="{nonce}", '
            f'uri="{uri}", '
            f'response="{response_hash}", '
            f'qop="{qop}", '
            f'nc="{nc}", '
            f'cnonce="{cnonce}", '
            f'opaque="{opaque}"'
        )

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
        self.assertEqual(response.headers["X-Frame-Options"], "DENY")
        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")

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

    def test_llm_status_reports_when_torch_is_unavailable(self) -> None:
        from ml.torch_language_model import PyTorchLanguageModelService

        self._login_basic()

        with mock.patch.object(
            PyTorchLanguageModelService,
            "_torch_availability",
            return_value={"available": False, "reason": "PyTorch missing for test"},
        ):
            response = self.client.get("/api/llm/status", headers={"X-Request-Id": "request-llm-status"})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["framework"], "pytorch")
        self.assertFalse(payload["torch_available"])
        self.assertEqual(payload["torch_reason"], "PyTorch missing for test")
        self.assertEqual(response.headers["X-Request-Id"], "request-llm-status")
        self.assertIn("X-Trace-Id", response.headers)

    def test_llm_status_reports_when_tensorflow_is_unavailable(self) -> None:
        from ml.tensorflow_language_model import TensorFlowLanguageModelService

        self._login_basic()

        with mock.patch.object(
            TensorFlowLanguageModelService,
            "_tensorflow_availability",
            return_value={"available": False, "reason": "TensorFlow missing for test"},
        ):
            response = self.client.get("/api/llm/status?framework=tensorflow")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["framework"], "tensorflow")
        self.assertFalse(payload["tensorflow_available"])
        self.assertEqual(payload["tensorflow_reason"], "TensorFlow missing for test")

    def test_llm_train_returns_dependency_error_when_torch_is_unavailable(self) -> None:
        from ml.torch_language_model import PyTorchLanguageModelService

        csrf_headers = self._login_basic()

        with mock.patch.object(
            PyTorchLanguageModelService,
            "_torch_availability",
            return_value={"available": False, "reason": "PyTorch missing for test"},
        ):
            response = self.client.post(
                "/api/llm/train",
                json={"domains": ["taxonomy"], "epochs": 1, "max_chars": 4096},
                headers=csrf_headers,
            )

        self.assertEqual(response.status_code, 503)
        payload = response.json()
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["error"]["code"], "torch_unavailable")
        self.assertIn("X-Request-Id", response.headers)
        self.assertIn("traceparent", response.headers)

    def test_llm_train_returns_dependency_error_when_tensorflow_is_unavailable(self) -> None:
        from ml.tensorflow_language_model import TensorFlowLanguageModelService

        csrf_headers = self._login_basic()

        with mock.patch.object(
            TensorFlowLanguageModelService,
            "_tensorflow_availability",
            return_value={"available": False, "reason": "TensorFlow missing for test"},
        ):
            response = self.client.post(
                "/api/llm/train",
                json={"framework": "tensorflow", "domains": ["taxonomy"], "epochs": 1, "max_chars": 4096},
                headers=csrf_headers,
            )

        self.assertEqual(response.status_code, 503)
        payload = response.json()
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["error"]["code"], "tensorflow_unavailable")

    def test_llm_generate_returns_dependency_error_when_torch_is_unavailable(self) -> None:
        from ml.torch_language_model import PyTorchLanguageModelService

        csrf_headers = self._login_basic()

        with mock.patch.object(
            PyTorchLanguageModelService,
            "_torch_availability",
            return_value={"available": False, "reason": "PyTorch missing for test"},
        ):
            response = self.client.post("/api/llm/generate", json={"prompt": "CID 4"}, headers=csrf_headers)

        self.assertEqual(response.status_code, 503)
        payload = response.json()
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["error"]["code"], "torch_unavailable")
        self.assertIn("X-Request-Id", response.headers)

    def test_llm_generate_returns_dependency_error_when_tensorflow_is_unavailable(self) -> None:
        from ml.tensorflow_language_model import TensorFlowLanguageModelService

        csrf_headers = self._login_basic()

        with mock.patch.object(
            TensorFlowLanguageModelService,
            "_tensorflow_availability",
            return_value={"available": False, "reason": "TensorFlow missing for test"},
        ):
            response = self.client.post(
                "/api/llm/generate",
                json={"framework": "tensorflow", "prompt": "CID 4"},
                headers=csrf_headers,
            )

        self.assertEqual(response.status_code, 503)
        payload = response.json()
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["error"]["code"], "tensorflow_unavailable")

    def test_llm_generate_validation_error_on_missing_prompt(self) -> None:
        csrf_headers = self._login_basic()
        response = self.client.post("/api/llm/generate", json={}, headers=csrf_headers)

        self.assertEqual(response.status_code, 422)
        self.assertIn("X-Request-Id", response.headers)

    def test_llm_generate_validation_error_on_invalid_framework(self) -> None:
        csrf_headers = self._login_basic()
        response = self.client.post(
            "/api/llm/generate",
            json={"framework": "jax", "prompt": "CID 4"},
            headers=csrf_headers,
        )

        self.assertEqual(response.status_code, 422)
        self.assertIn("X-Request-Id", response.headers)

    def test_llm_train_can_return_mocked_success_payload(self) -> None:
        from ml.torch_language_model import PyTorchLanguageModelService

        csrf_headers = self._login_basic()

        with mock.patch.object(
            PyTorchLanguageModelService,
            "train",
            return_value={
                "status": "ok",
                "framework": "pytorch",
                "model_name": "mocked-model",
                "model_type": "gru-char-language-model",
                "torch_available": True,
                "corpus": {"document_count": 1, "character_count": 32},
                "training": {
                    "epochs": 1,
                    "sequence_length": 32,
                    "batch_size": 2,
                    "final_loss": 1.0,
                    "min_loss": 1.0,
                    "perplexity_estimate": 2.7,
                },
                "artifacts": {"checkpoint": "checkpoint.pt", "metadata": "metadata.json"},
            },
        ):
            response = self.client.post(
                "/api/llm/train",
                json={"domains": ["literature"], "epochs": 1, "max_chars": 4096},
                headers=csrf_headers,
            )

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["model_name"], "mocked-model")
        self.assertEqual(payload["framework"], "pytorch")
        self.assertEqual(payload["model_type"], "gru-char-language-model")

    def test_llm_train_can_return_mocked_tensorflow_success_payload(self) -> None:
        from ml.tensorflow_language_model import TensorFlowLanguageModelService

        csrf_headers = self._login_basic()

        with mock.patch.object(
            TensorFlowLanguageModelService,
            "train",
            return_value={
                "status": "ok",
                "framework": "tensorflow",
                "model_name": "mocked-tf-model",
                "model_type": "gru-keras-language-model",
                "tensorflow_available": True,
                "corpus": {"document_count": 1, "character_count": 32},
                "training": {
                    "epochs": 1,
                    "sequence_length": 32,
                    "batch_size": 2,
                    "final_loss": 1.0,
                    "min_loss": 1.0,
                    "perplexity_estimate": 2.7,
                },
                "artifacts": {"checkpoint": "checkpoint.keras", "metadata": "metadata.json"},
            },
        ):
            response = self.client.post(
                "/api/llm/train",
                json={"framework": "tensorflow", "domains": ["literature"], "epochs": 1, "max_chars": 4096},
                headers=csrf_headers,
            )

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["framework"], "tensorflow")
        self.assertEqual(payload["model_name"], "mocked-tf-model")
        self.assertEqual(payload["model_type"], "gru-keras-language-model")

    @unittest.skipUnless(MCP_AVAILABLE, "mcp extra not installed")
    def test_mcp_requires_authentication(self) -> None:
        response = self.client.post(
            "/mcp/",
            json={
                "jsonrpc": "2.0",
                "id": "init-1",
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "cid4-test", "version": "1.0.0"},
                },
            },
            headers={
                "Accept": "application/json, text/event-stream",
                "MCP-Protocol-Version": "2025-06-18",
            },
        )

        self.assertEqual(response.status_code, 401)
        payload = response.json()
        self.assertEqual(payload["error"]["code"], "mcp_auth_required")

    @unittest.skipUnless(MCP_AVAILABLE, "mcp extra not installed")
    def test_mcp_lists_tools_and_reads_resources_with_authenticated_session(self) -> None:
        async def exercise_mcp() -> None:
            from httpx import ASGITransport, AsyncClient
            from mcp import ClientSession
            from mcp.client.streamable_http import streamable_http_client

            from fastapi_cid4.app import create_app

            app = create_app(self.data_dir, self.observability)
            session_manager = app.state.cid4_mcp_server.session_manager.run()
            await session_manager.__aenter__()
            transport = ASGITransport(app=app)
            try:
                async with AsyncClient(transport=transport, base_url="http://testserver") as http_client:
                    encoded = base64.b64encode(b"analyst:cid4-basic-password").decode("ascii")
                    login = await http_client.get(
                        "/api/auth/session",
                        headers={
                            "Authorization": f"Basic {encoded}",
                            "X-CID4-Auth-Method": "basic",
                        },
                    )
                    self.assertEqual(login.status_code, 200)

                    async with (
                        streamable_http_client("http://testserver/mcp/", http_client=http_client) as (
                            read_stream,
                            write_stream,
                            _,
                        ),
                        ClientSession(read_stream, write_stream) as session,
                    ):
                        await session.initialize()

                        tools = await session.list_tools()
                        tool_names = {tool.name for tool in tools.tools}
                        self.assertIn("get_compound_metadata", tool_names)
                        self.assertIn("retrieve_documents", tool_names)

                        tool_result = await session.call_tool("get_compound_metadata", {})
                        self.assertFalse(tool_result.isError)
                        self.assertEqual(tool_result.structuredContent["compound"]["cid"], 4)

                        resources = await session.list_resources()
                        resource_uris = {str(resource.uri) for resource in resources.resources}
                        self.assertIn("cid4://compound/4", resource_uris)

                        resource_result = await session.read_resource("cid4://compound/4")
                        self.assertTrue(resource_result.contents)
            finally:
                await session_manager.__aexit__(None, None, None)

        asyncio.run(exercise_mcp())

    def test_llm_generate_stream_sends_sse_events(self) -> None:
        from ml.language_model_common import build_stream_event
        from ml.torch_language_model import PyTorchLanguageModelService

        csrf_headers = self._login_basic()

        with (
            mock.patch.object(
                PyTorchLanguageModelService,
                "stream_generate",
                return_value=iter(
                    [
                        build_stream_event("start", framework="pytorch", model_name="demo", prompt="CID 4"),
                        build_stream_event(
                            "token", framework="pytorch", model_name="demo", text="A", generated_text="CID 4A"
                        ),
                        build_stream_event(
                            "complete",
                            framework="pytorch",
                            model_name="demo",
                            generated_text="CID 4A",
                            generated_suffix="A",
                        ),
                    ]
                ),
            ),
            self.client.stream(
                "POST",
                "/api/llm/generate/stream",
                json={"framework": "pytorch", "prompt": "CID 4", "model_name": "demo"},
                headers=csrf_headers,
            ) as response,
        ):
            body = b"".join(response.iter_bytes())

        self.assertEqual(response.status_code, 200)
        decoded = body.decode("utf-8")
        self.assertIn("event: start", decoded)
        self.assertIn('"text": "A"', decoded)
        self.assertIn("event: complete", decoded)

    def test_llm_generate_stream_returns_error_event_for_unavailable_framework(self) -> None:
        from ml.tensorflow_language_model import TensorFlowLanguageModelService

        csrf_headers = self._login_basic()

        with (
            mock.patch.object(
                TensorFlowLanguageModelService,
                "_tensorflow_availability",
                return_value={"available": False, "reason": "TensorFlow missing for stream test"},
            ),
            self.client.stream(
                "POST",
                "/api/llm/generate/stream",
                json={"framework": "tensorflow", "prompt": "CID 4", "model_name": "demo"},
                headers=csrf_headers,
            ) as response,
        ):
            body = b"".join(response.iter_bytes())

        self.assertEqual(response.status_code, 200)
        decoded = body.decode("utf-8")
        self.assertIn("event: error", decoded)
        self.assertIn("tensorflow_unavailable", decoded)

    def test_llm_generate_websocket_sends_stream_events(self) -> None:
        from ml.language_model_common import build_stream_event
        from ml.torch_language_model import PyTorchLanguageModelService

        self._login_basic()

        with (
            mock.patch.object(
                PyTorchLanguageModelService,
                "stream_generate",
                return_value=iter(
                    [
                        build_stream_event("start", framework="pytorch", model_name="demo", prompt="CID 4"),
                        build_stream_event(
                            "token", framework="pytorch", model_name="demo", text="A", generated_text="CID 4A"
                        ),
                        build_stream_event(
                            "complete",
                            framework="pytorch",
                            model_name="demo",
                            generated_text="CID 4A",
                            generated_suffix="A",
                        ),
                    ]
                ),
            ),
            self.client.websocket_connect("/ws/llm/generate") as websocket,
        ):
            websocket.send_json({"framework": "pytorch", "prompt": "CID 4", "model_name": "demo"})
            start_event = websocket.receive_json()
            token_event = websocket.receive_json()
            complete_event = websocket.receive_json()

        self.assertEqual(start_event["event"], "start")
        self.assertEqual(token_event["event"], "token")
        self.assertEqual(token_event["text"], "A")
        self.assertEqual(complete_event["event"], "complete")

    def test_llm_generate_websocket_reports_service_error(self) -> None:
        from ml.language_model_common import LlmServiceError
        from ml.torch_language_model import PyTorchLanguageModelService

        self._login_basic()

        with (
            mock.patch.object(
                PyTorchLanguageModelService,
                "stream_generate",
                side_effect=LlmServiceError(503, "torch_unavailable", "PyTorch missing for websocket test"),
            ),
            self.client.websocket_connect("/ws/llm/generate") as websocket,
        ):
            websocket.send_json({"framework": "pytorch", "prompt": "CID 4", "model_name": "demo"})
            error_event = websocket.receive_json()

        self.assertEqual(error_event["event"], "error")
        self.assertEqual(error_event["error"]["code"], "torch_unavailable")

    def test_anonymous_llm_request_redirects_to_auth_page(self) -> None:
        response = self.client.post(
            "/api/llm/generate",
            json={"prompt": "CID 4"},
            follow_redirects=False,
        )

        self.assertEqual(response.status_code, 307)
        self.assertIn("/auth/basic?returnTo=%2Fapi%2Fllm%2Fgenerate", response.headers["location"])

    def test_basic_auth_session_login_sets_session_cookie(self) -> None:
        csrf_headers = self._login_basic()

        self.assertIn("X-CSRF-Token", csrf_headers)
        self.assertIn("cid4_session", self.client.cookies)
        self.assertIn("cid4_csrf", self.client.cookies)

    def test_digest_auth_session_login_sets_session_cookie(self) -> None:
        csrf_headers = self._login_digest()

        self.assertIn("X-CSRF-Token", csrf_headers)
        self.assertIn("cid4_session", self.client.cookies)

    def test_keycloak_config_exposes_placeholder_contract(self) -> None:
        response = self.client.get("/api/auth/oauth2/keycloak/config")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["provider"], "keycloak")
        self.assertFalse(payload["configured"])

    def test_csrf_is_required_for_protected_post_routes(self) -> None:
        self._login_basic()

        response = self.client.post("/api/llm/generate", json={"prompt": "CID 4"})

        self.assertEqual(response.status_code, 403)
        payload = response.json()
        self.assertEqual(payload["error"]["code"], "csrf_invalid")


if __name__ == "__main__":
    unittest.main()
