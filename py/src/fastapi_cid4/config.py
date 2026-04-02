from __future__ import annotations

from pathlib import Path

from cid4_api import ServerConfig
from cid4_api import resolve_data_dir as shared_resolve_data_dir
from cid4_api import resolve_server_config as shared_resolve_server_config

FastApiServerConfig = ServerConfig


def resolve_data_dir() -> Path:
    return shared_resolve_data_dir()


def resolve_server_config(data_dir: Path) -> FastApiServerConfig:
    return shared_resolve_server_config(
        data_dir,
        preferred_host_env_names=("FASTAPI_HOST",),
        preferred_port_env_names=("FASTAPI_PORT",),
    )
