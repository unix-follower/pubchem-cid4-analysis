from __future__ import annotations

import argparse

import log_settings
from fastapi_cid4 import resolve_data_dir
from mcp_cid4.server import create_cid4_mcp_server


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the CID4 MCP server in local stdio mode."
    )
    return parser


def main() -> None:
    log_settings.configure_logging()
    build_argument_parser().parse_args()

    data_dir = resolve_data_dir()
    server = create_cid4_mcp_server(data_dir)
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
