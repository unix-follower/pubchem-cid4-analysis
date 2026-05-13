import csv
import html
from pathlib import Path
import re
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse


router = APIRouter()


@router.get("/api/v1/reaction-network")
async def reaction_network(request: Request) -> JSONResponse:
    data_dir: Path = request.app.state["data_dir"]
    return _build_reaction_network_payload(data_dir)


def _build_reaction_network_payload(data_dir: Path) -> dict[str, object]:
    pathway_rows = _read_csv_rows(data_dir / "pubchem_cid_4_pathway.csv")
    reaction_rows = _read_csv_rows(data_dir / "pubchem_cid_4_pathwayreaction.csv")
    graph = _build_reaction_network_graph(pathway_rows, reaction_rows)

    pathway_count = sum(
        1 for node in graph["nodes"] if str(node["id"]).startswith("pathway:")
    )
    reaction_count = sum(
        1 for node in graph["nodes"] if str(node["id"]).startswith("reaction:")
    )
    compound_count = sum(
        1 for node in graph["nodes"] if str(node["id"]).startswith("compound:")
    )
    taxonomy_count = sum(
        1 for node in graph["nodes"] if str(node["id"]).startswith("taxonomy:")
    )
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
        pathway_label = (
            pathway_lookup.get(pathway_key) or pathway_key or f"Pathway {row_index}"
        )
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
            taxonomy_suffix = taxonomy_id_value or taxonomy_name.lower().replace(
                " ", "-"
            )
            taxonomy_id = f"taxonomy:{taxonomy_suffix}"
            add_node(taxonomy_id, taxonomy_name or f"Taxonomy {taxonomy_id_value}")
            add_edge(
                f"{reaction_id}->{taxonomy_id}", reaction_id, taxonomy_id, "taxonomy"
            )

        for compound_id in _parse_compound_ids(_string_cell(row, "Reactant_CID")):
            compound_node_id = f"compound:{compound_id}"
            add_node(
                compound_node_id, _format_compound_label(compound_id, compound_labels)
            )
            add_edge(
                f"{compound_node_id}->{reaction_id}",
                compound_node_id,
                reaction_id,
                "reactant",
            )

        for compound_id in _parse_compound_ids(_string_cell(row, "Product_CID")):
            compound_node_id = f"compound:{compound_id}"
            add_node(
                compound_node_id, _format_compound_label(compound_id, compound_labels)
            )
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
        suffix = (
            pathway_accession.split(":", maxsplit=1)[-1] if pathway_accession else ""
        )

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
