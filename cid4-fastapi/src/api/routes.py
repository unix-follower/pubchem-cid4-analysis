from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

from cid4_observability import RequestScope, Runtime
from src.config.config import SecuritySettings, resolve_security_settings
from src.config.security import require_csrf
from src.api.v1 import (
    auth,
    conformer,
    llm,
    compound,
    pathway,
    bioactivity,
    taxonomy,
    structure,
    reaction_network,
)
from src.ml.tensorflow_language_model import TensorFlowLanguageModelService
from src.ml.torch_language_model import PyTorchLanguageModelService


def create_app(data_dir: Path, observability: Runtime | None = None) -> FastAPI:
    app = FastAPI(title="CID4 FastAPI", docs_url=None, redoc_url=None)
    app.state["data_dir"] = data_dir
    security_settings = resolve_security_settings()
    app.state["security_settings"] = security_settings
    app.state["pytorch_language_model_service"] = PyTorchLanguageModelService(data_dir)
    app.state["tensorflow_language_model_service"] = TensorFlowLanguageModelService(
        data_dir
    )

    app.add_middleware(
        TrustedHostMiddleware, allowed_hosts=list(security_settings.trusted_hosts)
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(security_settings.allowed_origins),
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=[
            "Accept",
            "Authorization",
            "Content-Type",
            "MCP-Protocol-Version",
            "Mcp-Session-Id",
            "X-CID4-Auth-Method",
            "X-Request-Id",
            security_settings.csrf_header_name,
        ],
        expose_headers=["Mcp-Session-Id"],
        allow_credentials=True,
    )

    _register_security(app, security_settings)
    _register_observability(app, observability)
    _register_mcp_routes(app, data_dir, security_settings)

    @app.get("/api/health", response_model=None)
    def health(_: Request) -> Response:
        return JSONResponse({"timestamp": datetime.now(UTC).isoformat()})

    app.include_router(auth.router)

    app.include_router(conformer.router)
    app.include_router(llm.router)
    app.include_router(compound.router)
    app.include_router(pathway.router)
    app.include_router(bioactivity.router)
    app.include_router(taxonomy.router)
    app.include_router(structure.router)
    app.include_router(reaction_network.router)

    return app


def _register_security(app: FastAPI, security_settings: SecuritySettings) -> None:
    @app.middleware("http")
    async def apply_security(request: Request, call_next):
        csrf_error = require_csrf(request, security_settings)
        if csrf_error is not None:
            response = csrf_error
        else:
            response = await call_next(request)
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; connect-src 'self' ws: wss:; "
            "img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; frame-ancestors 'none'; "
            "base-uri 'self'; form-action 'self'"
        )
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=()"
        )
        return response


def _register_observability(app: FastAPI, observability: Runtime | None) -> None:
    if observability is None:
        return

    @app.middleware("http")
    async def observe_requests(request: Request, call_next):
        scope = RequestScope(
            observability,
            request.method,
            request.url.path,
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


def _register_mcp_routes(
    app: FastAPI, data_dir: Path, security_settings: SecuritySettings
) -> None:
    from mcp_cid4.server import (
        create_authenticated_mcp_http_app,
        create_cid4_mcp_server,
    )

    mcp_server = create_cid4_mcp_server(data_dir)
    app.state.cid4_mcp_server = mcp_server
    app.mount("/mcp", create_authenticated_mcp_http_app(mcp_server, security_settings))

    @app.on_event("startup")
    async def startup_mcp_session_manager() -> None:
        session_manager = mcp_server.session_manager.run()
        app.state.cid4_mcp_session_manager = session_manager
        await session_manager.__aenter__()

    @app.on_event("shutdown")
    async def shutdown_mcp_session_manager() -> None:
        session_manager = getattr(app.state, "cid4_mcp_session_manager", None)
        if session_manager is not None:
            await session_manager.__aexit__(None, None, None)


def _target_from_request(request: Request) -> str:
    query_string = request.url.query
    return (
        request.url.path if not query_string else f"{request.url.path}?{query_string}"
    )


def _apply_observability_headers(response: Response, scope: RequestScope) -> None:
    for name, value in scope.response_headers.items():
        response.headers[name] = value
