from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from age_cid4.graphs import (  # noqa: E402
    build_assay_graph,
    build_molecular_graph,
    build_organism_graph,
    build_pathway_reaction_graph,
    build_unified_graph,
    parse_dot_organism_graph,
)
from age_cid4.queries import build_query_catalog  # noqa: E402


class AgeGraphTests(unittest.TestCase):
    def test_molecular_graph_contains_expected_atom_and_bond_counts(self) -> None:
        graph = build_molecular_graph()
        summary = graph.to_summary()

        self.assertEqual(summary["node_label_counts"]["Atom"], 14)
        self.assertEqual(summary["edge_label_counts"]["BOND"], 13)
        self.assertEqual(summary["edge_label_counts"]["HAS_ATOM"], 14)

    def test_dot_parser_captures_organism_groups_and_edges(self) -> None:
        parsed = parse_dot_organism_graph(
            'digraph CID_4 {\nsubgraph cluster_mammals {\nlabel="Mammals";\n"Bison";\n}\ncid4 -> "Bison";\n}'
        )

        self.assertEqual(parsed["organisms"]["Bison"], "Mammals")
        self.assertEqual(parsed["edges"], [("cid4", "Bison")])

    def test_organism_graph_contains_taxon_and_source_nodes(self) -> None:
        graph = build_organism_graph()
        summary = graph.to_summary()

        self.assertIn("Organism", summary["node_label_counts"])
        self.assertIn("Taxon", summary["node_label_counts"])
        self.assertIn("FOUND_IN", summary["edge_label_counts"])

    def test_pathway_and_assay_graphs_add_expected_labels(self) -> None:
        pathway_graph = build_pathway_reaction_graph()
        assay_graph = build_assay_graph()

        self.assertIn("Pathway", pathway_graph.to_summary()["node_label_counts"])
        self.assertIn("Reaction", pathway_graph.to_summary()["node_label_counts"])
        self.assertIn("Assay", assay_graph.to_summary()["node_label_counts"])
        self.assertIn("Target", assay_graph.to_summary()["node_label_counts"])

    def test_unified_graph_and_query_catalog_cover_multi_hop_use_cases(self) -> None:
        graph = build_unified_graph()
        queries = build_query_catalog()

        self.assertGreater(graph.to_summary()["node_count"], 14)
        self.assertTrue(any(query["id"] == "compound_assay_target_taxon" for query in queries))
        self.assertTrue(any("shortestPath" in query["cypher"] for query in queries))


if __name__ == "__main__":
    unittest.main()
