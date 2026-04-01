from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from langchain_cid4.documents import ChunkRecord, chunk_documents  # noqa: E402
from langchain_cid4.retrieval import InMemoryRetriever  # noqa: E402
from langchain_cid4.workflows import build_grounded_answer, route_question, summarize_hits  # noqa: E402
from pgvector.documents import VectorDocument  # noqa: E402


class LangchainWorkflowTests(unittest.TestCase):
    def test_route_question_detects_multi_source_queries(self) -> None:
        route = route_question("Find literature and assays related to Plasmodium falciparum")

        self.assertIn("literature", route["domains"])
        self.assertIn("assay", route["domains"])

    def test_chunk_documents_preserves_identity_metadata(self) -> None:
        documents = [
            VectorDocument(
                doc_id="literature:test:1",
                doc_type="literature",
                source_file="pubchem_cid_4_literature.csv",
                source_row_id="1",
                title="CID 4 literature example",
                text_payload=" ".join(["isopropanolamine pathway summary"] * 80),
                metadata={"pmid": "40581877"},
            )
        ]

        chunks = chunk_documents(documents, chunk_size=120, chunk_overlap=20)

        self.assertGreaterEqual(len(chunks), 2)
        self.assertEqual(chunks[0].metadata["doc_id"], "literature:test:1")
        self.assertEqual(chunks[0].doc_type, "literature")

    def test_in_memory_retriever_prefers_matching_chunk(self) -> None:
        chunks = [
            ChunkRecord(
                chunk_id="literature:1:chunk:1",
                doc_id="literature:1",
                doc_type="literature",
                source_file="pubchem_cid_4_literature.csv",
                source_row_id="1",
                title="Glutathione metabolism",
                content="Glutathione metabolism and amino alcohol pathway evidence.",
                metadata={"doc_id": "literature:1"},
            ),
            ChunkRecord(
                chunk_id="literature:2:chunk:1",
                doc_id="literature:2",
                doc_type="literature",
                source_file="pubchem_cid_4_literature.csv",
                source_row_id="2",
                title="Unrelated patent wording",
                content="Electronic grade purification device and assignee workflow.",
                metadata={"doc_id": "literature:2"},
            ),
        ]

        retriever = InMemoryRetriever(chunks)
        hits = retriever.retrieve("glutathione pathway", top_k=1)

        self.assertEqual(hits[0].title, "Glutathione metabolism")

    def test_grounded_answer_and_structured_output_include_top_hit(self) -> None:
        from langchain_cid4.retrieval import RetrievedPassage  # noqa: E402

        hits = [
            RetrievedPassage(
                source_id="bioactivity:1",
                doc_type="bioactivity",
                title="Estrogen receptor assay",
                content="Estrogen receptor antagonism assay from Tox21.",
                metadata={"BioAssay_AID": 743069, "Taxonomy_ID": 9606},
                score=0.93,
                backend="in_memory",
            )
        ]

        summary = summarize_hits(["assay"], hits)
        answer = build_grounded_answer(["assay"], hits)

        self.assertEqual(summary["supporting_records"][0]["title"], "Estrogen receptor assay")
        self.assertIn("Estrogen receptor assay", answer)


if __name__ == "__main__":
    unittest.main()
