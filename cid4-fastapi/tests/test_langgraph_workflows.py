from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from langgraph_cid4.workflows import (  # noqa: E402
    collect_supporting_ids,
    load_compound_context,
    run_assay_literature_workflow,
    run_pathway_taxonomy_workflow,
    run_router_question,
)


class LangGraphWorkflowTests(unittest.TestCase):
    def test_compound_context_includes_record_title(self) -> None:
        context = load_compound_context()

        self.assertEqual(context["cid"], 4)
        self.assertEqual(context["title"], "1-Amino-2-propanol")
        self.assertTrue(context["summary"])

    def test_collect_supporting_ids_reads_multiple_identifier_families(self) -> None:
        hits = [
            {
                "metadata": {
                    "BioAssay_AID": 743069,
                    "PMID": "40581877",
                    "DOI": "10.1000/example",
                    "Taxonomy_ID": 5833,
                    "Pathway_Accession": "SMP0002032",
                    "source_file": "pubchem_cid_4_bioactivity.csv",
                }
            }
        ]

        ids = collect_supporting_ids(hits)

        self.assertIn("743069", ids["aid"])
        self.assertIn("40581877", ids["pmid"])
        self.assertIn("10.1000/example", ids["doi"])
        self.assertIn("5833", ids["taxonomy_id"])
        self.assertIn("SMP0002032", ids["pathway_accession"])

    def test_router_question_routes_product_use_queries(self) -> None:
        output = run_router_question("List likely product-use categories for CID 4")

        self.assertIn("product_use", output["route"]["domains"])
        self.assertTrue(output["validation"]["passed"])

    def test_assay_literature_workflow_collects_both_evidence_families(self) -> None:
        output = run_assay_literature_workflow()

        self.assertTrue(output["validation"]["passed"])
        self.assertTrue(output["assay_hits"])
        self.assertTrue(output["literature_hits"])
        self.assertTrue(output["supporting_ids"]["aid"])
        self.assertTrue(
            output["supporting_ids"]["pmid"] or output["supporting_ids"]["doi"]
        )

    def test_pathway_taxonomy_workflow_collects_accessions_and_taxonomy(self) -> None:
        output = run_pathway_taxonomy_workflow()

        self.assertTrue(output["validation"]["passed"])
        self.assertTrue(output["pathway_hits"])
        self.assertTrue(output["taxonomy_hits"])
        self.assertTrue(output["supporting_ids"]["pathway_accession"])
        self.assertTrue(output["supporting_ids"]["taxonomy_id"])


if __name__ == "__main__":
    unittest.main()
