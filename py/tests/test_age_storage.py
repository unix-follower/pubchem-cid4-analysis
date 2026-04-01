from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from age_cid4.graphs import GraphEdge, GraphNode, PropertyGraph  # noqa: E402
from age_cid4.storage import (  # noqa: E402
    AgeConfig,
    build_edge_merge_cypher,
    build_node_merge_cypher,
    ingest_graph,
)


class AgeStorageTests(unittest.TestCase):
    def test_build_node_merge_cypher_includes_graph_id_and_properties(self) -> None:
        query = build_node_merge_cypher(
            GraphNode(graph_id="compound:4", label="Compound", properties={"cid": 4, "name": "1-Amino-2-propanol"})
        )

        self.assertIn("MERGE (n:Compound", query)
        self.assertIn('graph_id: "compound:4"', query)
        self.assertIn('name: "1-Amino-2-propanol"', query)

    def test_build_edge_merge_cypher_matches_labeled_nodes(self) -> None:
        query = build_edge_merge_cypher(
            GraphEdge(
                source_id="compound:4",
                source_label="Compound",
                target_id="atom:1",
                target_label="Atom",
                label="HAS_ATOM",
                properties={"source_file": "Conformer3D_COMPOUND_CID_4(1).json"},
            )
        )

        self.assertIn("MATCH (a:Compound", query)
        self.assertIn("MERGE (a)-[r:HAS_ATOM]->(b)", query)

    def test_ingest_graph_dry_runs_without_dsn(self) -> None:
        graph = PropertyGraph()
        graph.add_node(GraphNode(graph_id="compound:4", label="Compound", properties={"cid": 4}))
        graph.add_node(GraphNode(graph_id="atom:1", label="Atom", properties={"aid": 1, "element": "O"}))
        graph.add_edge(
            GraphEdge(
                source_id="compound:4",
                source_label="Compound",
                target_id="atom:1",
                target_label="Atom",
                label="HAS_ATOM",
            )
        )

        result = ingest_graph(graph, AgeConfig(dsn=None, graph_name="cid4_graph"))

        self.assertEqual(result["status"], "dry_run")
        self.assertEqual(result["node_count"], 2)
        self.assertEqual(result["edge_count"], 1)
        self.assertTrue(result["sample_statements"])


if __name__ == "__main__":
    unittest.main()
