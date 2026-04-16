from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass
from typing import Literal
from urllib.parse import urlencode

from fastapi import Request, WebSocket
from fastapi.responses import JSONResponse, RedirectResponse, Response

from fastapi_cid4.config import SecuritySettings

AuthMethod = Literal["basic", "digest", "oauth2"]


@dataclass(frozen=True)
class UserPrincipal:
    username: str
    auth_method: AuthMethod


@dataclass(frozen=True)
class SessionEnvelope:
    principal: UserPrincipal
    csrf_token: str


def resolve_auth_method(
    raw_value: str | None, settings: SecuritySettings
) -> AuthMethod:
    normalized = (raw_value or settings.default_auth_method).strip().lower()
    if normalized in {"basic", "digest", "oauth2"}:
        return normalized
    return settings.default_auth_method  # type: ignore[return-value]


def build_auth_redirect_response(
    request: Request,
    settings: SecuritySettings,
    auth_method: AuthMethod | None = None,
) -> RedirectResponse:
    method = auth_method or resolve_auth_method(
        request.headers.get("X-CID4-Auth-Method"), settings
    )
    return_to = (
        request.url.path
        if not request.url.query
        else f"{request.url.path}?{request.url.query}"
    )
    location = f"/auth/{method}?{urlencode({'returnTo': return_to})}"
    return RedirectResponse(url=location, status_code=307)


def attach_session_cookies(
    response: Response,
    settings: SecuritySettings,
    principal: UserPrincipal,
) -> str:
    session_token = issue_session_token(settings, principal)
    csrf_token = issue_csrf_token(settings)
    response.set_cookie(
        settings.session_cookie_name,
        session_token,
        max_age=settings.session_ttl_seconds,
        httponly=True,
        samesite="lax",
        secure=False,
        path="/",
    )
    response.set_cookie(
        settings.csrf_cookie_name,
        csrf_token,
        max_age=settings.session_ttl_seconds,
        httponly=False,
        samesite="lax",
        secure=False,
        path="/",
    )
    return csrf_token


def clear_session_cookies(response: Response, settings: SecuritySettings) -> None:
    response.delete_cookie(settings.session_cookie_name, path="/")
    response.delete_cookie(settings.csrf_cookie_name, path="/")


def issue_session_token(settings: SecuritySettings, principal: UserPrincipal) -> str:
    payload = {
        "username": principal.username,
        "auth_method": principal.auth_method,
        "issued_at": int(time.time()),
        "expires_at": int(time.time()) + settings.session_ttl_seconds,
    }
    return _encode_signed_payload(payload, settings.session_secret)


def validate_session_token(
    settings: SecuritySettings, token: str | None
) -> UserPrincipal | None:
    payload = _decode_signed_payload(token, settings.session_secret)
    if payload is None:
        return None
    expires_at = int(payload.get("expires_at", 0))
    if expires_at < int(time.time()):
        return None
    username = payload.get("username")
    auth_method = payload.get("auth_method")
    if not isinstance(username, str) or auth_method not in {
        "basic",
        "digest",
        "oauth2",
    }:
        return None
    return UserPrincipal(username=username, auth_method=auth_method)


def issue_csrf_token(settings: SecuritySettings) -> str:
    payload = {
        "nonce": secrets.token_urlsafe(18),
        "issued_at": int(time.time()),
        "expires_at": int(time.time()) + settings.session_ttl_seconds,
    }
    return _encode_signed_payload(payload, settings.csrf_secret)


def validate_csrf_token(
    settings: SecuritySettings, cookie_token: str | None, header_token: str | None
) -> bool:
    if not cookie_token or not header_token or cookie_token != header_token:
        return False
    payload = _decode_signed_payload(cookie_token, settings.csrf_secret)
    if payload is None:
        return False
    return int(payload.get("expires_at", 0)) >= int(time.time())


def authenticate_request(
    request: Request, settings: SecuritySettings
) -> UserPrincipal | None:
    principal = validate_session_token(
        settings, request.cookies.get(settings.session_cookie_name)
    )
    if principal is not None:
        return principal
    return None


def authenticate_websocket(
    websocket: WebSocket, settings: SecuritySettings
) -> UserPrincipal | None:
    cookie_header = websocket.headers.get("cookie")
    if not cookie_header:
        return None
    cookies = _parse_cookie_header(cookie_header)
    return validate_session_token(settings, cookies.get(settings.session_cookie_name))


def require_csrf(request: Request, settings: SecuritySettings) -> JSONResponse | None:
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return None
    if not request.url.path.startswith("/api/"):
        return None
    if settings.session_cookie_name not in request.cookies:
        return None
    cookie_token = request.cookies.get(settings.csrf_cookie_name)
    header_token = request.headers.get(settings.csrf_header_name)
    if validate_csrf_token(settings, cookie_token, header_token):
        return None
    return JSONResponse(
        status_code=403,
        content={
            "status": "error",
            "error": {
                "code": "csrf_invalid",
                "message": "A valid CSRF token is required for this request.",
            },
        },
    )


def authenticate_login_request(
    request: Request, settings: SecuritySettings
) -> tuple[UserPrincipal | None, Response | None]:
    method = resolve_auth_method(request.headers.get("X-CID4-Auth-Method"), settings)
    if method == "basic":
        principal = _authenticate_basic(request.headers.get("Authorization"), settings)
        if principal is not None:
            return principal, None
        response = JSONResponse(
            status_code=401,
            content={
                "status": "error",
                "error": {
                    "code": "basic_auth_required",
                    "message": "HTTP Basic credentials are required.",
                },
            },
        )
        response.headers["WWW-Authenticate"] = f'Basic realm="{settings.digest_realm}"'
        return None, response
    if method == "digest":
        principal = _authenticate_digest(
            request.method,
            request.url.path,
            request.headers.get("Authorization"),
            settings,
        )
        if principal is not None:
            return principal, None
        response = JSONResponse(
            status_code=401,
            content={
                "status": "error",
                "error": {
                    "code": "digest_auth_required",
                    "message": "HTTP Digest credentials are required.",
                },
            },
        )
        response.headers["WWW-Authenticate"] = build_digest_challenge(settings)
        return None, response
    principal = _authenticate_oauth2(request.headers.get("Authorization"), settings)
    if principal is not None:
        return principal, None
    return None, JSONResponse(
        status_code=401,
        content={
            "status": "error",
            "error": {
                "code": "oauth2_token_required",
                "message": "A bearer token issued by Keycloak is required.",
            },
        },
    )


def build_digest_challenge(settings: SecuritySettings) -> str:
    nonce = issue_digest_nonce(settings)
    return (
        "Digest "
        f'realm="{settings.digest_realm}", '
        f'qop="auth", '
        f'nonce="{nonce}", '
        f'opaque="{settings.digest_opaque}", '
        'algorithm="MD5"'
    )


def issue_digest_nonce(settings: SecuritySettings) -> str:
    issued_at = str(int(time.time()))
    signature = _hex_hmac(
        settings.digest_secret,
        f"{issued_at}:{settings.digest_realm}:{settings.digest_opaque}",
    )
    raw = f"{issued_at}:{signature}".encode()
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def keycloak_config_payload(settings: SecuritySettings) -> dict[str, object]:
    auth_url = None
    if settings.keycloak_base_url and settings.keycloak_realm:
        auth_url = f"{settings.keycloak_base_url.rstrip('/')}/realms/{settings.keycloak_realm}/protocol/openid-connect/auth"
    return {
        "status": "ok",
        "provider": "keycloak",
        "configured": bool(
            settings.keycloak_base_url
            and settings.keycloak_realm
            and settings.keycloak_client_id
        ),
        "issuer": (
            f"{settings.keycloak_base_url.rstrip('/')}/realms/{settings.keycloak_realm}"
            if settings.keycloak_base_url and settings.keycloak_realm
            else None
        ),
        "realm": settings.keycloak_realm,
        "client_id": settings.keycloak_client_id,
        "redirect_uri": settings.keycloak_redirect_uri,
        "authorization_endpoint": auth_url,
    }


def _authenticate_basic(
    authorization_header: str | None, settings: SecuritySettings
) -> UserPrincipal | None:
    if not authorization_header or not authorization_header.startswith("Basic "):
        return None
    try:
        raw_credentials = base64.b64decode(
            authorization_header.split(" ", 1)[1]
        ).decode("utf-8")
    except ValueError:
        return None
    username, separator, password = raw_credentials.partition(":")
    if separator != ":":
        return None
    if settings.basic_users.get(username) != password:
        return None
    return UserPrincipal(username=username, auth_method="basic")


def _authenticate_digest(
    method: str,
    uri: str,
    authorization_header: str | None,
    settings: SecuritySettings,
) -> UserPrincipal | None:
    if not authorization_header or not authorization_header.startswith("Digest "):
        return None
    values = _parse_digest_authorization(authorization_header.removeprefix("Digest "))
    username = values.get("username")
    nonce = values.get("nonce")
    digest_uri = values.get("uri")
    client_response = values.get("response")
    qop = values.get("qop")
    nc = values.get("nc")
    cnonce = values.get("cnonce")
    if not all(
        isinstance(item, str) and item
        for item in (username, nonce, digest_uri, client_response, qop, nc, cnonce)
    ):
        return None
    if digest_uri != uri or qop != "auth" or not validate_digest_nonce(settings, nonce):
        return None
    password = settings.digest_users.get(username)
    if password is None:
        return None
    ha1 = hashlib.md5(
        f"{username}:{settings.digest_realm}:{password}".encode(), usedforsecurity=False
    ).hexdigest()
    ha2 = hashlib.md5(
        f"{method}:{digest_uri}".encode(), usedforsecurity=False
    ).hexdigest()
    expected = hashlib.md5(
        f"{ha1}:{nonce}:{nc}:{cnonce}:{qop}:{ha2}".encode(), usedforsecurity=False
    ).hexdigest()
    if not hmac.compare_digest(expected, client_response):
        return None
    return UserPrincipal(username=username, auth_method="digest")


def _authenticate_oauth2(
    authorization_header: str | None, settings: SecuritySettings
) -> UserPrincipal | None:
    if not authorization_header or not authorization_header.startswith("Bearer "):
        return None
    token = authorization_header.removeprefix("Bearer ").strip()
    username = settings.oauth2_tokens.get(token)
    if username is None:
        return None
    return UserPrincipal(username=username, auth_method="oauth2")


def validate_digest_nonce(settings: SecuritySettings, nonce: str) -> bool:
    padded = nonce + "=" * (-len(nonce) % 4)
    try:
        raw = base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8")
    except ValueError:
        return False
    issued_at_raw, separator, signature = raw.partition(":")
    if separator != ":":
        return False
    if int(time.time()) - int(issued_at_raw) > settings.digest_nonce_ttl_seconds:
        return False
    expected = _hex_hmac(
        settings.digest_secret,
        f"{issued_at_raw}:{settings.digest_realm}:{settings.digest_opaque}",
    )
    return hmac.compare_digest(expected, signature)


def _encode_signed_payload(payload: dict[str, object], secret: str) -> str:
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    encoded = base64.urlsafe_b64encode(body).decode("ascii").rstrip("=")
    signature = _hex_hmac(secret, encoded)
    return f"{encoded}.{signature}"


def _decode_signed_payload(token: str | None, secret: str) -> dict[str, object] | None:
    if not token or "." not in token:
        return None
    encoded, signature = token.rsplit(".", 1)
    expected = _hex_hmac(secret, encoded)
    if not hmac.compare_digest(expected, signature):
        return None
    padded = encoded + "=" * (-len(encoded) % 4)
    try:
        raw = base64.urlsafe_b64decode(padded.encode("ascii"))
        decoded = json.loads(raw.decode("utf-8"))
    except ValueError:
        return None
    return decoded if isinstance(decoded, dict) else None


def _hex_hmac(secret: str, value: str) -> str:
    return hmac.new(
        secret.encode("utf-8"), value.encode("utf-8"), hashlib.sha256
    ).hexdigest()


def _parse_digest_authorization(value: str) -> dict[str, str]:
    pairs: dict[str, str] = {}
    for chunk in value.split(","):
        key, _, raw_value = chunk.strip().partition("=")
        if not key:
            continue
        normalized = raw_value.strip().strip('"')
        pairs[key.strip()] = normalized
    return pairs


def _parse_cookie_header(value: str) -> dict[str, str]:
    cookies: dict[str, str] = {}
    for item in value.split(";"):
        key, _, raw_value = item.strip().partition("=")
        if key:
            cookies[key] = raw_value
    return cookies
