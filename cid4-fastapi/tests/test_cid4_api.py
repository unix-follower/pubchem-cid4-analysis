from __future__ import annotations

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

from src.cid4_api import resolve_server_config  # noqa: E402


class Cid4ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.data_dir = PROJECT_ROOT.parent / "data"

    def test_asyncio_server_config_honors_asyncio_env_overrides(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)
            cert_path = data_dir / "cid4.demo.cert.pem"
            key_path = data_dir / "cid4.demo.key.pem"
            cert_path.write_text("demo-cert", encoding="utf-8")
            key_path.write_text("demo-key", encoding="utf-8")

            with mock.patch.dict(
                os.environ,
                {
                    "ASYNCIO_HOST": "127.0.0.1",
                    "ASYNCIO_PORT": "9559",
                    "SERVER_HOST": "0.0.0.0",
                    "SERVER_PORT": "8443",
                    "TLS_CERT_FILE": str(cert_path),
                    "TLS_KEY_FILE": str(key_path),
                },
                clear=False,
            ):
                config = resolve_server_config(
                    data_dir,
                    preferred_host_env_names=("ASYNCIO_HOST",),
                    preferred_port_env_names=("ASYNCIO_PORT",),
                )

            self.assertEqual(config.host, "127.0.0.1")
            self.assertEqual(config.port, 9559)
            self.assertEqual(config.cert_file, cert_path.resolve())
            self.assertEqual(config.key_file, key_path.resolve())


if __name__ == "__main__":
    unittest.main()
