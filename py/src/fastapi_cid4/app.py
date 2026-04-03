from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI

from cid4_observability import Runtime
from fastapi_cid4.routes import create_app as create_routes_app


def create_app(data_dir: Path, observability: Runtime | None = None) -> FastAPI:
    return create_routes_app(data_dir, observability)
