from __future__ import annotations

from pathlib import Path

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Route

from cid4_api import ApiResponse, route_api_request


def create_app(data_dir: Path) -> Starlette:
    routes = [
        Route("/api/health", endpoint=health, methods=["GET", "OPTIONS"]),
        Route("/api/cid4/conformer/{index}", endpoint=conformer, methods=["GET", "OPTIONS"]),
        Route("/api/cid4/structure/2d", endpoint=structure_2d, methods=["GET", "OPTIONS"]),
        Route("/api/cid4/compound", endpoint=compound, methods=["GET", "OPTIONS"]),
        Route("/api/algorithms/pathway", endpoint=pathway, methods=["GET", "OPTIONS"]),
        Route("/api/algorithms/bioactivity", endpoint=bioactivity, methods=["GET", "OPTIONS"]),
        Route("/api/algorithms/taxonomy", endpoint=taxonomy, methods=["GET", "OPTIONS"]),
    ]
    middleware = [
        Middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_methods=["GET", "OPTIONS"],
            allow_headers=["Content-Type"],
        )
    ]
    app = Starlette(debug=False, routes=routes, middleware=middleware)
    app.state.data_dir = data_dir
    return app


def health(request: Request) -> Response:
    return _response_for(request)


def conformer(request: Request) -> Response:
    return _response_for(request)


def structure_2d(request: Request) -> Response:
    return _response_for(request)


def compound(request: Request) -> Response:
    return _response_for(request)


def pathway(request: Request) -> Response:
    return _response_for(request)


def bioactivity(request: Request) -> Response:
    return _response_for(request)


def taxonomy(request: Request) -> Response:
    return _response_for(request)


def _response_for(request: Request) -> Response:
    api_response = route_api_request(
        request.method,
        _target_from_request(request),
        request.app.state.data_dir,
        source="starlette",
        transport_name="Starlette",
    )
    return _to_starlette_response(api_response)


def _target_from_request(request: Request) -> str:
    query_string = request.url.query
    return request.url.path if not query_string else f"{request.url.path}?{query_string}"


def _to_starlette_response(api_response: ApiResponse) -> Response:
    return Response(
        content=api_response.body,
        media_type=api_response.content_type,
        status_code=api_response.status_code,
    )
