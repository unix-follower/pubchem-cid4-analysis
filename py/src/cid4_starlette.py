from __future__ import annotations

import argparse

import log_settings
from fastapi_cid4.config import resolve_data_dir, resolve_server_config
from starlette_cid4 import create_app


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the CID 4 Starlette HTTPS server.")
    parser.add_argument("--host", help="Override the bind host.")
    parser.add_argument("--port", type=int, help="Override the bind port.")
    return parser


def main() -> None:
    try:
        import uvicorn
    except ModuleNotFoundError as exc:
        raise RuntimeError("Install the optional starlette extra to run the Starlette server.") from exc

    log_settings.configure_logging()
    args = build_argument_parser().parse_args()

    data_dir = resolve_data_dir()
    server_config = resolve_server_config(data_dir)

    host = args.host or server_config.host
    port = args.port or server_config.port
    app = create_app(data_dir)

    uvicorn.run(
        app,
        host=host,
        port=port,
        ssl_certfile=str(server_config.cert_file),
        ssl_keyfile=str(server_config.key_file),
        ssl_keyfile_password=server_config.key_password,
    )


if __name__ == "__main__":
    main()
