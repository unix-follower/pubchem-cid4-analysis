from typing import Annotated, Literal

from fastapi import APIRouter, Query, Request, Response
from fastapi.responses import JSONResponse
from src.config.config import SecuritySettings
from src.config.security import (
    UserPrincipal,
    attach_session_cookies,
    authenticate_login_request,
    authenticate_request,
    build_auth_redirect_response,
    build_digest_challenge,
    clear_session_cookies,
    issue_csrf_token,
    issue_session_token,
    keycloak_config_payload,
)


router = APIRouter()


@router.get("/api/v1/auth/methods")
def auth_methods(request: Request) -> JSONResponse:
    security_settings: SecuritySettings = request.app.state["security_settings"]
    return JSONResponse(
        status_code=200,
        content={
            "methods": ["basic", "digest", "oauth2"],
            "default_method": security_settings.default_auth_method,
        },
    )


@router.get("/api/v1/auth/oauth2/keycloak/config")
def auth_keycloak_config(request: Request) -> JSONResponse:
    security_settings: SecuritySettings = request.app.state["security_settings"]
    return JSONResponse(
        status_code=200, content=keycloak_config_payload(security_settings)
    )


@router.get("/api/v1/auth/me")
def auth_me(request: Request) -> JSONResponse:
    security_settings: SecuritySettings = request.app.state["security_settings"]
    principal = authenticate_request(request, security_settings)
    if principal is None:
        return Response(status_code=401)
    return _session_payload_response(
        principal.username,
        principal.auth_method,
        request.cookies.get(security_settings.csrf_cookie_name),
    )


@router.get("/api/v1/auth/basic/login")
def auth_basic_login(
    request: Request,
    return_to: Annotated[str, Query(alias="returnTo")] = "/chat/protocol",
) -> Response:
    security_settings: SecuritySettings = request.app.state["security_settings"]
    return _complete_browser_login(request, security_settings, "basic", return_to)


@router.get("/api/v1/auth/digest/login")
def auth_digest_login(
    request: Request,
    return_to: Annotated[str, Query(alias="returnTo")] = "/chat/protocol",
) -> Response:
    security_settings: SecuritySettings = request.app.state["security_settings"]
    return _complete_browser_login(request, security_settings, "digest", return_to)


@router.get("/api/v1/auth/digest/challenge")
def auth_digest_challenge(request: Request) -> JSONResponse:
    response = JSONResponse(
        status_code=401,
        content={
            "error": {
                "code": "digest_auth_required",
                "message": "Provide an HTTP Digest authorization header.",
            },
        },
    )
    security_settings: SecuritySettings = request.app.state["security_settings"]
    response.headers["WWW-Authenticate"] = build_digest_challenge(security_settings)
    return response


@router.get("/api/v1/auth/session")
def auth_session(request: Request) -> JSONResponse:
    security_settings: SecuritySettings = request.app.state["security_settings"]
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


@router.post("/api/v1/auth/logout")
def auth_logout(request: Request) -> Response:
    security_settings: SecuritySettings = request.app.state["security_settings"]
    response = Response(status_code=200)
    clear_session_cookies(response, security_settings)
    return response


def _session_response(
    username: str, auth_method: str, security_settings: SecuritySettings
) -> JSONResponse:
    principal = UserPrincipal(username=username, auth_method=auth_method)
    session_token = issue_session_token(security_settings, principal)
    csrf_token = issue_csrf_token(security_settings)
    response = JSONResponse(
        status_code=200,
        content={
            "user": {
                "username": username,
                "auth_method": auth_method,
            },
            "csrf_token": csrf_token,
        },
    )
    response.set_cookie(
        security_settings.session_cookie_name,
        session_token,
        max_age=security_settings.session_ttl_seconds,
        httponly=True,
        samesite="lax",
        secure=False,
        path="/",
    )
    response.set_cookie(
        security_settings.csrf_cookie_name,
        csrf_token,
        max_age=security_settings.session_ttl_seconds,
        httponly=False,
        samesite="lax",
        secure=False,
        path="/",
    )
    return response


def _session_payload_response(
    username: str, auth_method: str, csrf_token: str | None
) -> JSONResponse:
    return JSONResponse(
        status_code=200,
        content={
            "user": {
                "username": username,
                "auth_method": auth_method,
            },
            "csrf_token": csrf_token,
        },
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
