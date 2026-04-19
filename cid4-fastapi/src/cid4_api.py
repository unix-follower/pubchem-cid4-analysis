from __future__ import annotations

import csv
import html
import json
import os
import re
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

HEALTH_ROUTE = "/api/health"
CONFORMER_ROUTE_PREFIX = "/api/cid4/conformer/"
CONFORMER_ROUTE_LABEL = "/api/cid4/conformer/{index}"
STRUCTURE_2D_ROUTE = "/api/cid4/structure/2d"
COMPOUND_ROUTE = "/api/cid4/compound"
PATHWAY_ROUTE = "/api/algorithms/pathway"
BIOACTIVITY_ROUTE = "/api/algorithms/bioactivity"
TAXONOMY_ROUTE = "/api/algorithms/taxonomy"
REACTION_NETWORK_ROUTE = "/api/algorithms/reaction-network"
LLM_STATUS_ROUTE = "/api/llm/status"
LLM_TRAIN_ROUTE = "/api/llm/train"
LLM_GENERATE_ROUTE = "/api/llm/generate"
LLM_GENERATE_STREAM_ROUTE = "/api/llm/generate/stream"
LLM_WS_GENERATE_ROUTE = "/ws/llm/generate"


BIOACTIVITY_FIXTURE: dict[str, object] = {
    "records": [
        {"aid": 743069, "assay": "Tox21 ER-alpha agonist", "activityValue": 355.1},
        {"aid": 743070, "assay": "Tox21 ER-alpha antagonist", "activityValue": 18.2},
        {"aid": 651820, "assay": "NCI growth inhibition", "activityValue": 92.4},
        {
            "aid": 540317,
            "assay": "Cell viability counter-screen",
            "activityValue": 112.7,
        },
        {"aid": 504332, "assay": "ChEMBL potency panel", "activityValue": 8.6},
        {
            "aid": 720699,
            "assay": "Nuclear receptor confirmation",
            "activityValue": 61.9,
        },
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


ALGORITHM_PAYLOAD_BUILDERS = {
    PATHWAY_ROUTE: lambda _data_dir: PATHWAY_FIXTURE,
    BIOACTIVITY_ROUTE: lambda _data_dir: BIOACTIVITY_FIXTURE,
    TAXONOMY_ROUTE: lambda _data_dir: TAXONOMY_FIXTURE,
    REACTION_NETWORK_ROUTE: lambda data_dir: _build_reaction_network_payload(data_dir),
}

STATIC_FILE_ROUTES = {
    STRUCTURE_2D_ROUTE: "Structure2D_COMPOUND_CID_4.json",
    COMPOUND_ROUTE: "COMPOUND_CID_4.json",
}

NORMALIZED_STATIC_ROUTES = {
    HEALTH_ROUTE,
    STRUCTURE_2D_ROUTE,
    COMPOUND_ROUTE,
    LLM_STATUS_ROUTE,
    LLM_TRAIN_ROUTE,
    LLM_GENERATE_ROUTE,
    LLM_GENERATE_STREAM_ROUTE,
    LLM_WS_GENERATE_ROUTE,
    PATHWAY_ROUTE,
    BIOACTIVITY_ROUTE,
    TAXONOMY_ROUTE,
    REACTION_NETWORK_ROUTE,
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
        if candidate.is_dir() and all(
            (candidate / filename).is_file() for filename in REQUIRED_DATA_FILES
        ):
            return candidate

    checked = ", ".join(str(path) for path in candidates)
    raise RuntimeError(
        f"Unable to resolve the CID 4 data directory. Checked: {checked}"
    )


def resolve_server_config(
    data_dir: Path,
    preferred_host_env_names: tuple[str, ...] = (),
    preferred_port_env_names: tuple[str, ...] = (),
) -> ServerConfig:
    host = _first_env_value(*preferred_host_env_names, "SERVER_HOST") or "0.0.0.0"
    port = (
        _first_int_env_value(*preferred_port_env_names, "SERVER_PORT", "PORT") or 8443
    )

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
        return _json_response(
            405, {"message": f"Method {normalized_method} not allowed"}
        )

    parsed = urlsplit(target)
    path = parsed.path or "/"
    query = parse_qs(parsed.query, keep_blank_values=True)

    if path == HEALTH_ROUTE:
        return _health_response(query, source, transport_name)
    if path.startswith(CONFORMER_ROUTE_PREFIX):
        return _conformer_response(path, data_dir)
    if path in STATIC_FILE_ROUTES:
        return _file_response(data_dir / STATIC_FILE_ROUTES[path])
    if path in ALGORITHM_PAYLOAD_BUILDERS:
        return _json_response(200, ALGORITHM_PAYLOAD_BUILDERS[path](data_dir))

    return _json_response(404, {"message": "Not found"})


def normalized_route_label(raw_target: str) -> str:
    path = urlsplit(raw_target).path or "/"
    if path in NORMALIZED_STATIC_ROUTES:
        return path
    if path.startswith(CONFORMER_ROUTE_PREFIX):
        suffix = path.removeprefix(CONFORMER_ROUTE_PREFIX)
        if suffix and "/" not in suffix:
            return CONFORMER_ROUTE_LABEL
    return path


def timestamp() -> str:
    return datetime.now(UTC).isoformat()


def _health_response(
    query: dict[str, list[str]], source: str, transport_name: str
) -> ApiResponse:
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


def _conformer_response(path: str, data_dir: Path) -> ApiResponse:
    raw_index = path.removeprefix(CONFORMER_ROUTE_PREFIX)
    if not raw_index or "/" in raw_index:
        return _json_response(404, {"message": "Unknown conformer"})

    try:
        index = int(raw_index)
    except ValueError:
        return _json_response(404, {"message": "Unknown conformer"})

    if index < 1 or index > 6:
        return _json_response(404, {"message": f"Unknown conformer {index}"})

    return _file_response(data_dir / f"Conformer3D_COMPOUND_CID_4({index}).json")


def _build_reaction_network_payload(data_dir: Path) -> dict[str, object]:
    pathway_rows = _read_csv_rows(data_dir / "pubchem_cid_4_pathway.csv")
    reaction_rows = _read_csv_rows(data_dir / "pubchem_cid_4_pathwayreaction.csv")
    graph = _build_reaction_network_graph(pathway_rows, reaction_rows)

    pathway_count = sum(1 for node in graph["nodes"] if str(node["id"]).startswith("pathway:"))
    reaction_count = sum(1 for node in graph["nodes"] if str(node["id"]).startswith("reaction:"))
    compound_count = sum(1 for node in graph["nodes"] if str(node["id"]).startswith("compound:"))
    taxonomy_count = sum(1 for node in graph["nodes"] if str(node["id"]).startswith("taxonomy:"))
    cid4_edges = sum(
        1
        for edge in graph["edges"]
        if str(edge["id"]).startswith("compound:4->reaction:")
        or str(edge["id"]).endswith("->compound:4")
    )

    return {
        "graph": graph,
        "summary": {
            "pathwayCount": int(pathway_count),
            "reactionCount": int(reaction_count),
            "compoundCount": int(compound_count),
            "taxonomyCount": int(taxonomy_count),
            "edgeCount": int(len(graph["edges"])),
            "cid4ParticipationEdgeCount": int(cid4_edges),
        },
    }


def _build_reaction_network_graph(
    pathway_rows: list[dict[str, str]],
    reaction_rows: list[dict[str, str]],
) -> dict[str, object]:
    pathway_lookup = _build_pathway_lookup(pathway_rows)
    compound_labels = _extract_compound_labels(reaction_rows)
    nodes: dict[str, dict[str, object]] = {}
    edges: dict[str, dict[str, object]] = {}

    def add_node(node_id: str, label: str) -> None:
        nodes.setdefault(node_id, {"id": node_id, "label": label})

    def add_edge(
        edge_id: str,
        source: str,
        target: str,
        label: str,
        weight: float = 1.0,
    ) -> None:
        edges.setdefault(
            edge_id,
            {
                "id": edge_id,
                "source": source,
                "target": target,
                "label": label,
                "weight": weight,
            },
        )

    for row_index, row in enumerate(reaction_rows, start=1):
        pathway_key = _string_cell(row, "PubChem_Pathway")
        pathway_id = f"pathway:{pathway_key or row_index}"
        pathway_label = pathway_lookup.get(pathway_key) or pathway_key or f"Pathway {row_index}"
        reaction_id = f"reaction:{pathway_key or 'unassigned'}:{row_index}"
        reaction_label = _truncate_label(
            _clean_text(_string_cell(row, "Equation"))
            or _clean_text(_string_cell(row, "Source_Pathway"))
            or _clean_text(_string_cell(row, "Reaction"))
            or f"Reaction {row_index}",
            max_length=56,
        )

        add_node(pathway_id, pathway_label)
        add_node(reaction_id, reaction_label)
        add_edge(f"{pathway_id}->{reaction_id}", pathway_id, reaction_id, "contains")

        taxonomy_name = _clean_text(_string_cell(row, "Taxonomy"))
        taxonomy_id_value = _string_cell(row, "Taxonomy_ID")
        if taxonomy_name or taxonomy_id_value:
            taxonomy_suffix = taxonomy_id_value or taxonomy_name.lower().replace(" ", "-")
            taxonomy_id = f"taxonomy:{taxonomy_suffix}"
            add_node(taxonomy_id, taxonomy_name or f"Taxonomy {taxonomy_id_value}")
            add_edge(f"{reaction_id}->{taxonomy_id}", reaction_id, taxonomy_id, "taxonomy")

        for compound_id in _parse_compound_ids(_string_cell(row, "Reactant_CID")):
            compound_node_id = f"compound:{compound_id}"
            add_node(compound_node_id, _format_compound_label(compound_id, compound_labels))
            add_edge(
                f"{compound_node_id}->{reaction_id}",
                compound_node_id,
                reaction_id,
                "reactant",
            )

        for compound_id in _parse_compound_ids(_string_cell(row, "Product_CID")):
            compound_node_id = f"compound:{compound_id}"
            add_node(compound_node_id, _format_compound_label(compound_id, compound_labels))
            add_edge(
                f"{reaction_id}->{compound_node_id}",
                reaction_id,
                compound_node_id,
                "product",
            )

    return {
        "id": "cid4-reaction-network",
        "title": "CID 4 reaction network",
        "directed": True,
        "nodes": sorted(nodes.values(), key=lambda node: str(node["id"])),
        "edges": sorted(edges.values(), key=lambda edge: str(edge["id"])),
    }


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _build_pathway_lookup(pathway_rows: list[dict[str, str]]) -> dict[str, str]:
    lookup: dict[str, str] = {}

    for row in pathway_rows:
        source_id = _string_cell(row, "Source_ID")
        pathway_accession = _string_cell(row, "Pathway_Accession")
        label = _string_cell(row, "Pathway_Name") or source_id or pathway_accession
        suffix = pathway_accession.split(":", maxsplit=1)[-1] if pathway_accession else ""

        for key in (source_id, suffix, pathway_accession):
            if key:
                lookup[key] = label

    return lookup


def _extract_compound_labels(reaction_rows: list[dict[str, str]]) -> dict[int, str]:
    label_by_cid = {4: "CID 4 (1-Amino-2-propanol)"}
    anchor_pattern = re.compile(r"compound/(\d+)[^>]*>([^<]+)<", flags=re.IGNORECASE)

    for row in reaction_rows:
        for value in row.values():
            if not value:
                continue
            if "compound/" not in value:
                continue

            for raw_cid, raw_label in anchor_pattern.findall(value):
                compound_id = int(raw_cid)
                cleaned_label = _clean_text(raw_label)
                if compound_id not in label_by_cid and cleaned_label:
                    label_by_cid[compound_id] = cleaned_label

    return label_by_cid


def _parse_compound_ids(raw_value: str) -> list[int]:
    compound_ids: list[int] = []

    for token in raw_value.split("|"):
        stripped = token.strip()
        if not stripped:
            continue
        try:
            compound_ids.append(int(stripped))
        except ValueError:
            continue

    return compound_ids


def _format_compound_label(compound_id: int, label_by_cid: dict[int, str]) -> str:
    label = label_by_cid.get(compound_id)
    if label:
        return label if label.startswith("CID ") else f"CID {compound_id} ({label})"
    return f"CID {compound_id}"


def _string_cell(row: dict[str, str], column: str) -> str:
    return str(row.get(column, "") or "").strip()


def _clean_text(value: str) -> str:
    without_tags = re.sub(r"<[^>]+>", "", html.unescape(value))
    return re.sub(r"\s+", " ", without_tags).strip()


def _truncate_label(value: str, max_length: int) -> str:
    if len(value) <= max_length:
        return value
    return f"{value[: max_length - 1].rstrip()}…"


def _file_response(path: Path) -> ApiResponse:
    if not path.is_file():
        return _json_response(404, {"message": f"Missing JSON payload {path.name}"})
    return ApiResponse(status_code=200, body=path.read_text(encoding="utf-8"))


def _json_response(status_code: int, payload: dict[str, object]) -> ApiResponse:
    return ApiResponse(status_code=status_code, body=json.dumps(payload))


def _resolve_server_config_from_crypto_summary(
    data_dir: Path, host: str, port: int
) -> ServerConfig:
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
