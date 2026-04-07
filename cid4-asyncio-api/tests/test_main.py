from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from main import build_response_from_request_head, render_http_response  # noqa: E402


class AsyncIoServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.data_dir = PROJECT_ROOT.parent / "data"

    def test_build_response_from_request_head_routes_health(self) -> None:
        response = build_response_from_request_head(
            "GET /api/health HTTP/1.1", self.data_dir
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('"source": "asyncio"', response.body)

    def test_build_response_from_request_head_rejects_malformed_requests(self) -> None:
        response = build_response_from_request_head("GET /api/health", self.data_dir)

        self.assertEqual(response.status_code, 400)

    def test_render_http_response_sets_allow_header_for_method_errors(self) -> None:
        response = build_response_from_request_head(
            "POST /api/health HTTP/1.1", self.data_dir
        )
        payload = render_http_response(response)

        self.assertIn("HTTP/1.1 405 Method Not Allowed", payload)
        self.assertIn("Allow: GET, OPTIONS", payload)


if __name__ == "__main__":
    unittest.main()
