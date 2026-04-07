from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from datasets import (
    BIOACTIVITY_FILENAME,
    CPDAT_FILENAME,
    LITERATURE_FILENAME,
    PATENT_FILENAME,
    PATHWAY_FILENAME,
    PATHWAY_REACTION_FILENAME,
    TAXONOMY_FILENAME,
    load_bioactivity_frame,
    load_cpdat_frame,
    load_literature_frame,
    load_patent_frame,
    load_pathway_frame,
    load_pathway_reaction_frame,
    load_taxonomy_frame,
)


@dataclass(frozen=True)
class VectorDocument:
    doc_id: str
    doc_type: str
    source_file: str
    source_row_id: str
    title: str
    text_payload: str
    cid: int | None = None
    sid: int | None = None
    aid: int | None = None
    pmid: str | None = None
    doi: str | None = None
    taxonomy_id: int | None = None
    pathway_accession: str | None = None
    metadata: dict[str, Any] | None = None

    def to_record(self) -> dict[str, Any]:
        return {
            "doc_id": self.doc_id,
            "doc_type": self.doc_type,
            "source_file": self.source_file,
            "source_row_id": self.source_row_id,
            "title": self.title,
            "text_payload": self.text_payload,
            "cid": self.cid,
            "sid": self.sid,
            "aid": self.aid,
            "pmid": self.pmid,
            "doi": self.doi,
            "taxonomy_id": self.taxonomy_id,
            "pathway_accession": self.pathway_accession,
            "metadata": {} if self.metadata is None else dict(self.metadata),
        }


def build_all_documents() -> list[VectorDocument]:
    documents: list[VectorDocument] = []
    documents.extend(build_literature_documents())
    documents.extend(build_patent_documents())
    documents.extend(build_bioactivity_documents())
    documents.extend(build_pathway_documents())
    documents.extend(build_pathway_reaction_documents())
    documents.extend(build_taxonomy_documents())
    documents.extend(build_cpdat_documents())
    return documents


def build_literature_documents(
    frame: pd.DataFrame | None = None,
) -> list[VectorDocument]:
    literature_frame = load_literature_frame() if frame is None else frame
    documents: list[VectorDocument] = []
    for row_index, row in literature_frame.iterrows():
        row_id = first_non_empty(
            row.get("PubChem_Literature_ID_(PCLID)"),
            row.get("PMID"),
            row.get("DOI"),
            row_index,
        )
        documents.append(
            VectorDocument(
                doc_id=build_doc_id("literature", LITERATURE_FILENAME, row_id),
                doc_type="literature",
                source_file=LITERATURE_FILENAME,
                source_row_id=str(row_id),
                title=clean_text(row.get("Title")),
                text_payload=compose_text_payload(
                    row,
                    [
                        "Title",
                        "Abstract",
                        "Keywords",
                        "Citation",
                        "Subject",
                        "Publication_Name",
                    ],
                ),
                cid=safe_int(row.get("PubChem_CID")),
                pmid=clean_text(first_non_empty(row.get("PMID"), row.get("PMID_(All)")))
                or None,
                doi=clean_text(first_non_empty(row.get("DOI"), row.get("DOI_(All)")))
                or None,
                metadata={
                    "publication_type": clean_text(row.get("Publication_Type")),
                    "publication_name": clean_text(row.get("Publication_Name")),
                    "subject": clean_text(row.get("Subject")),
                    "pubchem_data_source": clean_text(row.get("PubChem_Data_Source")),
                    "publication_date": clean_text(row.get("Publication_Date")),
                },
            )
        )
    return documents


def build_patent_documents(frame: pd.DataFrame | None = None) -> list[VectorDocument]:
    patent_frame = load_patent_frame() if frame is None else frame
    documents: list[VectorDocument] = []
    for row_index, row in patent_frame.iterrows():
        row_id = first_non_empty(
            row.get("gpid"), row.get("publicationnumber"), row_index
        )
        documents.append(
            VectorDocument(
                doc_id=build_doc_id("patent", PATENT_FILENAME, row_id),
                doc_type="patent",
                source_file=PATENT_FILENAME,
                source_row_id=str(row_id),
                title=clean_text(row.get("title")),
                text_payload=compose_text_payload(
                    row, ["title", "abstract", "inventors", "assignees"]
                ),
                cid=first_int_from_pipe_list(row.get("cids")),
                metadata={
                    "publicationnumber": clean_text(row.get("publicationnumber")),
                    "prioritydate": clean_text(row.get("prioritydate")),
                    "grantdate": clean_text(row.get("grantdate")),
                    "assignees": clean_text(row.get("assignees")),
                },
            )
        )
    return documents


def build_bioactivity_documents(
    frame: pd.DataFrame | None = None,
) -> list[VectorDocument]:
    bioactivity_frame = load_bioactivity_frame() if frame is None else frame
    documents: list[VectorDocument] = []
    for row_index, row in bioactivity_frame.iterrows():
        row_id = first_non_empty(
            row.get("Bioactivity_ID"), row.get("BioAssay_AID"), row_index
        )
        documents.append(
            VectorDocument(
                doc_id=build_doc_id("bioactivity", BIOACTIVITY_FILENAME, row_id),
                doc_type="bioactivity",
                source_file=BIOACTIVITY_FILENAME,
                source_row_id=str(row_id),
                title=clean_text(row.get("BioAssay_Name")),
                text_payload=compose_text_payload(
                    row,
                    [
                        "BioAssay_Name",
                        "Target_Name",
                        "Activity_Type",
                        "Bioassay_Data_Source",
                        "citations",
                    ],
                ),
                cid=safe_int(row.get("Compound_CID")),
                sid=safe_int(row.get("Substance_SID")),
                aid=safe_int(row.get("BioAssay_AID")),
                pmid=clean_text(row.get("PMID")) or None,
                taxonomy_id=safe_int(row.get("Taxonomy_ID")),
                metadata={
                    "aid_type": clean_text(row.get("Aid_Type")),
                    "activity": clean_text(row.get("Activity")),
                    "activity_type": clean_text(row.get("Activity_Type")),
                    "target_name": clean_text(row.get("Target_Name")),
                    "bioassay_data_source": clean_text(row.get("Bioassay_Data_Source")),
                    "gene_id": clean_text(row.get("Gene_ID")),
                    "protein_accession": clean_text(row.get("Protein_Accession")),
                    "target_taxonomy_id": clean_text(row.get("Target_Taxonomy_ID")),
                },
            )
        )
    return documents


def build_pathway_documents(frame: pd.DataFrame | None = None) -> list[VectorDocument]:
    pathway_frame = load_pathway_frame() if frame is None else frame
    documents: list[VectorDocument] = []
    for row_index, row in pathway_frame.iterrows():
        row_id = first_non_empty(
            row.get("Pathway_Accession"), row.get("pathwayid"), row_index
        )
        documents.append(
            VectorDocument(
                doc_id=build_doc_id("pathway", PATHWAY_FILENAME, row_id),
                doc_type="pathway",
                source_file=PATHWAY_FILENAME,
                source_row_id=str(row_id),
                title=clean_text(row.get("Pathway_Name")),
                text_payload=compose_text_payload(
                    row,
                    [
                        "Pathway_Name",
                        "Pathway_Category",
                        "Taxonomy_Name",
                        "Data_Source",
                    ],
                ),
                cid=first_int_from_pipe_list(row.get("Linked_Compounds")),
                taxonomy_id=safe_int(row.get("Taxonomy_ID")),
                pathway_accession=clean_text(row.get("Pathway_Accession")) or None,
                metadata={
                    "pathway_type": clean_text(row.get("Pathway_Type")),
                    "pathway_category": clean_text(row.get("Pathway_Category")),
                    "taxonomy_name": clean_text(row.get("Taxonomy_Name")),
                    "data_source": clean_text(row.get("Data_Source")),
                    "source_id": clean_text(row.get("Source_ID")),
                },
            )
        )
    return documents


def build_pathway_reaction_documents(
    frame: pd.DataFrame | None = None,
) -> list[VectorDocument]:
    pathway_frame = load_pathway_reaction_frame() if frame is None else frame
    documents: list[VectorDocument] = []
    for row_index, row in pathway_frame.iterrows():
        row_id = first_non_empty(row.get("id"), row.get("Source_Pathway"), row_index)
        documents.append(
            VectorDocument(
                doc_id=build_doc_id(
                    "pathway_reaction", PATHWAY_REACTION_FILENAME, row_id
                ),
                doc_type="pathway_reaction",
                source_file=PATHWAY_REACTION_FILENAME,
                source_row_id=str(row_id),
                title=clean_text(
                    first_non_empty(row.get("Reaction"), row.get("Equation"))
                ),
                text_payload=compose_text_payload(
                    row, ["Reaction", "Equation", "Control", "Taxonomy"]
                ),
                cid=safe_int(row.get("Compound_CID")),
                taxonomy_id=safe_int(row.get("Taxonomy_ID")),
                pathway_accession=clean_text(row.get("PubChem_Pathway")) or None,
                metadata={
                    "source": clean_text(row.get("Source")),
                    "source_pathway": clean_text(row.get("Source_Pathway")),
                    "pubchem_protein": clean_text(row.get("PubChem_Protein")),
                    "pubchem_gene": clean_text(row.get("PubChem_Gene")),
                    "pubchem_enzyme": clean_text(row.get("PubChem_Enzyme")),
                },
            )
        )
    return documents


def build_taxonomy_documents(frame: pd.DataFrame | None = None) -> list[VectorDocument]:
    taxonomy_frame = load_taxonomy_frame() if frame is None else frame
    documents: list[VectorDocument] = []
    for row_index, row in taxonomy_frame.iterrows():
        row_id = first_non_empty(
            row.get("Source_Organism_ID"), row.get("Taxonomy_ID"), row_index
        )
        documents.append(
            VectorDocument(
                doc_id=build_doc_id("taxonomy", TAXONOMY_FILENAME, row_id),
                doc_type="taxonomy",
                source_file=TAXONOMY_FILENAME,
                source_row_id=str(row_id),
                title=clean_text(row.get("Source_Organism")),
                text_payload=compose_text_payload(
                    row,
                    ["Source_Organism", "Taxonomy", "Source", "Evidence", "Compound"],
                ),
                cid=safe_int(row.get("Compound_CID")),
                taxonomy_id=safe_int(row.get("Taxonomy_ID")),
                metadata={
                    "data_source": clean_text(row.get("Data_Source")),
                    "source": clean_text(row.get("Source")),
                    "source_kind": clean_text(row.get("Source_Kind")),
                    "source_organism_id": clean_text(row.get("Source_Organism_ID")),
                    "references": clean_text(row.get("References")),
                },
            )
        )
    return documents


def build_cpdat_documents(frame: pd.DataFrame | None = None) -> list[VectorDocument]:
    cpdat_frame = load_cpdat_frame() if frame is None else frame
    documents: list[VectorDocument] = []
    for row_index, row in cpdat_frame.iterrows():
        row_id = first_non_empty(row.get("gid"), row.get("CID"), row_index)
        documents.append(
            VectorDocument(
                doc_id=build_doc_id("cpdat", CPDAT_FILENAME, row_id),
                doc_type="cpdat",
                source_file=CPDAT_FILENAME,
                source_row_id=str(row_id),
                title=clean_text(row.get("Category")),
                text_payload=compose_text_payload(
                    row, ["Category", "Category_Description", "cmpdname"]
                ),
                cid=safe_int(row.get("CID")),
                metadata={
                    "categorization_type": clean_text(row.get("Categorization_Type")),
                    "cmpdname": clean_text(row.get("cmpdname")),
                },
            )
        )
    return documents


def build_doc_id(doc_type: str, source_file: str, source_row_id: Any) -> str:
    return f"{doc_type}:{source_file}:{clean_text(source_row_id)}"


def compose_text_payload(row: pd.Series, fields: list[str]) -> str:
    values = [clean_text(row.get(field)) for field in fields]
    return "\n".join(value for value in values if value)


def clean_text(value: Any) -> str:
    if value is None or pd.isna(value):
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


def first_int_from_pipe_list(value: Any) -> int | None:
    text = clean_text(value)
    if text == "":
        return None
    first = text.split("|")[0]
    return safe_int(first)


def first_non_empty(*values: Any) -> Any:
    for value in values:
        text = clean_text(value)
        if text != "":
            return value
    return values[-1] if values else ""
