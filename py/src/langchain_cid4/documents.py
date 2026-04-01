from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pgvector.documents import (
    VectorDocument,
    build_bioactivity_documents,
    build_cpdat_documents,
    build_literature_documents,
    build_patent_documents,
    build_pathway_documents,
    build_pathway_reaction_documents,
    build_taxonomy_documents,
)


@dataclass(frozen=True)
class ChunkRecord:
    chunk_id: str
    doc_id: str
    doc_type: str
    source_file: str
    source_row_id: str
    title: str
    content: str
    metadata: dict[str, Any]


def import_langchain_stack() -> dict[str, Any]:
    try:
        from langchain_core.documents import Document
        from langchain_core.prompts import PromptTemplate
        from langchain_core.runnables import RunnableLambda
        from langchain_text_splitters import RecursiveCharacterTextSplitter

        return {
            "available": True,
            "Document": Document,
            "PromptTemplate": PromptTemplate,
            "RunnableLambda": RunnableLambda,
            "RecursiveCharacterTextSplitter": RecursiveCharacterTextSplitter,
        }
    except (ImportError, ModuleNotFoundError) as exc:
        return {
            "available": False,
            "reason": f"LangChain dependencies are not installed in the current environment: {exc}",
        }


def load_domain_documents(domain: str) -> list[VectorDocument]:
    if domain == "literature":
        return build_literature_documents()
    if domain == "patent":
        return build_patent_documents()
    if domain == "assay":
        return build_bioactivity_documents()
    if domain == "pathway":
        return build_pathway_documents() + build_pathway_reaction_documents()
    if domain == "taxonomy":
        return build_taxonomy_documents()
    if domain == "product_use":
        return build_cpdat_documents()
    raise ValueError(f"Unsupported domain: {domain}")


def chunk_documents(
    documents: list[VectorDocument],
    *,
    chunk_size: int = 700,
    chunk_overlap: int = 120,
) -> list[ChunkRecord]:
    stack = import_langchain_stack()
    if stack["available"]:
        splitter = stack["RecursiveCharacterTextSplitter"](
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", ". ", " ", ""],
        )
        chunks: list[ChunkRecord] = []
        for document in documents:
            metadata = {
                "doc_id": document.doc_id,
                "doc_type": document.doc_type,
                "source_file": document.source_file,
                "source_row_id": document.source_row_id,
                "title": document.title,
                **({} if document.metadata is None else dict(document.metadata)),
            }
            for index, content in enumerate(splitter.split_text(document.text_payload), start=1):
                chunks.append(
                    ChunkRecord(
                        chunk_id=f"{document.doc_id}:chunk:{index}",
                        doc_id=document.doc_id,
                        doc_type=document.doc_type,
                        source_file=document.source_file,
                        source_row_id=document.source_row_id,
                        title=document.title,
                        content=content,
                        metadata={**metadata, "chunk_index": index},
                    )
                )
        return chunks

    chunks = []
    for document in documents:
        for index, content in enumerate(
            _fallback_split_text(document.text_payload, chunk_size, chunk_overlap), start=1
        ):
            chunks.append(
                ChunkRecord(
                    chunk_id=f"{document.doc_id}:chunk:{index}",
                    doc_id=document.doc_id,
                    doc_type=document.doc_type,
                    source_file=document.source_file,
                    source_row_id=document.source_row_id,
                    title=document.title,
                    content=content,
                    metadata={
                        "doc_id": document.doc_id,
                        "doc_type": document.doc_type,
                        "source_file": document.source_file,
                        "source_row_id": document.source_row_id,
                        "title": document.title,
                        "chunk_index": index,
                        **({} if document.metadata is None else dict(document.metadata)),
                    },
                )
            )
    return chunks


def build_langchain_documents(documents: list[VectorDocument]) -> list[Any]:
    stack = import_langchain_stack()
    if not stack["available"]:
        return []

    langchain_documents = []
    for document in documents:
        langchain_documents.append(
            stack["Document"](
                page_content=document.text_payload,
                metadata={
                    "doc_id": document.doc_id,
                    "doc_type": document.doc_type,
                    "source_file": document.source_file,
                    "source_row_id": document.source_row_id,
                    "title": document.title,
                    "chunk_index": 0,
                    **({} if document.metadata is None else dict(document.metadata)),
                },
            )
        )
    return langchain_documents


def _fallback_split_text(text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    cleaned = " ".join(text.split())
    if not cleaned:
        return []

    step = max(1, chunk_size - chunk_overlap)
    chunks: list[str] = []
    start = 0
    while start < len(cleaned):
        chunk = cleaned[start : start + chunk_size].strip()
        if chunk:
            chunks.append(chunk)
        if start + chunk_size >= len(cleaned):
            break
        start += step
    return chunks
