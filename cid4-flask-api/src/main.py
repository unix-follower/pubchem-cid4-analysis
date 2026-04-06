from __future__ import annotations

import argparse
import os
import ssl
from pathlib import Path

from flask import Flask

import log_settings
from config import resolve_data_dir, resolve_server_config
from observability import Runtime, initialize, resolve_observability_config, shutdown
from routes import create_app as create_routes_app


def create_app(data_dir: Path, observability: Runtime | None = None) -> Flask:
    return create_routes_app(data_dir, observability)


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the CID 4 Flask HTTPS server.")
    parser.add_argument("--host", help="Override the bind host.")
    parser.add_argument("--port", type=int, help="Override the bind port.")
    return parser


def main() -> None:
    log_settings.configure_logging()
    args = build_argument_parser().parse_args()

    data_dir = resolve_data_dir()
    server_config = resolve_server_config(data_dir)
    observability_config = resolve_observability_config("FLASK", "pubchem-cid4-flask")

    host = args.host or os.environ.get("FLASK_HOST") or server_config.host
    port = args.port or _parse_port_override(os.environ.get("FLASK_PORT")) or server_config.port
    observability = initialize(observability_config)
    app = create_app(data_dir, observability)
    ssl_context = _build_ssl_context(server_config)

    if observability is not None:
        observability.log_startup(host, port)

    try:
        app.run(host=host, port=port, ssl_context=ssl_context)
    except Exception as exc:
        if observability is not None:
            observability.log_startup_failure(str(exc))
        raise
    finally:
        shutdown(observability)


def _build_ssl_context(server_config) -> ssl.SSLContext:
    context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(
        certfile=str(server_config.cert_file),
        keyfile=str(server_config.key_file),
        password=server_config.key_password,
    )
    return context


def _parse_port_override(value: str | None) -> int | None:
    if not value:
        return None
    try:
        parsed = int(value)
    except ValueError:
        return None
    return parsed if parsed > 0 else None


if __name__ == "__main__":
    main()
