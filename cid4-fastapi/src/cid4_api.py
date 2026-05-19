import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ServerConfig:
    host: str
    port: int
    cert_file: Path
    key_file: Path
    key_password: str | None


@dataclass(frozen=True)
class ApiResponse:
    status_code: int
    body: str
    content_type: str = "application/json"


def resolve_data_dir() -> Path:
    candidates: list[Path] = []
    if os.environ.get("DATA_DIR"):
        candidates.append(Path(os.environ["DATA_DIR"]).expanduser().resolve())

    candidates.append((Path.cwd().resolve() / "../data").resolve())

    for candidate in candidates:
        if candidate.is_dir():
            return candidate

    checked = ", ".join(str(path) for path in candidates)
    raise RuntimeError(
        f"Unable to resolve the CID 4 data directory. Checked: {checked}"
    )


def resolve_server_config() -> ServerConfig:
    host = os.environ.get("SERVER_HOST") or "0.0.0.0"
    port = int(os.environ.get("SERVER_PORT") or 8443)

    config = ServerConfig(
        host=host,
        port=port,
        cert_file=Path(os.environ.get("TLS_CERT_FILE")).expanduser().resolve(),
        key_file=Path(os.environ.get("TLS_KEY_FILE")).expanduser().resolve(),
        key_password=os.environ.get("TLS_KEY_PASSWORD"),
    )

    if not config.cert_file.is_file():
        raise RuntimeError(f"TLS certificate file does not exist: {config.cert_file}")
    if not config.key_file.is_file():
        raise RuntimeError(f"TLS private key file does not exist: {config.key_file}")

    return config
