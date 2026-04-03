from __future__ import annotations

from pathlib import Path

from flask import Flask, Response, g, request

from cid4_api import ApiResponse, normalized_route_label, route_api_request
from cid4_observability import RequestScope, Runtime


def create_app(data_dir: Path, observability: Runtime | None = None) -> Flask:
    app = Flask(__name__)
    app.config["DATA_DIR"] = data_dir

    if observability is not None:

        @app.before_request
        def start_observability_scope() -> None:
            g.cid4_request_scope = RequestScope(
                observability,
                request.method,
                normalized_route_label(request.path),
                _target_from_request(),
                request.headers.get("X-Request-Id"),
            )

        @app.teardown_request
        def finish_failed_request(error: BaseException | None) -> None:
            if error is None:
                return

            scope = _request_scope()
            if scope is not None:
                scope.finish(500)

    @app.after_request
    def finalize_response(response: Response) -> Response:
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"

        scope = _request_scope()
        if scope is not None:
            for name, value in scope.response_headers.items():
                response.headers[name] = value
            scope.finish(response.status_code)

        return response

    @app.route("/api/health", methods=["GET", "OPTIONS"])
    def health() -> Response:
        return _response_for(app)

    @app.route("/api/cid4/conformer/<index>", methods=["GET", "OPTIONS"])
    def conformer(index: str) -> Response:
        del index
        return _response_for(app)

    @app.route("/api/cid4/structure/2d", methods=["GET", "OPTIONS"])
    def structure_2d() -> Response:
        return _response_for(app)

    @app.route("/api/cid4/compound", methods=["GET", "OPTIONS"])
    def compound() -> Response:
        return _response_for(app)

    @app.route("/api/algorithms/pathway", methods=["GET", "OPTIONS"])
    def pathway() -> Response:
        return _response_for(app)

    @app.route("/api/algorithms/bioactivity", methods=["GET", "OPTIONS"])
    def bioactivity() -> Response:
        return _response_for(app)

    @app.route("/api/algorithms/taxonomy", methods=["GET", "OPTIONS"])
    def taxonomy() -> Response:
        return _response_for(app)

    return app


def _data_dir(app: Flask) -> Path:
    value = app.config["DATA_DIR"]
    return value if isinstance(value, Path) else Path(value)


def _response_for(app: Flask) -> Response:
    api_response = route_api_request(
        request.method,
        _target_from_request(),
        _data_dir(app),
        source="flask",
        transport_name="Flask",
    )
    return _to_flask_response(api_response)


def _target_from_request() -> str:
    query_string = request.query_string.decode("utf-8")
    return request.path if not query_string else f"{request.path}?{query_string}"


def _to_flask_response(api_response: ApiResponse) -> Response:
    return Response(api_response.body, mimetype=api_response.content_type, status=api_response.status_code)


def _request_scope() -> RequestScope | None:
    return getattr(g, "cid4_request_scope", None)
