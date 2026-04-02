from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FastApiServerConfig:
    host: str
    port: int
    cert_file: Path
    key_file: Path
    key_password: str | None


REQUIRED_DATA_FILES = (
    "COMPOUND_CID_4.json",
    "Structure2D_COMPOUND_CID_4.json",
    "Conformer3D_COMPOUND_CID_4(1).json",
)


def resolve_data_dir() -> Path:
    candidates: list[Path] = []
    if os.environ.get("DATA_DIR"):
        candidates.append(Path(os.environ["DATA_DIR"]).expanduser().resolve())

    repo_data_dir = Path(__file__).resolve().parents[3] / "data"
    candidates.extend(
        [
            repo_data_dir.resolve(),
            Path.cwd().resolve() / "data",
            (Path.cwd().resolve() / "../data").resolve(),
        ]
    )

    for candidate in candidates:
        if candidate.is_dir() and all((candidate / filename).is_file() for filename in REQUIRED_DATA_FILES):
            return candidate

    checked = ", ".join(str(path) for path in candidates)
    raise RuntimeError(f"Unable to resolve the CID 4 data directory. Checked: {checked}")


def resolve_server_config(data_dir: Path) -> FastApiServerConfig:
    host = _first_env_value("FASTAPI_HOST", "SERVER_HOST") or "0.0.0.0"
    port = _first_int_env_value("FASTAPI_PORT", "SERVER_PORT", "PORT") or 8443

    cert_file = _first_env_value("TLS_CERT_FILE")
    key_file = _first_env_value("TLS_KEY_FILE")
    key_password = _first_env_value("TLS_KEY_PASSWORD")

    if cert_file or key_file:
        if not cert_file or not key_file:
            raise RuntimeError(
                "Set both TLS_CERT_FILE and TLS_KEY_FILE, or neither to use the crypto summary fallback."
            )
        config = FastApiServerConfig(
            host=host,
            port=port,
            cert_file=Path(cert_file).expanduser().resolve(),
            key_file=Path(key_file).expanduser().resolve(),
            key_password=key_password,
        )
    else:
        config = _resolve_server_config_from_crypto_summary(data_dir, host, port)

    if not config.cert_file.is_file():
        raise RuntimeError(f"TLS certificate file does not exist: {config.cert_file}")
    if not config.key_file.is_file():
        raise RuntimeError(f"TLS private key file does not exist: {config.key_file}")

    return config


def _resolve_server_config_from_crypto_summary(data_dir: Path, host: str, port: int) -> FastApiServerConfig:
    summary_path = data_dir / "out" / "crypto" / "cid4_crypto.summary.json"
    if not summary_path.is_file():
        raise RuntimeError(
            "No TLS certificate configuration found. Set TLS_CERT_FILE and TLS_KEY_FILE, "
            f"or generate {summary_path} first."
        )

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    pem_paths = summary.get("x509_and_pkcs12", {}).get("pem_paths", {})
    cert_path = pem_paths.get("certificate")
    key_path = pem_paths.get("private_key")
    if not cert_path or not key_path:
        raise RuntimeError(f"FastAPI TLS fallback requires PEM paths in {summary_path}")

    return FastApiServerConfig(
        host=host,
        port=port,
        cert_file=Path(cert_path).expanduser().resolve(),
        key_file=Path(key_path).expanduser().resolve(),
        key_password=summary.get("demo_password"),
    )


def _first_env_value(*names: str) -> str | None:
    for name in names:
        value = os.environ.get(name)
        if value:
            return value
    return None


def _first_int_env_value(*names: str) -> int | None:
    for name in names:
        value = os.environ.get(name)
        if value:
            try:
                parsed = int(value)
            except ValueError:
                continue
            if parsed > 0:
                return parsed
    return None
