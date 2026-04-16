from __future__ import annotations

import contextvars
import json
import os
from collections.abc import Iterable
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from fastapi.responses import JSONResponse
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import CallToolResult, TextContent
from pydantic import BaseModel, Field
from starlette.requests import Request
from starlette.types import ASGIApp, Receive, Scope, Send

from fastapi_cid4.config import SecuritySettings
from fastapi_cid4.security import (
    UserPrincipal,
    authenticate_login_request,
    authenticate_request,
)
from langchain_cid4.workflows import (
    retrieve_domain_hits,
    run_question_workflow,
)
from langchain_cid4.workflows import (
    route_question as route_question_workflow,
)
from langgraph_cid4.state import empty_supporting_ids, merge_supporting_ids
from langgraph_cid4.workflows import (
    collect_supporting_ids,
    finalize_state,
    flatten_hits,
    generic_validation_node,
    load_compound_context,
)

SUPPORTED_MCP_DOMAINS = ("literature", "patent", "assay", "pathway", "taxonomy", "product_use")
CURRENT_PRINCIPAL: contextvars.ContextVar[UserPrincipal | None] = contextvars.ContextVar(
    "cid4_mcp_current_principal",
    default=None,
)


class CompoundMetadata(BaseModel):
    cid: int
    title: str
    record_type: str
    summary: str


class RouteDecision(BaseModel):
    domains: list[str]
    primary_domain: str
    reason: str


class RetrievedHit(BaseModel):
    source_id: str | None = None
    doc_type: str | None = None
    title: str | None = None
    score: float | None = None
    backend: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RetrievalPayload(BaseModel):
    domain: str
    doc_count: int
    chunk_count: int
    backend: str
    fallback_reason: str | None = None
    hits: list[RetrievedHit]


class AnswerPayload(BaseModel):
    workflow: str
    question: str
    route: RouteDecision
    answer: str
    structured_output: dict[str, Any]
    context_preview: str


class ValidationPayload(BaseModel):
    question: str
    answer: str
    domains: list[str]
    validation: dict[str, Any]
    validated_answer: str


def create_cid4_mcp_server(data_dir: Path) -> FastMCP:
    mcp = FastMCP(
        "CID4 Python MCP",
        instructions=(
            "Grounded CID4 analysis tools over the repository datasets. The server exposes compound metadata, "
            "question routing, document retrieval, answer synthesis, and validation helpers."
        ),
        stateless_http=True,
        json_response=True,
        streamable_http_path="/",
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
    )

    @mcp.resource("cid4://compound/4")
    def compound_resource() -> str:
        with _bound_data_dir(data_dir):
            return json.dumps(load_compound_context(), indent=2, sort_keys=True)

    @mcp.resource("cid4://capabilities")
    def capabilities_resource() -> str:
        payload = {
            "data_dir": str(data_dir),
            "domains": list(SUPPORTED_MCP_DOMAINS),
            "tools": [
                "get_compound_metadata",
                "route_question",
                "retrieve_documents",
                "answer_question",
                "validate_grounded_answer",
            ],
            "transport": "streamable-http or stdio",
            "security": "http transport requires existing CID4 auth; stdio is local-process only",
        }
        return json.dumps(payload, indent=2, sort_keys=True)

    @mcp.tool()
    def get_compound_metadata() -> CallToolResult:
        with _bound_data_dir(data_dir):
            compound = CompoundMetadata.model_validate(load_compound_context())
        principal = _principal_payload()
        payload = {"compound": compound.model_dump(), "principal": principal}
        summary = f"Loaded {compound.title} (CID {compound.cid}) for {principal['username']}."
        return _tool_result(summary, payload)

    @mcp.tool()
    def route_question(question: str) -> CallToolResult:
        route = RouteDecision.model_validate(route_question_impl(question))
        payload = route.model_dump()
        summary = f"Primary domain: {route.primary_domain}. Routed domains: {', '.join(route.domains)}."
        return _tool_result(summary, payload)

    @mcp.tool()
    def retrieve_documents(question: str, domain: str, top_k: int = 4) -> CallToolResult:
        normalized_domain = _validate_domain(domain)
        with _bound_data_dir(data_dir):
            payload = retrieve_domain_hits(question, normalized_domain, top_k=top_k)
        public_payload = RetrievalPayload.model_validate(
            {key: value for key, value in payload.items() if key != "_hits"}
        )
        summary = f"Retrieved {len(public_payload.hits)} {normalized_domain} passages via {public_payload.backend}."
        return _tool_result(summary, public_payload.model_dump())

    @mcp.tool()
    def answer_question(question: str, domains: list[str] | None = None, top_k: int = 4) -> CallToolResult:
        normalized_domains = _normalize_domains(domains)
        with _bound_data_dir(data_dir):
            workflow = run_question_workflow(
                question,
                domains=normalized_domains or None,
                workflow="mcp-grounded-answer",
                top_k=top_k,
            )
        route = RouteDecision.model_validate(workflow["route"])
        payload = AnswerPayload(
            workflow=str(workflow["workflow"]),
            question=str(workflow["question"]),
            route=route,
            answer=str(workflow["answer"]),
            structured_output=dict(workflow["structured_output"]),
            context_preview=str(workflow["context_preview"]),
        )
        summary = payload.answer
        return _tool_result(summary, payload.model_dump())

    @mcp.tool()
    def validate_grounded_answer(
        question: str,
        answer: str,
        domains: list[str] | None = None,
        top_k: int = 4,
    ) -> CallToolResult:
        normalized_domains = _normalize_domains(domains)
        effective_domains = normalized_domains or route_question_impl(question)["domains"]
        with _bound_data_dir(data_dir):
            state = {
                "question": question,
                "workflow": "mcp-validation",
                "trace": [],
                "draft_answer": answer,
                "retrieved_rows": [],
                "supporting_ids": empty_supporting_ids(),
            }

            for domain_name in effective_domains:
                result = retrieve_domain_hits(question, domain_name, top_k=top_k)
                state["retrieved_rows"].extend(flatten_hits(domain_name, list(result["hits"])))
                state["supporting_ids"] = merge_supporting_ids(
                    state["supporting_ids"],
                    collect_supporting_ids(list(result["hits"])),
                )

            state.update(generic_validation_node(state))
            finalized = finalize_state(state)
        payload = ValidationPayload(
            question=question,
            answer=answer,
            domains=effective_domains,
            validation=dict(finalized["validation"]),
            validated_answer=str(finalized["validated_answer"]),
        )
        passed = bool(payload.validation.get("passed"))
        summary = (
            "Validation passed." if passed else f"Validation flagged: {'; '.join(payload.validation.get('issues', []))}"
        )
        return _tool_result(summary, payload.model_dump(), is_error=not passed)

    return mcp


def create_authenticated_mcp_http_app(mcp: FastMCP, security_settings: SecuritySettings) -> ASGIApp:
    return AuthenticatedMcpHttpApp(mcp.streamable_http_app(), security_settings)


class AuthenticatedMcpHttpApp:
    def __init__(self, app: ASGIApp, security_settings: SecuritySettings) -> None:
        self.app = app
        self.security_settings = security_settings

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive=receive)
        origin = request.headers.get("origin")
        if origin and origin not in self.security_settings.allowed_origins:
            response = JSONResponse(
                status_code=403,
                content={
                    "status": "error",
                    "error": {
                        "code": "mcp_origin_rejected",
                        "message": "The request origin is not allowed for the MCP endpoint.",
                    },
                },
            )
            await response(scope, receive, send)
            return

        principal = authenticate_request(request, self.security_settings)
        if principal is None and (
            request.headers.get("authorization") is not None or request.headers.get("x-cid4-auth-method") is not None
        ):
            principal, challenge_response = authenticate_login_request(request, self.security_settings)
            if principal is None:
                assert challenge_response is not None
                await challenge_response(scope, receive, send)
                return

        if principal is None:
            response = JSONResponse(
                status_code=401,
                content={
                    "status": "error",
                    "error": {
                        "code": "mcp_auth_required",
                        "message": "Authenticate with the existing CID4 session or "
                        "Authorization header before using /mcp.",
                    },
                },
            )
            await response(scope, receive, send)
            return

        token = CURRENT_PRINCIPAL.set(principal)
        try:
            await self.app(scope, receive, send)
        finally:
            CURRENT_PRINCIPAL.reset(token)


def route_question_impl(question: str) -> dict[str, Any]:
    return route_question_workflow(question)


def _normalize_domains(domains: Iterable[str] | None) -> list[str]:
    if domains is None:
        return []
    normalized = []
    for domain in domains:
        checked = _validate_domain(domain)
        if checked not in normalized:
            normalized.append(checked)
    return normalized


def _validate_domain(domain: str) -> str:
    normalized = domain.strip().lower().replace("-", "_")
    if normalized not in SUPPORTED_MCP_DOMAINS:
        raise ValueError(f"Unsupported domain '{domain}'. Expected one of: {', '.join(SUPPORTED_MCP_DOMAINS)}.")
    return normalized


def _principal_payload() -> dict[str, str]:
    principal = CURRENT_PRINCIPAL.get()
    if principal is None:
        return {"username": "local-stdio", "auth_method": "stdio"}
    return {"username": principal.username, "auth_method": principal.auth_method}


def _tool_result(summary: str, payload: dict[str, Any], *, is_error: bool = False) -> CallToolResult:
    return CallToolResult(
        content=[TextContent(type="text", text=summary)],
        structuredContent=payload,
        isError=is_error,
    )


@contextmanager
def _bound_data_dir(data_dir: Path):
    previous = os.environ.get("DATA_DIR")
    os.environ["DATA_DIR"] = str(data_dir)
    load_compound_context.cache_clear()
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("DATA_DIR", None)
        else:
            os.environ["DATA_DIR"] = previous
        load_compound_context.cache_clear()
