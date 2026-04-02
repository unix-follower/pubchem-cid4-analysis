from __future__ import annotations

from pathlib import Path

from flask import Flask

from flask_cid4.routes import create_app as create_routes_app


def create_app(data_dir: Path) -> Flask:
    return create_routes_app(data_dir)
