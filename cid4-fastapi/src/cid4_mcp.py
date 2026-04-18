from __future__ import annotations

import log_settings
from cid4_api import resolve_data_dir
from mcp_cid4.server import create_cid4_mcp_server


def main() -> None:
    log_settings.configure_logging()

    data_dir = resolve_data_dir()
    server = create_cid4_mcp_server(data_dir)
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
