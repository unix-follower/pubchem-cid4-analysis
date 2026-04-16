from __future__ import annotations

import argparse
import uvicorn
from pathlib import Path

from fastapi import FastAPI

from cid4_observability import Runtime
from fastapi_cid4.routes import create_app as create_routes_app

import log_settings
from cid4_observability import initialize, resolve_observability_config, shutdown
from fastapi_cid4.config import resolve_data_dir, resolve_server_config


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the CID 4 FastAPI HTTPS server.")
    parser.add_argument("--host", help="Override the bind host.")
    parser.add_argument("--port", type=int, help="Override the bind port.")
    return parser


def create_app(data_dir: Path, observability: Runtime | None = None) -> FastAPI:
    return create_routes_app(data_dir, observability)


def main() -> None:
    log_settings.configure_logging()
    args = build_argument_parser().parse_args()

    data_dir = resolve_data_dir()
    server_config = resolve_server_config(data_dir)
    observability_config = resolve_observability_config(
        "FASTAPI", "pubchem-cid4-fastapi"
    )

    host = args.host or server_config.host
    port = args.port or server_config.port
    observability = initialize(observability_config)
    app = create_app(data_dir, observability)

    if observability is not None:
        observability.log_startup(host, port)

    try:
        uvicorn.run(
            app,
            host=host,
            port=port,
            ssl_certfile=str(server_config.cert_file),
            ssl_keyfile=str(server_config.key_file),
            ssl_keyfile_password=server_config.key_password,
        )
    except Exception as exc:
        if observability is not None:
            observability.log_startup_failure(str(exc))
        raise
    finally:
        shutdown(observability)


if __name__ == "__main__":
    main()
