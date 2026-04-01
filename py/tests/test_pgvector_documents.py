from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from pgvector.documents import (  # noqa: E402
    build_bioactivity_documents,
    build_cpdat_documents,
    build_literature_documents,
)
from pgvector.embedding import HashedTokenEmbeddingProvider  # noqa: E402


class PgvectorDocumentTests(unittest.TestCase):
    def test_literature_document_shape(self) -> None:
        frame = pd.DataFrame(
            [
                {
                    "PubChem_Literature_ID_(PCLID)": 39023451,
                    "PMID": "40581877",
                    "DOI": "10.1000/example",
                    "Title": "CID 4 literature example",
                    "Abstract": "Isopropanolamine metabolism pathway summary",
                    "Keywords": "isopropanolamine, pathway",
                    "Citation": "PMID 40581877",
                    "Subject": "Chemistry",
                    "Publication_Name": "Journal",
                    "PubChem_CID": 4,
                    "Publication_Type": "Journal Article",
                    "PubChem_Data_Source": "PubChem",
                    "Publication_Date": "2025-01-01",
                }
            ]
        )

        documents = build_literature_documents(frame)

        self.assertEqual(len(documents), 1)
        self.assertEqual(documents[0].doc_type, "literature")
        self.assertEqual(documents[0].cid, 4)
        self.assertIn("Isopropanolamine metabolism pathway summary", documents[0].text_payload)

    def test_bioactivity_document_captures_structured_filters(self) -> None:
        frame = pd.DataFrame(
            [
                {
                    "Bioactivity_ID": 123,
                    "BioAssay_AID": 743069,
                    "Compound_CID": 4,
                    "Substance_SID": 144212021,
                    "Taxonomy_ID": 9606,
                    "PMID": "12345678",
                    "BioAssay_Name": "Estrogen receptor antagonism assay",
                    "Target_Name": "ESR1",
                    "Activity_Type": "Potency",
                    "Bioassay_Data_Source": "Tox21",
                    "citations": "PMID 12345678",
                    "Aid_Type": "Confirmatory",
                    "Activity": "Active",
                    "Gene_ID": "2099",
                    "Protein_Accession": "P03372",
                    "Target_Taxonomy_ID": "9606",
                }
            ]
        )

        documents = build_bioactivity_documents(frame)

        self.assertEqual(len(documents), 1)
        self.assertEqual(documents[0].aid, 743069)
        self.assertEqual(documents[0].taxonomy_id, 9606)
        self.assertEqual(documents[0].metadata["aid_type"], "Confirmatory")

    def test_cpdat_document_shape(self) -> None:
        frame = pd.DataFrame(
            [
                {
                    "gid": 11,
                    "CID": 4,
                    "Category": "general arts and crafts cleaner",
                    "Category_Description": "Solvent-based cleaner",
                    "Categorization_Type": "Product Use Category (PUC)",
                    "cmpdname": "1-Aminopropan-2-ol",
                }
            ]
        )

        documents = build_cpdat_documents(frame)

        self.assertEqual(len(documents), 1)
        self.assertEqual(documents[0].doc_type, "cpdat")
        self.assertIn("Solvent-based cleaner", documents[0].text_payload)

    def test_hashed_embedding_provider_returns_stable_dimension(self) -> None:
        provider = HashedTokenEmbeddingProvider(dimension=16)

        embedding = provider.embed("isopropanolamine glutathione pathway assay")

        self.assertEqual(len(embedding), 16)
        self.assertGreater(sum(abs(value) for value in embedding), 0.0)


if __name__ == "__main__":
    unittest.main()
