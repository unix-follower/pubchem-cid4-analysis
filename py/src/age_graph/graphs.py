from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

import cid4_analysis

COMPOUND_FILENAME = "COMPOUND_CID_4.json"
CONFORMER_FILENAME = "Conformer3D_COMPOUND_CID_4(1).json"
STRUCTURE_2D_FILENAME = "Structure2D_COMPOUND_CID_4.json"

BIOACTIVITY_FILENAME = "pubchem_cid_4_bioactivity.csv"
PATHWAY_FILENAME = "pubchem_cid_4_pathway.csv"
PATHWAY_REACTION_FILENAME = "pubchem_cid_4_pathwayreaction.csv"
TAXONOMY_FILENAME = "pubchem_cid_4_consolidatedcompoundtaxonomy.csv"

DOT_FILENAME = "cid_4.dot"


def load_bioactivity_frame(filename: str = BIOACTIVITY_FILENAME) -> pd.DataFrame:
    return _read_csv(filename)


def load_pathway_frame(filename: str = PATHWAY_FILENAME) -> pd.DataFrame:
    return _read_csv(filename)


def load_pathway_reaction_frame(
    filename: str = PATHWAY_REACTION_FILENAME,
) -> pd.DataFrame:
    return _read_csv(filename)


def load_taxonomy_frame(filename: str = TAXONOMY_FILENAME) -> pd.DataFrame:
    return _read_csv(filename)


def _read_csv(filename: str) -> pd.DataFrame:
    path = Path(cid4_analysis.resolve_data_path(filename))
    return pd.read_csv(path, low_memory=False)


@dataclass(frozen=True)
class GraphNode:
    graph_id: str
    label: str
    properties: dict[str, Any]


@dataclass(frozen=True)
class GraphEdge:
    source_id: str
    source_label: str
    target_id: str
    target_label: str
    label: str
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass
class PropertyGraph:
    nodes: dict[str, GraphNode] = field(default_factory=dict)
    edges: list[GraphEdge] = field(default_factory=list)
    _edge_keys: set[tuple[str, str, str, str, str]] = field(default_factory=set, init=False, repr=False)

    def add_node(self, node: GraphNode) -> None:
        existing = self.nodes.get(node.graph_id)
        if existing is None:
            self.nodes[node.graph_id] = node
            return

        merged = dict(existing.properties)
        for key, value in node.properties.items():
            if value not in (None, "", [], {}):
                merged[key] = value
        self.nodes[node.graph_id] = GraphNode(graph_id=node.graph_id, label=existing.label, properties=merged)

    def add_edge(self, edge: GraphEdge) -> None:
        key = (
            edge.source_id,
            edge.source_label,
            edge.label,
            edge.target_id,
            edge.target_label,
        )
        if key in self._edge_keys:
            return
        self._edge_keys.add(key)
        self.edges.append(edge)

    def extend(self, other: PropertyGraph) -> None:
        for node in other.nodes.values():
            self.add_node(node)
        for edge in other.edges:
            self.add_edge(edge)

    def to_summary(self) -> dict[str, Any]:
        node_counts: dict[str, int] = {}
        for node in self.nodes.values():
            node_counts[node.label] = node_counts.get(node.label, 0) + 1

        edge_counts: dict[str, int] = {}
        for edge in self.edges:
            edge_counts[edge.label] = edge_counts.get(edge.label, 0) + 1

        return {
            "node_count": int(len(self.nodes)),
            "edge_count": int(len(self.edges)),
            "node_label_counts": dict(sorted(node_counts.items())),
            "edge_label_counts": dict(sorted(edge_counts.items())),
            "sample_nodes": [
                {
                    "graph_id": node.graph_id,
                    "label": node.label,
                    "properties": node.properties,
                }
                for node in list(self.nodes.values())[:8]
            ],
            "sample_edges": [
                {
                    "source_id": edge.source_id,
                    "source_label": edge.source_label,
                    "label": edge.label,
                    "target_id": edge.target_id,
                    "target_label": edge.target_label,
                    "properties": edge.properties,
                }
                for edge in self.edges[:8]
            ],
        }


def build_unified_graph() -> PropertyGraph:
    graph = PropertyGraph()
    for partial_graph in (
        build_molecular_graph(),
        build_organism_graph(),
        build_pathway_reaction_graph(),
        build_assay_graph(),
    ):
        graph.extend(partial_graph)
    return graph


def build_compound_node(filename: str = COMPOUND_FILENAME) -> GraphNode:
    path = Path(cid4_analysis.resolve_data_path(filename))
    with path.open(encoding="utf-8") as file:
        record = json.load(file)["Record"]

    cid = int(record["RecordNumber"])
    return GraphNode(
        graph_id=compound_graph_id(cid),
        label="Compound",
        properties={
            "cid": cid,
            "name": str(record.get("RecordTitle", f"CID {cid}")),
            "record_type": str(record.get("RecordType", "CID")),
            "source_file": filename,
        },
    )


def build_molecular_graph(filename: str = CONFORMER_FILENAME) -> PropertyGraph:
    compound = cid4_analysis.load_conformer_compound(filename)
    graph = PropertyGraph()
    compound_node = build_compound_node()
    graph.add_node(compound_node)

    cid = int(compound["id"]["id"]["cid"])
    atom_ids = list(compound["atoms"]["aid"])
    atomic_numbers = list(compound["atoms"]["element"])
    bond_starts = list(compound["bonds"]["aid1"])
    bond_ends = list(compound["bonds"]["aid2"])
    bond_orders = list(compound["bonds"].get("order", [1] * len(bond_starts)))
    conformer = compound["coords"][0]["conformers"][0]
    x_coords = list(conformer.get("x", []))
    y_coords = list(conformer.get("y", []))
    z_coords = list(conformer.get("z", [None] * len(atom_ids)))

    for index, atom_id in enumerate(atom_ids):
        symbol = cid4_analysis.PERIODIC_TABLE.GetElementSymbol(int(atomic_numbers[index]))
        atom_node = GraphNode(
            graph_id=atom_graph_id(atom_id),
            label="Atom",
            properties={
                "aid": int(atom_id),
                "cid": cid,
                "element": symbol,
                "atomic_number": int(atomic_numbers[index]),
                "x": float(x_coords[index]),
                "y": float(y_coords[index]),
                "z": None if z_coords[index] is None else float(z_coords[index]),
                "source_file": filename,
            },
        )
        graph.add_node(atom_node)
        graph.add_edge(
            GraphEdge(
                source_id=compound_node.graph_id,
                source_label="Compound",
                target_id=atom_node.graph_id,
                target_label="Atom",
                label="HAS_ATOM",
                properties={"source_file": filename},
            )
        )

    for aid1, aid2, order in zip(bond_starts, bond_ends, bond_orders, strict=True):
        graph.add_edge(
            GraphEdge(
                source_id=atom_graph_id(int(aid1)),
                source_label="Atom",
                target_id=atom_graph_id(int(aid2)),
                target_label="Atom",
                label="BOND",
                properties={
                    "order": int(order),
                    "cid": cid,
                    "source_file": filename,
                },
            )
        )

    return graph


def build_structure_2d_graph(filename: str = STRUCTURE_2D_FILENAME) -> PropertyGraph:
    return build_molecular_graph(filename=filename)


def build_organism_graph(
    dot_filename: str = DOT_FILENAME,
    taxonomy_filename: str = TAXONOMY_FILENAME,
    frame: pd.DataFrame | None = None,
) -> PropertyGraph:
    graph = PropertyGraph()
    compound_node = build_compound_node()
    graph.add_node(compound_node)

    dot_graph = parse_dot_organism_graph(
        Path(cid4_analysis.resolve_data_path(dot_filename)).read_text(encoding="utf-8")
    )
    for organism_name, organism_group in sorted(dot_graph["organisms"].items()):
        organism_node = GraphNode(
            graph_id=organism_graph_id("dot", organism_name),
            label="Organism",
            properties={
                "name": organism_name,
                "source": "cid_4.dot",
                "group": organism_group,
            },
        )
        graph.add_node(organism_node)

    for source_name, target_name in dot_graph["edges"]:
        if source_name != dot_graph["compound_alias"]:
            continue
        graph.add_edge(
            GraphEdge(
                source_id=compound_node.graph_id,
                source_label="Compound",
                target_id=organism_graph_id("dot", target_name),
                target_label="Organism",
                label="ASSOCIATED_WITH",
                properties={"source_file": dot_filename, "evidence_type": "dot_graph"},
            )
        )

    taxonomy_frame = load_taxonomy_frame(taxonomy_filename) if frame is None else frame
    for row_index, row in taxonomy_frame.iterrows():
        organism_name = clean_text(row.get("Source_Organism")) or f"taxonomy-row-{row_index}"
        organism_node = GraphNode(
            graph_id=organism_graph_id(
                "taxonomy",
                first_non_empty(row.get("Source_Organism_ID"), organism_name),
            ),
            label="Organism",
            properties={
                "name": organism_name,
                "source_organism_id": safe_int(row.get("Source_Organism_ID")),
                "source": clean_text(row.get("Source")),
                "data_source": clean_text(row.get("Data_Source")),
                "taxonomy_id": safe_int(row.get("Taxonomy_ID")),
                "source_file": taxonomy_filename,
            },
        )
        graph.add_node(organism_node)

        source_name = clean_text(row.get("Source"))
        if source_name:
            source_node = GraphNode(
                graph_id=source_graph_id(source_name),
                label="Source",
                properties={"name": source_name, "source_file": taxonomy_filename},
            )
            graph.add_node(source_node)
            graph.add_edge(
                GraphEdge(
                    source_id=organism_node.graph_id,
                    source_label="Organism",
                    target_id=source_node.graph_id,
                    target_label="Source",
                    label="FROM_SOURCE",
                    properties={"source_file": taxonomy_filename},
                )
            )

        graph.add_edge(
            GraphEdge(
                source_id=compound_node.graph_id,
                source_label="Compound",
                target_id=organism_node.graph_id,
                target_label="Organism",
                label="FOUND_IN",
                properties={
                    "source_file": taxonomy_filename,
                    "evidence_type": "taxonomy_csv",
                },
            )
        )

        taxonomy_id = safe_int(row.get("Taxonomy_ID"))
        if taxonomy_id is not None:
            taxon_node = GraphNode(
                graph_id=taxon_graph_id(taxonomy_id),
                label="Taxon",
                properties={
                    "taxonomy_id": taxonomy_id,
                    "taxonomy": clean_text(row.get("Taxonomy")),
                    "source_file": taxonomy_filename,
                },
            )
            graph.add_node(taxon_node)
            graph.add_edge(
                GraphEdge(
                    source_id=organism_node.graph_id,
                    source_label="Organism",
                    target_id=taxon_node.graph_id,
                    target_label="Taxon",
                    label="IN_TAXON",
                    properties={"source_file": taxonomy_filename},
                )
            )

    return graph


def build_pathway_reaction_graph(
    pathway_filename: str = PATHWAY_FILENAME,
    pathway_reaction_filename: str = PATHWAY_REACTION_FILENAME,
    pathway_frame: pd.DataFrame | None = None,
    reaction_frame: pd.DataFrame | None = None,
) -> PropertyGraph:
    graph = PropertyGraph()
    compound_node = build_compound_node()
    graph.add_node(compound_node)

    loaded_pathway_frame = load_pathway_frame(pathway_filename) if pathway_frame is None else pathway_frame
    for row_index, row in loaded_pathway_frame.iterrows():
        accession = clean_text(first_non_empty(row.get("Pathway_Accession"), row.get("Source_ID"), row_index))
        pathway_node = GraphNode(
            graph_id=pathway_graph_id(accession),
            label="Pathway",
            properties={
                "pathway_accession": accession,
                "name": clean_text(row.get("Pathway_Name")),
                "pathway_type": clean_text(row.get("Pathway_Type")),
                "pathway_category": clean_text(row.get("Pathway_Category")),
                "data_source": clean_text(row.get("Data_Source")),
                "source_file": pathway_filename,
            },
        )
        graph.add_node(pathway_node)
        graph.add_edge(
            GraphEdge(
                source_id=compound_node.graph_id,
                source_label="Compound",
                target_id=pathway_node.graph_id,
                target_label="Pathway",
                label="PARTICIPATES_IN",
                properties={"source_file": pathway_filename},
            )
        )

        taxonomy_id = safe_int(row.get("Taxonomy_ID"))
        if taxonomy_id is not None:
            taxon_node = GraphNode(
                graph_id=taxon_graph_id(taxonomy_id),
                label="Taxon",
                properties={
                    "taxonomy_id": taxonomy_id,
                    "taxonomy": clean_text(row.get("Taxonomy_Name")),
                    "source_file": pathway_filename,
                },
            )
            graph.add_node(taxon_node)
            graph.add_edge(
                GraphEdge(
                    source_id=pathway_node.graph_id,
                    source_label="Pathway",
                    target_id=taxon_node.graph_id,
                    target_label="Taxon",
                    label="IN_TAXON",
                    properties={"source_file": pathway_filename},
                )
            )

    loaded_reaction_frame = (
        load_pathway_reaction_frame(pathway_reaction_filename) if reaction_frame is None else reaction_frame
    )
    for row_index, row in loaded_reaction_frame.iterrows():
        pathway_id = clean_text(first_non_empty(row.get("PubChem_Pathway"), row.get("Source_Pathway"), "unknown"))
        reaction_id = reaction_graph_id(f"{pathway_id}:{row_index}")
        reaction_node = GraphNode(
            graph_id=reaction_id,
            label="Reaction",
            properties={
                "equation": clean_text(row.get("Equation")),
                "reaction": clean_text(row.get("Reaction")),
                "control": clean_text(row.get("Control")),
                "pathway_accession": pathway_id,
                "source_file": pathway_reaction_filename,
            },
        )
        graph.add_node(reaction_node)

        graph.add_edge(
            GraphEdge(
                source_id=pathway_graph_id(pathway_id),
                source_label="Pathway",
                target_id=reaction_node.graph_id,
                target_label="Reaction",
                label="IN_PATHWAY",
                properties={"source_file": pathway_reaction_filename},
            )
        )

        taxonomy_id = safe_int(row.get("Taxonomy_ID"))
        if taxonomy_id is not None:
            taxon_node = GraphNode(
                graph_id=taxon_graph_id(taxonomy_id),
                label="Taxon",
                properties={
                    "taxonomy_id": taxonomy_id,
                    "taxonomy": clean_text(row.get("Taxonomy")),
                    "source_file": pathway_reaction_filename,
                },
            )
            graph.add_node(taxon_node)
            graph.add_edge(
                GraphEdge(
                    source_id=reaction_node.graph_id,
                    source_label="Reaction",
                    target_id=taxon_node.graph_id,
                    target_label="Taxon",
                    label="IN_TAXON",
                    properties={"source_file": pathway_reaction_filename},
                )
            )

        protein_accession = clean_text(row.get("PubChem_Protein"))
        if protein_accession:
            protein_node = GraphNode(
                graph_id=protein_graph_id(protein_accession),
                label="Protein",
                properties={
                    "protein_accession": protein_accession,
                    "source_file": pathway_reaction_filename,
                },
            )
            graph.add_node(protein_node)
            graph.add_edge(
                GraphEdge(
                    source_id=reaction_node.graph_id,
                    source_label="Reaction",
                    target_id=protein_node.graph_id,
                    target_label="Protein",
                    label="LINKED_TO_PROTEIN",
                    properties={"source_file": pathway_reaction_filename},
                )
            )

        gene_id = clean_text(row.get("PubChem_Gene"))
        if gene_id:
            gene_node = GraphNode(
                graph_id=gene_graph_id(gene_id),
                label="Gene",
                properties={
                    "gene_id": gene_id,
                    "source_file": pathway_reaction_filename,
                },
            )
            graph.add_node(gene_node)
            graph.add_edge(
                GraphEdge(
                    source_id=reaction_node.graph_id,
                    source_label="Reaction",
                    target_id=gene_node.graph_id,
                    target_label="Gene",
                    label="LINKED_TO_GENE",
                    properties={"source_file": pathway_reaction_filename},
                )
            )

        enzyme_id = clean_text(row.get("PubChem_Enzyme"))
        if enzyme_id:
            enzyme_node = GraphNode(
                graph_id=enzyme_graph_id(enzyme_id),
                label="Enzyme",
                properties={
                    "enzyme_id": enzyme_id,
                    "source_file": pathway_reaction_filename,
                },
            )
            graph.add_node(enzyme_node)
            graph.add_edge(
                GraphEdge(
                    source_id=reaction_node.graph_id,
                    source_label="Reaction",
                    target_id=enzyme_node.graph_id,
                    target_label="Enzyme",
                    label="CATALYZED_BY",
                    properties={"source_file": pathway_reaction_filename},
                )
            )

    return graph


def build_assay_graph(filename: str = BIOACTIVITY_FILENAME, frame: pd.DataFrame | None = None) -> PropertyGraph:
    graph = PropertyGraph()
    compound_node = build_compound_node()
    graph.add_node(compound_node)

    bioactivity_frame = load_bioactivity_frame(filename) if frame is None else frame
    for row_index, row in bioactivity_frame.iterrows():
        assay_key = clean_text(first_non_empty(row.get("Bioactivity_ID"), row.get("BioAssay_AID"), row_index))
        assay_node = GraphNode(
            graph_id=assay_graph_id(assay_key),
            label="Assay",
            properties={
                "bioactivity_id": clean_text(row.get("Bioactivity_ID")),
                "aid": safe_int(row.get("BioAssay_AID")),
                "aid_type": clean_text(row.get("Aid_Type")),
                "activity": clean_text(row.get("Activity")),
                "activity_type": clean_text(row.get("Activity_Type")),
                "activity_value": safe_float(row.get("Activity_Value")),
                "name": clean_text(row.get("BioAssay_Name")),
                "source_file": filename,
            },
        )
        graph.add_node(assay_node)
        graph.add_edge(
            GraphEdge(
                source_id=assay_node.graph_id,
                source_label="Assay",
                target_id=compound_node.graph_id,
                target_label="Compound",
                label="ABOUT_COMPOUND",
                properties={"source_file": filename},
            )
        )

        source_name = clean_text(row.get("Bioassay_Data_Source"))
        if source_name:
            source_node = GraphNode(
                graph_id=source_graph_id(source_name),
                label="Source",
                properties={"name": source_name, "source_file": filename},
            )
            graph.add_node(source_node)
            graph.add_edge(
                GraphEdge(
                    source_id=assay_node.graph_id,
                    source_label="Assay",
                    target_id=source_node.graph_id,
                    target_label="Source",
                    label="FROM_SOURCE",
                    properties={"source_file": filename},
                )
            )

        target_key = clean_text(
            first_non_empty(row.get("Target_Name"), row.get("Protein_Accession"), row.get("Gene_ID"))
        )
        if target_key:
            target_node = GraphNode(
                graph_id=target_graph_id(target_key),
                label="Target",
                properties={
                    "name": clean_text(row.get("Target_Name")),
                    "protein_accession": clean_text(row.get("Protein_Accession")),
                    "gene_id": clean_text(row.get("Gene_ID")),
                    "source_file": filename,
                },
            )
            graph.add_node(target_node)
            graph.add_edge(
                GraphEdge(
                    source_id=assay_node.graph_id,
                    source_label="Assay",
                    target_id=target_node.graph_id,
                    target_label="Target",
                    label="TARGETS",
                    properties={"source_file": filename},
                )
            )

        taxonomy_id = safe_int(first_non_empty(row.get("Target_Taxonomy_ID"), row.get("Taxonomy_ID")))
        if taxonomy_id is not None:
            taxon_node = GraphNode(
                graph_id=taxon_graph_id(taxonomy_id),
                label="Taxon",
                properties={"taxonomy_id": taxonomy_id, "source_file": filename},
            )
            graph.add_node(taxon_node)
            graph.add_edge(
                GraphEdge(
                    source_id=assay_node.graph_id,
                    source_label="Assay",
                    target_id=taxon_node.graph_id,
                    target_label="Taxon",
                    label="TESTED_IN",
                    properties={"source_file": filename},
                )
            )

    return graph


def parse_dot_organism_graph(dot_text: str) -> dict[str, Any]:
    compound_alias = "cid4"
    current_group = "unclassified"
    group_labels: dict[str, str] = {}
    organisms: dict[str, str] = {}
    edges: list[tuple[str, str]] = []

    for raw_line in dot_text.splitlines():
        line = raw_line.strip()
        next_group = parse_dot_cluster_start(line)
        if next_group is not None:
            current_group = next_group
            continue

        if update_dot_group_label(line, current_group, group_labels):
            continue

        edge = parse_dot_edge(line)
        if edge is not None:
            edges.append(edge)
            continue

        if line.startswith("cid4 [label="):
            continue

        register_dot_organisms(line, current_group, group_labels, organisms)

    return {
        "compound_alias": compound_alias,
        "organisms": organisms,
        "edges": edges,
    }


def parse_dot_cluster_start(line: str) -> str | None:
    if not line.startswith("subgraph cluster_"):
        return None
    return line.split("cluster_", 1)[1].split()[0].strip("{")


def update_dot_group_label(line: str, current_group: str, group_labels: dict[str, str]) -> bool:
    label_match = re.match(r'label="([^"]+)"', line)
    if label_match is None or current_group == "unclassified":
        return False
    group_labels[current_group] = label_match.group(1)
    return True


def parse_dot_edge(line: str) -> tuple[str, str] | None:
    if "->" not in line:
        return None
    edge_match = re.match(r'([^\s]+)\s*->\s*"([^"]+)";', line)
    if edge_match is None:
        return None
    return (edge_match.group(1), edge_match.group(2))


def register_dot_organisms(
    line: str,
    current_group: str,
    group_labels: dict[str, str],
    organisms: dict[str, str],
) -> None:
    quoted = re.findall(r'"([^"]+)"', line)
    if not quoted:
        return
    group_name = group_labels.get(current_group, current_group.replace("_", " "))
    for organism_name in quoted:
        organisms[organism_name] = group_name


def compound_graph_id(cid: int) -> str:
    return f"compound:{cid}"


def atom_graph_id(aid: int) -> str:
    return f"atom:{aid}"


def organism_graph_id(namespace: str, name: Any) -> str:
    return f"organism:{namespace}:{slugify(name)}"


def taxon_graph_id(taxonomy_id: int) -> str:
    return f"taxon:{taxonomy_id}"


def pathway_graph_id(accession: str) -> str:
    return f"pathway:{slugify(accession)}"


def reaction_graph_id(identifier: str) -> str:
    return f"reaction:{slugify(identifier)}"


def source_graph_id(name: str) -> str:
    return f"source:{slugify(name)}"


def target_graph_id(name: str) -> str:
    return f"target:{slugify(name)}"


def assay_graph_id(identifier: str) -> str:
    return f"assay:{slugify(identifier)}"


def protein_graph_id(identifier: str) -> str:
    return f"protein:{slugify(identifier)}"


def gene_graph_id(identifier: str) -> str:
    return f"gene:{slugify(identifier)}"


def enzyme_graph_id(identifier: str) -> str:
    return f"enzyme:{slugify(identifier)}"


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and pd.isna(value):
        return ""
    return str(value).strip()


def safe_int(value: Any) -> int | None:
    text = clean_text(value)
    if text == "":
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def safe_float(value: Any) -> float | None:
    text = clean_text(value)
    if text == "":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def first_non_empty(*values: Any) -> Any:
    for value in values:
        text = clean_text(value)
        if text != "":
            return value
    return ""


def slugify(value: Any) -> str:
    text = clean_text(value).lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_") or "unknown"
