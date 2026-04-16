from __future__ import annotations

from typing import Any

from langchain_cid4.documents import (
    chunk_documents,
    import_langchain_stack,
    load_domain_documents,
)
from langchain_cid4.retrieval import (
    InMemoryRetriever,
    RetrievedPassage,
    retrieve_with_pgvector,
)


def route_question(question: str) -> dict[str, Any]:
    normalized = question.lower()
    domains: list[str] = []
    reasons: list[str] = []

    keyword_map = {
        "literature": ["literature", "paper", "abstract", "doi", "pmid", "citation"],
        "patent": ["patent", "inventor", "assignee", "publication number"],
        "assay": [
            "assay",
            "target",
            "activity",
            "aid",
            "tox21",
            "estrogen",
            "androgen",
        ],
        "pathway": [
            "pathway",
            "reaction",
            "enzyme",
            "gene",
            "nadh",
            "glutathione",
            "trypanosoma",
        ],
        "taxonomy": ["taxonomy", "organism", "species", "bird", "mammal", "fooddb"],
        "product_use": ["product", "use", "cpdat", "category", "consumer"],
    }

    for domain, keywords in keyword_map.items():
        matched = [keyword for keyword in keywords if keyword in normalized]
        if matched:
            domains.append(domain)
            reasons.append(f"{domain}: {', '.join(matched[:3])}")

    if not domains:
        domains = ["literature"]
        reasons = ["default literature route for open-ended CID 4 questions"]

    ordered_domains = []
    for domain in domains:
        if domain not in ordered_domains:
            ordered_domains.append(domain)

    return {
        "domains": ordered_domains,
        "primary_domain": ordered_domains[0],
        "reason": "; ".join(reasons),
    }


def run_literature_workflow() -> dict[str, Any]:
    question = "What does the literature say about isopropanolamine fungicide activity?"
    return run_question_workflow(
        question, domains=["literature"], workflow="literature-rag"
    )


def run_assay_workflow() -> dict[str, Any]:
    question = "Which CID 4 assays involve estrogen receptor signaling?"
    return run_question_workflow(question, domains=["assay"], workflow="assay-qa")


def run_pathway_workflow() -> dict[str, Any]:
    question = "Which pathways involving CID 4 are linked to Trypanosoma brucei?"
    return run_question_workflow(
        question, domains=["pathway"], workflow="pathway-explainer"
    )


def run_taxonomy_workflow() -> dict[str, Any]:
    question = "Which organisms in the dataset are birds?"
    return run_question_workflow(
        question, domains=["taxonomy"], workflow="taxonomy-assistant"
    )


def run_agent_workflow() -> dict[str, Any]:
    sample_questions = [
        "Find literature and assays related to Plasmodium falciparum",
        "Summarize pathway evidence for CID 4 in Trypanosoma brucei",
        "List likely product-use categories and supporting descriptions",
    ]
    outputs = []
    for question in sample_questions:
        route = route_question(question)
        outputs.append(
            run_question_workflow(
                question,
                domains=route["domains"],
                workflow="multi-tool-agent",
                route=route,
                top_k=2,
            )
        )

    stack = import_langchain_stack()
    return {
        "status": "ok",
        "workflow": "multi-tool-agent",
        "langchain_runtime": build_langchain_runtime(stack),
        "question_count": len(outputs),
        "questions": outputs,
    }


def run_question_workflow(
    question: str,
    *,
    domains: list[str] | None = None,
    workflow: str,
    route: dict[str, Any] | None = None,
    top_k: int = 4,
) -> dict[str, Any]:
    effective_route = route or route_question(question)
    effective_domains = effective_route["domains"] if domains is None else domains
    stack = import_langchain_stack()

    domain_results = [
        retrieve_domain_hits(question, domain, top_k=top_k)
        for domain in effective_domains
    ]
    flattened_hits = [hit for result in domain_results for hit in result["_hits"]]
    flattened_hits = sorted(
        flattened_hits, key=lambda item: (-item.score, item.title, item.source_id)
    )[:top_k]
    public_domain_results = [
        {key: value for key, value in result.items() if key != "_hits"}
        for result in domain_results
    ]

    response = build_chain_response(question, effective_domains, flattened_hits, stack)

    return {
        "status": "ok",
        "workflow": workflow,
        "question": question,
        "route": effective_route,
        "langchain_runtime": build_langchain_runtime(stack),
        "retrieval": public_domain_results,
        "answer": response["answer"],
        "structured_output": response["structured_output"],
        "context_preview": response["context_preview"],
    }


def retrieve_domain_hits(
    question: str, domain: str, *, top_k: int = 4
) -> dict[str, Any]:
    documents = load_domain_documents(domain)
    chunks = chunk_documents(documents)

    pgvector_result = retrieve_with_pgvector(
        question, doc_type=map_domain_to_doc_type(domain), top_k=top_k
    )
    if pgvector_result.get("status") == "ok":
        hits = pgvector_result["hits"]
        backend = "pgvector"
        reason = None
    else:
        retriever = InMemoryRetriever(chunks)
        hits = retriever.retrieve(question, top_k=top_k)
        backend = "in_memory"
        reason = pgvector_result.get("reason")

    return {
        "domain": domain,
        "doc_count": len(documents),
        "chunk_count": len(chunks),
        "backend": backend,
        "fallback_reason": reason,
        "hits": [serialize_hit(hit) for hit in hits],
        "_hits": hits,
    }


def build_chain_response(
    question: str,
    domains: list[str],
    hits: list[RetrievedPassage],
    stack: dict[str, Any],
) -> dict[str, Any]:
    context_preview = format_hits_for_prompt(hits)
    structured_output = summarize_hits(domains, hits)

    if stack["available"]:
        prompt = stack["PromptTemplate"].from_template(
            "Question: {question}\nDomains: {domains}\nContext:\n{context}\n"
            "Return a grounded CID 4 answer that stays within the supplied evidence."
        )
        chain = prompt | stack["RunnableLambda"](
            lambda rendered_prompt: {
                "answer": build_grounded_answer(domains, hits),
                "prompt_preview": str(rendered_prompt),
            }
        )
        result = chain.invoke(
            {
                "question": question,
                "domains": ", ".join(domains),
                "context": context_preview,
            }
        )
        return {
            "answer": result["answer"],
            "structured_output": structured_output,
            "context_preview": context_preview,
        }

    return {
        "answer": build_grounded_answer(domains, hits),
        "structured_output": structured_output,
        "context_preview": context_preview,
    }


def summarize_hits(domains: list[str], hits: list[RetrievedPassage]) -> dict[str, Any]:
    if not hits:
        return {
            "domains": domains,
            "hit_count": 0,
            "supporting_records": [],
        }

    supporting_records = []
    for hit in hits[:4]:
        supporting_records.append(
            {
                "doc_type": hit.doc_type,
                "title": hit.title,
                "score": round(hit.score, 4),
                "pmid": hit.metadata.get("pmid") or hit.metadata.get("PMID"),
                "doi": hit.metadata.get("doi") or hit.metadata.get("DOI"),
                "aid": hit.metadata.get("aid") or hit.metadata.get("BioAssay_AID"),
                "taxonomy_id": hit.metadata.get("taxonomy_id")
                or hit.metadata.get("Taxonomy_ID"),
                "pathway_accession": hit.metadata.get("pathway_accession")
                or hit.metadata.get("Pathway_Accession"),
            }
        )

    return {
        "domains": domains,
        "hit_count": len(hits),
        "supporting_records": supporting_records,
    }


def build_grounded_answer(domains: list[str], hits: list[RetrievedPassage]) -> str:
    if not hits:
        return "No grounded CID 4 evidence was retrieved for the requested domains."

    top_titles = "; ".join(hit.title for hit in hits[:3] if hit.title)
    domain_phrase = ", ".join(domains)
    if "assay" in domains:
        aid_values = [
            str(hit.metadata.get("aid") or hit.metadata.get("BioAssay_AID"))
            for hit in hits[:3]
            if hit.metadata
        ]
        return (
            f"The strongest {domain_phrase} evidence centers on {top_titles}. Relevant assay identifiers include "
            f"{
                ', '.join(value for value in aid_values if value and value != 'None')
                or 'no explicit AIDs in the top hits'
            }."
        )
    if "pathway" in domains:
        accessions = [
            str(
                hit.metadata.get("pathway_accession")
                or hit.metadata.get("Source_Pathway")
            )
            for hit in hits[:3]
            if hit.metadata
        ]
        return (
            f"The grounded {domain_phrase} evidence points to {top_titles}. Pathway references in the top hits "
            f"include {
                ', '.join(value for value in accessions if value and value != 'None')
                or 'no explicit accession in the top hits'
            }."
        )
    if "taxonomy" in domains:
        tax_ids = [
            str(hit.metadata.get("taxonomy_id") or hit.metadata.get("Taxonomy_ID"))
            for hit in hits[:3]
            if hit.metadata
        ]
        return (
            f"The grounded {domain_phrase} evidence highlights {top_titles}. The leading supporting taxonomy "
            f"identifiers are {
                ', '.join(value for value in tax_ids if value and value != 'None')
                or 'not present in the top hits'
            }."
        )
    return (
        f"The grounded {domain_phrase} evidence is led by {top_titles}. "
        "These results stay scoped to CID 4 and the retrieved source rows."
    )


def format_hits_for_prompt(hits: list[RetrievedPassage]) -> str:
    if not hits:
        return "No retrieved context."
    lines = []
    for index, hit in enumerate(hits[:4], start=1):
        lines.append(
            f"[{index}] ({hit.doc_type}, {hit.backend}, score={hit.score:.4f}) {hit.title}"
            f"\n{truncate_text(hit.content, 280)}"
        )
    return "\n\n".join(lines)


def truncate_text(text: str, limit: int) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return f"{compact[: limit - 3].rstrip()}..."


def build_langchain_runtime(stack: dict[str, Any]) -> dict[str, Any]:
    if stack["available"]:
        return {
            "available": True,
            "mode": "langchain-core",
        }
    return {
        "available": False,
        "mode": "fallback",
        "reason": stack["reason"],
    }


def map_domain_to_doc_type(domain: str) -> str:
    if domain == "assay":
        return "bioactivity"
    if domain == "product_use":
        return "cpdat"
    return domain


def serialize_hit(hit: RetrievedPassage) -> dict[str, Any]:
    return {
        "source_id": hit.source_id,
        "doc_type": hit.doc_type,
        "title": hit.title,
        "score": round(hit.score, 4),
        "backend": hit.backend,
        "metadata": dict(hit.metadata),
        "content_preview": truncate_text(hit.content, 220),
    }
