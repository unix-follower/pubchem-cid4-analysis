from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from cid4_api import ApiResponse, normalized_route_label, route_api_request
from cid4_observability import RequestScope, Runtime


def create_app(data_dir: Path, observability: Runtime | None = None) -> FastAPI:
    app = FastAPI(title="CID4 FastAPI", docs_url=None, redoc_url=None)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["GET", "OPTIONS"],
        allow_headers=["Content-Type"],
    )

    if observability is not None:

        @app.middleware("http")
        async def observe_requests(request: Request, call_next):
            scope = RequestScope(
                observability,
                request.method,
                normalized_route_label(request.url.path),
                _target_from_request(request),
                request.headers.get("X-Request-Id"),
            )
            request.state.cid4_request_scope = scope
            try:
                response = await call_next(request)
            except Exception:
                scope.finish(500)
                raise

            _apply_observability_headers(response, scope)
            scope.finish(response.status_code)
            return response

    @app.api_route("/api/health", methods=["GET", "OPTIONS"], response_model=None)
    def health(request: Request) -> Response:
        return _response_for(request, data_dir)

    @app.api_route("/api/cid4/conformer/{index}", methods=["GET", "OPTIONS"])
    def conformer(index: int | str, request: Request) -> Response:
        del index
        return _response_for(request, data_dir)

    @app.api_route("/api/cid4/structure/2d", methods=["GET", "OPTIONS"])
    def structure_2d(request: Request) -> Response:
        return _response_for(request, data_dir)

    @app.api_route("/api/cid4/compound", methods=["GET", "OPTIONS"])
    def compound(request: Request) -> Response:
        return _response_for(request, data_dir)

    @app.api_route("/api/algorithms/pathway", methods=["GET", "OPTIONS"])
    def pathway(request: Request) -> Response:
        return _response_for(request, data_dir)

    @app.api_route("/api/algorithms/bioactivity", methods=["GET", "OPTIONS"])
    def bioactivity(request: Request) -> Response:
        return _response_for(request, data_dir)

    @app.api_route("/api/algorithms/taxonomy", methods=["GET", "OPTIONS"])
    def taxonomy(request: Request) -> Response:
        return _response_for(request, data_dir)

    return app


def _response_for(request: Request, data_dir: Path) -> Response:
    api_response = route_api_request(
        request.method,
        _target_from_request(request),
        data_dir,
        source="fastapi",
        transport_name="FastAPI",
    )
    return _to_fastapi_response(api_response)


def _target_from_request(request: Request) -> str:
    query_string = request.url.query
    return request.url.path if not query_string else f"{request.url.path}?{query_string}"


def _to_fastapi_response(api_response: ApiResponse) -> Response:
    return Response(
        content=api_response.body,
        media_type=api_response.content_type,
        status_code=api_response.status_code,
    )


def _apply_observability_headers(response: Response, scope: RequestScope) -> None:
    for name, value in scope.response_headers.items():
        response.headers[name] = value
