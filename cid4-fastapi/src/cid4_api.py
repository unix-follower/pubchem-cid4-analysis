from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import parse_qs, urlsplit


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


REQUIRED_DATA_FILES = (
    "COMPOUND_CID_4.json",
    "Structure2D_COMPOUND_CID_4.json",
    "Conformer3D_COMPOUND_CID_4(1).json",
)


BIOACTIVITY_FIXTURE: dict[str, object] = {
    "records": [
        {"aid": 743069, "assay": "Tox21 ER-alpha agonist", "activityValue": 355.1},
        {"aid": 743070, "assay": "Tox21 ER-alpha antagonist", "activityValue": 18.2},
        {"aid": 651820, "assay": "NCI growth inhibition", "activityValue": 92.4},
        {"aid": 540317, "assay": "Cell viability counter-screen", "activityValue": 112.7},
        {"aid": 504332, "assay": "ChEMBL potency panel", "activityValue": 8.6},
        {"aid": 720699, "assay": "Nuclear receptor confirmation", "activityValue": 61.9},
        {"aid": 743053, "assay": "Tox21 luciferase artifact", "activityValue": 140.4},
        {"aid": 743122, "assay": "Dose-response validation", "activityValue": 28.8},
        {"aid": 1259368, "assay": "Secondary pharmacology", "activityValue": 4.2},
        {"aid": 1345073, "assay": "Metabolism pathway screen", "activityValue": 205.5},
    ]
}

TAXONOMY_FIXTURE: dict[str, object] = {
    "organisms": [
        {"taxonomyId": 9913, "sourceOrganism": "Bos taurus"},
        {"taxonomyId": 9913, "sourceOrganism": "Bos taurus"},
        {"taxonomyId": 9823, "sourceOrganism": "Sus scrofa"},
        {"taxonomyId": 9031, "sourceOrganism": "Gallus gallus"},
        {"taxonomyId": 9031, "sourceOrganism": "Gallus gallus"},
        {"taxonomyId": 9103, "sourceOrganism": "Meleagris gallopavo"},
        {"taxonomyId": 9986, "sourceOrganism": "Oryctolagus cuniculus"},
        {"taxonomyId": 9685, "sourceOrganism": "Felis catus"},
    ]
}

PATHWAY_FIXTURE: dict[str, object] = {
    "graph": {
        "id": "glutathione-metabolism-iii",
        "title": "Glutathione Metabolism III",
        "directed": True,
        "nodes": [
            {"id": "step-1", "label": "Import precursor"},
            {"id": "step-2", "label": "Activate cysteine"},
            {"id": "step-3", "label": "Ligate glutamate"},
            {"id": "step-4", "label": "Add glycine"},
            {"id": "step-5", "label": "Reduce intermediate"},
            {"id": "step-6", "label": "Export product"},
        ],
        "edges": [
            {"id": "step-1-2", "source": "step-1", "target": "step-2"},
            {"id": "step-2-3", "source": "step-2", "target": "step-3"},
            {"id": "step-3-4", "source": "step-3", "target": "step-4"},
            {"id": "step-3-5", "source": "step-3", "target": "step-5"},
            {"id": "step-4-6", "source": "step-4", "target": "step-6"},
            {"id": "step-5-6", "source": "step-5", "target": "step-6"},
        ],
    }
}


def resolve_data_dir() -> Path:
    candidates: list[Path] = []
    if os.environ.get("DATA_DIR"):
        candidates.append(Path(os.environ["DATA_DIR"]).expanduser().resolve())

    repo_data_dir = Path(__file__).resolve().parents[2] / "data"
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


def resolve_server_config(
    data_dir: Path,
    preferred_host_env_names: tuple[str, ...] = (),
    preferred_port_env_names: tuple[str, ...] = (),
) -> ServerConfig:
    host = _first_env_value(*preferred_host_env_names, "SERVER_HOST") or "0.0.0.0"
    port = _first_int_env_value(*preferred_port_env_names, "SERVER_PORT", "PORT") or 8443

    cert_file = _first_env_value("TLS_CERT_FILE")
    key_file = _first_env_value("TLS_KEY_FILE")
    key_password = _first_env_value("TLS_KEY_PASSWORD")

    if cert_file or key_file:
        if not cert_file or not key_file:
            raise RuntimeError(
                "Set both TLS_CERT_FILE and TLS_KEY_FILE, or neither to use the crypto summary fallback."
            )
        config = ServerConfig(
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


def route_api_request(
    method: str,
    target: str,
    data_dir: Path,
    source: str,
    transport_name: str,
) -> ApiResponse:
    normalized_method = method.upper()
    if normalized_method == "OPTIONS":
        return ApiResponse(status_code=204, body="")
    if normalized_method != "GET":
        return _json_response(405, {"message": f"Method {normalized_method} not allowed"})

    parsed = urlsplit(target)
    path = parsed.path or "/"
    query = parse_qs(parsed.query, keep_blank_values=True)

    if path == "/api/health":
        if query.get("mode", [None])[0] == "error":
            return _json_response(
                503,
                {
                    "message": f"Transport error from {transport_name}",
                    "source": source,
                    "timestamp": timestamp(),
                },
            )

        return _json_response(
            200,
            {
                "message": f"{transport_name} transport is healthy",
                "source": source,
                "timestamp": timestamp(),
            },
        )

    conformer_prefix = "/api/cid4/conformer/"
    if path.startswith(conformer_prefix):
        raw_index = path.removeprefix(conformer_prefix)
        if not raw_index or "/" in raw_index:
            return _json_response(404, {"message": "Unknown conformer"})
        try:
            index = int(raw_index)
        except ValueError:
            return _json_response(404, {"message": "Unknown conformer"})
        if index < 1 or index > 6:
            return _json_response(404, {"message": f"Unknown conformer {index}"})
        return _file_response(data_dir / f"Conformer3D_COMPOUND_CID_4({index}).json")

    if path == "/api/cid4/structure/2d":
        return _file_response(data_dir / "Structure2D_COMPOUND_CID_4.json")
    if path == "/api/cid4/compound":
        return _file_response(data_dir / "COMPOUND_CID_4.json")
    if path == "/api/algorithms/pathway":
        return _json_response(200, PATHWAY_FIXTURE)
    if path == "/api/algorithms/bioactivity":
        return _json_response(200, BIOACTIVITY_FIXTURE)
    if path == "/api/algorithms/taxonomy":
        return _json_response(200, TAXONOMY_FIXTURE)

    return _json_response(404, {"message": "Not found"})


def normalized_route_label(raw_target: str) -> str:
    path = urlsplit(raw_target).path or "/"
    if path == "/api/health":
        return "/api/health"
    if path == "/api/cid4/structure/2d":
        return "/api/cid4/structure/2d"
    if path == "/api/cid4/compound":
        return "/api/cid4/compound"
    if path == "/api/llm/status":
        return "/api/llm/status"
    if path == "/api/llm/train":
        return "/api/llm/train"
    if path == "/api/llm/generate":
        return "/api/llm/generate"
    if path == "/api/llm/generate/stream":
        return "/api/llm/generate/stream"
    if path == "/ws/llm/generate":
        return "/ws/llm/generate"
    if path == "/api/algorithms/pathway":
        return "/api/algorithms/pathway"
    if path == "/api/algorithms/bioactivity":
        return "/api/algorithms/bioactivity"
    if path == "/api/algorithms/taxonomy":
        return "/api/algorithms/taxonomy"
    if path.startswith("/api/cid4/conformer/"):
        suffix = path.removeprefix("/api/cid4/conformer/")
        if suffix and "/" not in suffix:
            return "/api/cid4/conformer/{index}"
    return path


def timestamp() -> str:
    return datetime.now(UTC).isoformat()


def _file_response(path: Path) -> ApiResponse:
    if not path.is_file():
        return _json_response(404, {"message": f"Missing JSON payload {path.name}"})
    return ApiResponse(status_code=200, body=path.read_text(encoding="utf-8"))


def _json_response(status_code: int, payload: dict[str, object]) -> ApiResponse:
    return ApiResponse(status_code=status_code, body=json.dumps(payload))


def _resolve_server_config_from_crypto_summary(data_dir: Path, host: str, port: int) -> ServerConfig:
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
        raise RuntimeError(f"TLS fallback requires PEM paths in {summary_path}")

    return ServerConfig(
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
