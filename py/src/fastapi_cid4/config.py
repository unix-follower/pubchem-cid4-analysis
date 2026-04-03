from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from cid4_api import ServerConfig
from cid4_api import resolve_data_dir as shared_resolve_data_dir
from cid4_api import resolve_server_config as shared_resolve_server_config

FastApiServerConfig = ServerConfig


@dataclass(frozen=True)
class SecuritySettings:
    allowed_origins: tuple[str, ...]
    trusted_hosts: tuple[str, ...]
    default_auth_method: str
    basic_users: dict[str, str]
    digest_users: dict[str, str]
    oauth2_tokens: dict[str, str]
    session_cookie_name: str
    csrf_cookie_name: str
    csrf_header_name: str
    session_secret: str
    csrf_secret: str
    digest_secret: str
    digest_realm: str
    digest_opaque: str
    digest_nonce_ttl_seconds: int
    session_ttl_seconds: int
    keycloak_base_url: str | None
    keycloak_realm: str | None
    keycloak_client_id: str | None
    keycloak_redirect_uri: str | None


def resolve_security_settings(environ: dict[str, str] | None = None) -> SecuritySettings:
    env = os.environ if environ is None else environ
    return SecuritySettings(
        allowed_origins=_split_csv(
            env.get(
                "FASTAPI_ALLOWED_ORIGINS",
                "http://localhost:4200,http://127.0.0.1:4200,http://testserver",
            )
        ),
        trusted_hosts=_split_csv(env.get("FASTAPI_TRUSTED_HOSTS", "localhost,127.0.0.1,testserver")),
        default_auth_method=env.get("FASTAPI_DEFAULT_AUTH_METHOD", "basic"),
        basic_users=_load_user_map(
            env,
            "FASTAPI_BASIC_USERS_JSON",
            {"analyst": "cid4-basic-password"},
        ),
        digest_users=_load_user_map(
            env,
            "FASTAPI_DIGEST_USERS_JSON",
            {"digestor": "cid4-digest-password"},
        ),
        oauth2_tokens=_load_user_map(
            env,
            "FASTAPI_KEYCLOAK_TOKENS_JSON",
            {"cid4-keycloak-dev-token": "keycloak-analyst"},
        ),
        session_cookie_name=env.get("FASTAPI_SESSION_COOKIE_NAME", "cid4_session"),
        csrf_cookie_name=env.get("FASTAPI_CSRF_COOKIE_NAME", "cid4_csrf"),
        csrf_header_name=env.get("FASTAPI_CSRF_HEADER_NAME", "X-CSRF-Token"),
        session_secret=env.get("FASTAPI_SESSION_SECRET", "cid4-fastapi-session-secret"),
        csrf_secret=env.get("FASTAPI_CSRF_SECRET", "cid4-fastapi-csrf-secret"),
        digest_secret=env.get("FASTAPI_DIGEST_SECRET", "cid4-fastapi-digest-secret"),
        digest_realm=env.get("FASTAPI_DIGEST_REALM", "CID4 Chat"),
        digest_opaque=env.get("FASTAPI_DIGEST_OPAQUE", "cid4-chat-opaque"),
        digest_nonce_ttl_seconds=int(env.get("FASTAPI_DIGEST_NONCE_TTL_SECONDS", "300")),
        session_ttl_seconds=int(env.get("FASTAPI_SESSION_TTL_SECONDS", "28800")),
        keycloak_base_url=env.get("FASTAPI_KEYCLOAK_BASE_URL") or None,
        keycloak_realm=env.get("FASTAPI_KEYCLOAK_REALM") or None,
        keycloak_client_id=env.get("FASTAPI_KEYCLOAK_CLIENT_ID") or None,
        keycloak_redirect_uri=env.get("FASTAPI_KEYCLOAK_REDIRECT_URI") or None,
    )


def resolve_data_dir() -> Path:
    return shared_resolve_data_dir()


def resolve_server_config(data_dir: Path) -> FastApiServerConfig:
    return shared_resolve_server_config(
        data_dir,
        preferred_host_env_names=("FASTAPI_HOST",),
        preferred_port_env_names=("FASTAPI_PORT",),
    )


def _split_csv(raw_value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in raw_value.split(",") if item.strip())


def _load_user_map(
    environ: dict[str, str],
    env_name: str,
    fallback: dict[str, str],
) -> dict[str, str]:
    raw_value = environ.get(env_name)
    if not raw_value:
        return dict(fallback)
    loaded = json.loads(raw_value)
    if not isinstance(loaded, dict):
        return dict(fallback)
    return {str(key): str(value) for key, value in loaded.items()}
