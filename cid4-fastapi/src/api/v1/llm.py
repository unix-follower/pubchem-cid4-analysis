from typing import Annotated, Literal
import json
from fastapi import (
    APIRouter,
    Query,
    Request,
    Response,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import JSONResponse, RedirectResponse, StreamingResponse

from src.config.config import SecuritySettings
from src.config.security import (
    authenticate_request,
    authenticate_websocket,
    build_auth_redirect_response,
)

from src.ml.language_model_common import (
    DEFAULT_MODEL_NAME,
    SUPPORTED_LLM_FRAMEWORKS,
    GenerationConfig,
    LlmServiceError,
    TrainingConfig,
    sanitize_model_name,
)
from src.ml.tensorflow_language_model import TensorFlowLanguageModelService
from src.ml.torch_language_model import PyTorchLanguageModelService
from .models import TrainLanguageModelRequest, GenerateLanguageModelRequest


router = APIRouter()


@router.get("/api/v1/llm/status")
def llm_status(
    request: Request,
    model_name: Annotated[str, Query(min_length=1, max_length=80)] = DEFAULT_MODEL_NAME,
    framework: Annotated[Literal["pytorch", "tensorflow"], Query()] = "pytorch",
) -> Response:
    security_settings: SecuritySettings = request.app.state["security_settings"]
    pytorch_language_model_service: PyTorchLanguageModelService = request.app.state[
        "pytorch_language_model_service"
    ]
    tensorflow_language_model_service: TensorFlowLanguageModelService = (
        request.app.state["tensorflow_language_model_service"]
    )

    redirect_response = _require_authenticated_request(request, security_settings)
    if redirect_response is not None:
        return redirect_response

    language_model_service = _language_model_service(
        framework,
        pytorch_language_model_service,
        tensorflow_language_model_service,
    )
    return _execute_llm_action(lambda: language_model_service.status(model_name))


@router.post("/api/v1/llm/train")
def llm_train(request: Request, request_payload: TrainLanguageModelRequest) -> Response:
    security_settings: SecuritySettings = request.app.state["security_settings"]
    pytorch_language_model_service: PyTorchLanguageModelService = request.app.state[
        "pytorch_language_model_service"
    ]
    tensorflow_language_model_service: TensorFlowLanguageModelService = (
        request.app.state["tensorflow_language_model_service"]
    )

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


@router.post("/api/v1/llm/generate")
def llm_generate(
    request: Request, request_payload: GenerateLanguageModelRequest
) -> Response:
    security_settings: SecuritySettings = request.app.state["security_settings"]
    pytorch_language_model_service: PyTorchLanguageModelService = request.app.state[
        "pytorch_language_model_service"
    ]
    tensorflow_language_model_service: TensorFlowLanguageModelService = (
        request.app.state["tensorflow_language_model_service"]
    )

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


@router.post("/api/v1/llm/generate/stream")
async def llm_generate_stream(
    request: Request,
    request_payload: GenerateLanguageModelRequest,
) -> Response:
    security_settings: SecuritySettings = request.app.state["security_settings"]
    pytorch_language_model_service: PyTorchLanguageModelService = request.app.state[
        "pytorch_language_model_service"
    ]
    tensorflow_language_model_service: TensorFlowLanguageModelService = (
        request.app.state["tensorflow_language_model_service"]
    )

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


@router.websocket("/ws/llm/generate")
async def llm_generate_websocket(websocket: WebSocket) -> None:
    security_settings: SecuritySettings = websocket.app.state["security_settings"]
    pytorch_language_model_service: PyTorchLanguageModelService = websocket.app.state[
        "pytorch_language_model_service"
    ]
    tensorflow_language_model_service: TensorFlowLanguageModelService = (
        websocket.app.state["tensorflow_language_model_service"]
    )

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
        return JSONResponse(content=exc.to_payload(), status_code=exc.status_code)
    return JSONResponse(content=payload, status_code=status_code)


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
