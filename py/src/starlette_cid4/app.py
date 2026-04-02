from __future__ import annotations

from pathlib import Path

from starlette.applications import Starlette

from starlette_cid4.routes import create_app as create_routes_app


def create_app(data_dir: Path) -> Starlette:
    return create_routes_app(data_dir)
