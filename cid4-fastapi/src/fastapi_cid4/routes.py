from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Literal

from fastapi import FastAPI, Query, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse, StreamingResponse
from pydantic import BaseModel, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from cid4_api import ApiResponse, normalized_route_label, route_api_request
from cid4_observability import RequestScope, Runtime
from fastapi_cid4.config import SecuritySettings, resolve_security_settings
from fastapi_cid4.security import (
    UserPrincipal,
    attach_session_cookies,
    authenticate_login_request,
    authenticate_request,
    authenticate_websocket,
    build_auth_redirect_response,
    build_digest_challenge,
    clear_session_cookies,
    keycloak_config_payload,
    require_csrf,
)
from ml.language_model_common import (
    DEFAULT_MODEL_NAME,
    SUPPORTED_LLM_DOMAINS,
    SUPPORTED_LLM_FRAMEWORKS,
    GenerationConfig,
    LlmServiceError,
    TrainingConfig,
    sanitize_model_name,
)
from ml.tensorflow_language_model import TensorFlowLanguageModelService
from ml.torch_language_model import PyTorchLanguageModelService


class TrainLanguageModelRequest(BaseModel):
    framework: Literal["pytorch", "tensorflow"] = Field(default="pytorch")
    domains: list[str] = Field(default_factory=lambda: list(SUPPORTED_LLM_DOMAINS))
    output_name: str = Field(
        default=DEFAULT_MODEL_NAME,
        min_length=1,
        max_length=80,
        pattern=r"^[A-Za-z0-9_-]+$",
    )
    epochs: int = Field(default=12, ge=1, le=200)
    sequence_length: int = Field(default=64, ge=8, le=256)
    batch_size: int = Field(default=32, ge=1, le=256)
    embedding_dim: int = Field(default=64, ge=8, le=256)
    hidden_size: int = Field(default=128, ge=16, le=512)
    num_layers: int = Field(default=1, ge=1, le=4)
    learning_rate: float = Field(default=0.003, gt=0.0, le=0.1)
    max_chars: int = Field(default=120000, ge=1024, le=500000)
    seed: int = Field(default=17, ge=0, le=2_147_483_647)


class GenerateLanguageModelRequest(BaseModel):
    framework: Literal["pytorch", "tensorflow"] = Field(default="pytorch")
    prompt: str = Field(min_length=1, max_length=4000)
    model_name: str = Field(
        default=DEFAULT_MODEL_NAME,
        min_length=1,
        max_length=80,
        pattern=r"^[A-Za-z0-9_-]+$",
    )
    max_new_tokens: int = Field(default=160, ge=1, le=1000)
    temperature: float = Field(default=0.8, ge=0.0, le=5.0)
    top_k: int = Field(default=8, ge=0, le=128)
    seed: int | None = Field(default=None, ge=0, le=2_147_483_647)


def create_app(data_dir: Path, observability: Runtime | None = None) -> FastAPI:
    app = FastAPI(title="CID4 FastAPI", docs_url=None, redoc_url=None)
    security_settings = resolve_security_settings()
    pytorch_language_model_service = PyTorchLanguageModelService(data_dir)
    tensorflow_language_model_service = TensorFlowLanguageModelService(data_dir)
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
    _register_static_routes(app, data_dir)
    _register_auth_routes(app, security_settings)
    _register_llm_routes(
        app,
        security_settings,
        pytorch_language_model_service,
        tensorflow_language_model_service,
    )

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


def _register_static_routes(app: FastAPI, data_dir: Path) -> None:
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

    @app.api_route("/api/algorithms/reaction-network", methods=["GET", "OPTIONS"])
    def reaction_network(request: Request) -> Response:
        return _response_for(request, data_dir)


def _register_auth_routes(app: FastAPI, security_settings: SecuritySettings) -> None:
    @app.get("/api/auth/methods")
    def auth_methods() -> JSONResponse:
        return _json_response(
            {
                "status": "ok",
                "methods": ["basic", "digest", "oauth2"],
                "default_method": security_settings.default_auth_method,
            }
        )

    @app.get("/api/auth/oauth2/keycloak/config")
    def auth_keycloak_config() -> JSONResponse:
        return _json_response(keycloak_config_payload(security_settings))

    @app.get("/api/auth/me")
    def auth_me(request: Request) -> JSONResponse:
        principal = authenticate_request(request, security_settings)
        if principal is None:
            return _json_response(
                {"status": "ok", "authenticated": False}, status_code=401
            )
        return _session_payload_response(
            principal.username,
            principal.auth_method,
            request.cookies.get(security_settings.csrf_cookie_name),
        )

    @app.get("/api/auth/basic/login")
    def auth_basic_login(
        request: Request,
        return_to: Annotated[str, Query(alias="returnTo")] = "/chat/protocol",
    ) -> Response:
        return _complete_browser_login(request, security_settings, "basic", return_to)

    @app.get("/api/auth/digest/login")
    def auth_digest_login(
        request: Request,
        return_to: Annotated[str, Query(alias="returnTo")] = "/chat/protocol",
    ) -> Response:
        return _complete_browser_login(request, security_settings, "digest", return_to)

    @app.get("/api/auth/digest/challenge")
    def auth_digest_challenge() -> JSONResponse:
        response = _json_response(
            {
                "status": "error",
                "error": {
                    "code": "digest_auth_required",
                    "message": "Provide an HTTP Digest authorization header.",
                },
            },
            status_code=401,
        )
        response.headers["WWW-Authenticate"] = build_digest_challenge(security_settings)
        return response

    @app.get("/api/auth/session")
    def auth_session(request: Request) -> JSONResponse:
        existing_principal = authenticate_request(request, security_settings)
        if existing_principal is not None:
            return _session_payload_response(
                existing_principal.username,
                existing_principal.auth_method,
                request.cookies.get(security_settings.csrf_cookie_name),
            )

        principal, challenge_response = authenticate_login_request(
            request, security_settings
        )
        if principal is None:
            assert challenge_response is not None
            return challenge_response

        return _session_response(
            principal.username, principal.auth_method, security_settings
        )

    @app.post("/api/auth/logout")
    def auth_logout() -> JSONResponse:
        response = _json_response({"status": "ok", "authenticated": False})
        clear_session_cookies(response, security_settings)
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


def _register_llm_routes(
    app: FastAPI,
    security_settings: SecuritySettings,
    pytorch_language_model_service: PyTorchLanguageModelService,
    tensorflow_language_model_service: TensorFlowLanguageModelService,
) -> None:
    _register_llm_status_route(
        app,
        security_settings,
        pytorch_language_model_service,
        tensorflow_language_model_service,
    )
    _register_llm_train_route(
        app,
        security_settings,
        pytorch_language_model_service,
        tensorflow_language_model_service,
    )
    _register_llm_generate_route(
        app,
        security_settings,
        pytorch_language_model_service,
        tensorflow_language_model_service,
    )
    _register_llm_stream_route(
        app,
        security_settings,
        pytorch_language_model_service,
        tensorflow_language_model_service,
    )
    _register_llm_websocket_route(
        app,
        security_settings,
        pytorch_language_model_service,
        tensorflow_language_model_service,
    )


def _register_llm_status_route(
    app: FastAPI,
    security_settings: SecuritySettings,
    pytorch_language_model_service: PyTorchLanguageModelService,
    tensorflow_language_model_service: TensorFlowLanguageModelService,
) -> None:
    @app.get("/api/llm/status")
    def llm_status(
        request: Request,
        model_name: Annotated[
            str, Query(min_length=1, max_length=80)
        ] = DEFAULT_MODEL_NAME,
        framework: Annotated[Literal["pytorch", "tensorflow"], Query()] = "pytorch",
    ) -> Response:
        redirect_response = _require_authenticated_request(request, security_settings)
        if redirect_response is not None:
            return redirect_response
        language_model_service = _language_model_service(
            framework,
            pytorch_language_model_service,
            tensorflow_language_model_service,
        )
        return _execute_llm_action(lambda: language_model_service.status(model_name))


def _register_llm_train_route(
    app: FastAPI,
    security_settings: SecuritySettings,
    pytorch_language_model_service: PyTorchLanguageModelService,
    tensorflow_language_model_service: TensorFlowLanguageModelService,
) -> None:
    @app.post("/api/llm/train")
    def llm_train(
        request: Request, request_payload: TrainLanguageModelRequest
    ) -> Response:
        redirect_response = _require_authenticated_request(request, security_settings)
        if redirect_response is not None:
            return redirect_response
        language_model_service = _language_model_service(
            request_payload.framework,
            pytorch_language_model_service,
            tensorflow_language_model_service,
        )
        return _execute_llm_action(
            lambda: language_model_service.train(
                _training_config_from_request(request_payload)
            ),
            status_code=201,
        )


def _register_llm_generate_route(
    app: FastAPI,
    security_settings: SecuritySettings,
    pytorch_language_model_service: PyTorchLanguageModelService,
    tensorflow_language_model_service: TensorFlowLanguageModelService,
) -> None:
    @app.post("/api/llm/generate")
    def llm_generate(
        request: Request, request_payload: GenerateLanguageModelRequest
    ) -> Response:
        redirect_response = _require_authenticated_request(request, security_settings)
        if redirect_response is not None:
            return redirect_response
        language_model_service = _language_model_service(
            request_payload.framework,
            pytorch_language_model_service,
            tensorflow_language_model_service,
        )
        return _execute_llm_action(
            lambda: language_model_service.generate(
                _generation_config_from_request(request_payload)
            )
        )


def _register_llm_stream_route(
    app: FastAPI,
    security_settings: SecuritySettings,
    pytorch_language_model_service: PyTorchLanguageModelService,
    tensorflow_language_model_service: TensorFlowLanguageModelService,
) -> None:
    @app.post("/api/llm/generate/stream")
    async def llm_generate_stream(
        request: Request,
        request_payload: GenerateLanguageModelRequest,
    ) -> Response:
        redirect_response = _require_authenticated_request(request, security_settings)
        if redirect_response is not None:
            return redirect_response
        language_model_service = _language_model_service(
            request_payload.framework,
            pytorch_language_model_service,
            tensorflow_language_model_service,
        )
        config = _generation_config_from_request(request_payload)
        return StreamingResponse(
            _sse_event_stream(language_model_service, config),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )


def _register_llm_websocket_route(
    app: FastAPI,
    security_settings: SecuritySettings,
    pytorch_language_model_service: PyTorchLanguageModelService,
    tensorflow_language_model_service: TensorFlowLanguageModelService,
) -> None:
    @app.websocket("/ws/llm/generate")
    async def llm_generate_websocket(websocket: WebSocket) -> None:
        principal = authenticate_websocket(websocket, security_settings)
        if principal is None:
            await websocket.close(code=4401)
            return
        await websocket.accept()
        try:
            payload = GenerateLanguageModelRequest.model_validate(
                await websocket.receive_json()
            )
            language_model_service = _language_model_service(
                payload.framework,
                pytorch_language_model_service,
                tensorflow_language_model_service,
            )
            config = _generation_config_from_request(payload)
            for event in language_model_service.stream_generate(config):
                await websocket.send_json(event.to_dict())
            await websocket.close(code=1000)
        except LlmServiceError as exc:
            await websocket.send_json(
                {
                    "event": "error",
                    "framework": "unknown",
                    "user": principal.username,
                    "error": {"code": exc.code, "message": exc.message},
                }
            )
            await websocket.close(code=1011)
        except WebSocketDisconnect:
            return
        except Exception:
            await websocket.send_json(
                {
                    "event": "error",
                    "framework": "unknown",
                    "user": principal.username,
                    "error": {
                        "code": "websocket_error",
                        "message": "Unexpected WebSocket generation failure.",
                    },
                }
            )
            await websocket.close(code=1011)


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
    return (
        request.url.path if not query_string else f"{request.url.path}?{query_string}"
    )


def _to_fastapi_response(api_response: ApiResponse) -> Response:
    return Response(
        content=api_response.body,
        media_type=api_response.content_type,
        status_code=api_response.status_code,
    )


def _json_response(payload: dict[str, object], status_code: int = 200) -> JSONResponse:
    return JSONResponse(content=payload, status_code=status_code)


def _session_response(
    username: str, auth_method: str, security_settings: SecuritySettings
) -> JSONResponse:
    principal = UserPrincipal(username=username, auth_method=auth_method)
    response = _session_payload_response(username, auth_method, "pending")
    csrf_token = attach_session_cookies(response, security_settings, principal)
    response.body = json.dumps(
        {
            "status": "ok",
            "authenticated": True,
            "user": {
                "username": username,
                "auth_method": auth_method,
            },
            "csrf_token": csrf_token,
        }
    ).encode("utf-8")
    return response


def _session_payload_response(
    username: str, auth_method: str, csrf_token: str | None
) -> JSONResponse:
    return _json_response(
        {
            "status": "ok",
            "authenticated": True,
            "user": {
                "username": username,
                "auth_method": auth_method,
            },
            "csrf_token": csrf_token,
        }
    )


def _complete_browser_login(
    request: Request,
    security_settings: SecuritySettings,
    auth_method: Literal["basic", "digest"],
    return_to: str,
) -> Response:
    principal, challenge_response = authenticate_login_request(
        request, security_settings
    )
    if principal is None:
        assert challenge_response is not None
        return challenge_response
    response = build_auth_redirect_response(request, security_settings, auth_method)
    response.headers["Location"] = return_to
    attach_session_cookies(response, security_settings, principal)
    return response


def _require_authenticated_request(
    request: Request,
    security_settings: SecuritySettings,
) -> RedirectResponse | None:
    if authenticate_request(request, security_settings) is None:
        return build_auth_redirect_response(request, security_settings)
    return None


def _training_config_from_request(
    request_payload: TrainLanguageModelRequest,
) -> TrainingConfig:
    return TrainingConfig(
        framework=request_payload.framework,
        domains=tuple(request_payload.domains),
        output_name=sanitize_model_name(request_payload.output_name),
        epochs=request_payload.epochs,
        sequence_length=request_payload.sequence_length,
        batch_size=request_payload.batch_size,
        embedding_dim=request_payload.embedding_dim,
        hidden_size=request_payload.hidden_size,
        num_layers=request_payload.num_layers,
        learning_rate=request_payload.learning_rate,
        max_chars=request_payload.max_chars,
        seed=request_payload.seed,
    )


def _generation_config_from_request(
    request_payload: GenerateLanguageModelRequest,
) -> GenerationConfig:
    return GenerationConfig(
        framework=request_payload.framework,
        prompt=request_payload.prompt,
        model_name=sanitize_model_name(request_payload.model_name),
        max_new_tokens=request_payload.max_new_tokens,
        temperature=request_payload.temperature,
        top_k=request_payload.top_k,
        seed=request_payload.seed,
    )


def _execute_llm_action(action, status_code: int = 200) -> JSONResponse:
    try:
        payload = action()
    except LlmServiceError as exc:
        return _json_response(exc.to_payload(), exc.status_code)
    return _json_response(payload, status_code=status_code)


def _language_model_service(
    framework: str,
    pytorch_service: PyTorchLanguageModelService,
    tensorflow_service: TensorFlowLanguageModelService,
) -> PyTorchLanguageModelService | TensorFlowLanguageModelService:
    if framework == "pytorch":
        return pytorch_service
    if framework == "tensorflow":
        return tensorflow_service
    raise LlmServiceError(
        400,
        "unsupported_framework",
        f"Unsupported LLM framework '{framework}'. Supported frameworks: {', '.join(SUPPORTED_LLM_FRAMEWORKS)}",
    )


async def _sse_event_stream(
    language_model_service: PyTorchLanguageModelService
    | TensorFlowLanguageModelService,
    config: GenerationConfig,
):
    try:
        for event in language_model_service.stream_generate(config):
            yield _format_sse_event(event.to_dict())
    except LlmServiceError as exc:
        yield _format_sse_event(
            {
                "event": "error",
                "framework": config.framework,
                "error": {"code": exc.code, "message": exc.message},
            }
        )


def _format_sse_event(payload: dict[str, object]) -> bytes:
    event_name = str(payload.get("event", "message"))
    body = json.dumps(payload)
    return f"event: {event_name}\ndata: {body}\n\n".encode()


def _apply_observability_headers(response: Response, scope: RequestScope) -> None:
    for name, value in scope.response_headers.items():
        response.headers[name] = value
