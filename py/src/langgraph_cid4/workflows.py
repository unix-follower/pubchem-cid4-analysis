from __future__ import annotations

import json
from collections.abc import Callable
from functools import lru_cache
from importlib import import_module
from typing import Any

import cid4_analysis
from langchain_cid4.workflows import retrieve_domain_hits, route_question
from langgraph_cid4.state import (
    GraphState,
    append_trace,
    build_initial_state,
    empty_supporting_ids,
    merge_supporting_ids,
)


def import_langgraph_stack() -> dict[str, Any]:
    try:
        graph_module = import_module("langgraph.graph")

        return {
            "available": True,
            "StateGraph": graph_module.StateGraph,
            "START": graph_module.START,
            "END": graph_module.END,
        }
    except (ImportError, ModuleNotFoundError) as exc:
        return {
            "available": False,
            "reason": f"LangGraph dependencies are not installed in the current environment: {exc}",
        }


def run_router_workflow() -> dict[str, Any]:
    questions = [
        "Find literature about isopropanolamine and fungicide activity",
        "Which CID 4 assays involve estrogen receptor signaling?",
        "What pathway evidence links CID 4 to Trypanosoma brucei?",
        "Which organisms in the dataset are birds?",
        "List likely product-use categories for CID 4",
    ]
    question_outputs = [run_router_question(question) for question in questions]
    runtime = (
        question_outputs[0]["langgraph_runtime"]
        if question_outputs
        else build_langgraph_runtime(import_langgraph_stack())
    )
    return {
        "status": "ok",
        "workflow": "router-graph",
        "langgraph_runtime": runtime,
        "question_count": len(question_outputs),
        "questions": question_outputs,
    }


def run_router_question(question: str) -> dict[str, Any]:
    state = execute_graph(
        build_initial_state(question, "router-graph", question_type="router"),
        [
            ("compound_context", compound_context_node),
            ("router", router_node),
            ("routed_retrieval", routed_retrieval_node),
            ("draft_answer", generic_synthesis_node),
            ("validator", generic_validation_node),
        ],
    )
    return finalize_state(state)


def run_assay_literature_workflow() -> dict[str, Any]:
    question = "Find assays related to Plasmodium falciparum and summarize supporting literature"
    state = execute_graph(
        build_initial_state(question, "assay-plus-literature", question_type="assay_plus_literature"),
        [
            ("compound_context", compound_context_node),
            ("router", router_node),
            ("assay_retrieval", assay_retrieval_node),
            ("literature_followup", literature_followup_node),
            ("draft_answer", assay_literature_synthesis_node),
            ("validator", assay_literature_validation_node),
        ],
    )
    return finalize_state(state)


def run_pathway_taxonomy_workflow() -> dict[str, Any]:
    question = "What pathway evidence links CID 4 to Trypanosoma brucei?"
    state = execute_graph(
        build_initial_state(question, "pathway-plus-taxonomy", question_type="pathway_plus_taxonomy"),
        [
            ("compound_context", compound_context_node),
            ("router", router_node),
            ("pathway_retrieval", pathway_retrieval_node),
            ("taxonomy_followup", taxonomy_followup_node),
            ("draft_answer", pathway_taxonomy_synthesis_node),
            ("validator", pathway_taxonomy_validation_node),
        ],
    )
    return finalize_state(state)


def run_compound_context_workflow() -> dict[str, Any]:
    question = "List likely product-use categories for CID 4 while keeping the answer grounded in the compound record"
    state = execute_graph(
        build_initial_state(question, "compound-context-assistant", question_type="compound_context"),
        [
            ("compound_context", compound_context_node),
            ("router", router_node),
            ("routed_retrieval", routed_retrieval_node),
            ("draft_answer", compound_context_synthesis_node),
            ("validator", generic_validation_node),
        ],
    )
    return finalize_state(state)


def execute_graph(
    initial_state: GraphState,
    steps: list[tuple[str, Callable[[GraphState], dict[str, Any]]]],
) -> GraphState:
    stack = import_langgraph_stack()
    runtime = build_langgraph_runtime(stack)

    if stack["available"]:
        builder = stack["StateGraph"](GraphState)
        previous = stack["START"]
        for name, node in steps:
            builder.add_node(name, node)
            builder.add_edge(previous, name)
            previous = name
        builder.add_edge(previous, stack["END"])
        state = dict(builder.compile().invoke(initial_state))
    else:
        state = dict(initial_state)
        for _, node in steps:
            state.update(node(state))

    state["langgraph_runtime"] = runtime
    return state


def build_langgraph_runtime(stack: dict[str, Any]) -> dict[str, Any]:
    if stack["available"]:
        return {
            "available": True,
            "mode": "langgraph",
        }
    return {
        "available": False,
        "mode": "fallback",
        "reason": stack["reason"],
    }


def compound_context_node(state: GraphState) -> dict[str, Any]:
    context = load_compound_context()
    return {
        "compound_context": context,
        "trace": append_trace(
            state,
            f"compound_context loaded {context['title']} (CID {context['cid']})",
        ),
    }


def router_node(state: GraphState) -> dict[str, Any]:
    route = route_question(state["question"])
    return {
        "route": route,
        "domains": list(route["domains"]),
        "question_type": state.get("question_type") or str(route["primary_domain"]),
        "trace": append_trace(state, f"router selected domains: {', '.join(route['domains'])}"),
    }


def routed_retrieval_node(state: GraphState) -> dict[str, Any]:
    updates: dict[str, Any] = {
        "retrieved_rows": list(state.get("retrieved_rows", [])),
        "supporting_ids": dict(state.get("supporting_ids", empty_supporting_ids())),
        "trace": list(state.get("trace", [])),
    }
    for domain in state.get("domains", []):
        result = retrieve_domain_hits(state["question"], domain, top_k=3)
        hits = list(result["hits"])
        updates[get_hits_key(domain)] = hits
        updates["retrieved_rows"].extend(flatten_hits(domain, hits))
        updates["supporting_ids"] = merge_supporting_ids(updates["supporting_ids"], collect_supporting_ids(hits))
        updates["trace"].append(f"retrieved {len(hits)} {domain} hits via {result['backend']}")
    return updates


def assay_retrieval_node(state: GraphState) -> dict[str, Any]:
    result = retrieve_domain_hits(state["question"], "assay", top_k=4)
    hits = list(result["hits"])
    return {
        "domains": ["assay", "literature"],
        "assay_hits": hits,
        "retrieved_rows": [*state.get("retrieved_rows", []), *flatten_hits("assay", hits)],
        "supporting_ids": merge_supporting_ids(
            state.get("supporting_ids", empty_supporting_ids()), collect_supporting_ids(hits)
        ),
        "trace": append_trace(state, f"retrieved {len(hits)} assay hits via {result['backend']}"),
    }


def literature_followup_node(state: GraphState) -> dict[str, Any]:
    query = build_followup_query(
        state["question"], state.get("assay_hits", []), keys=["target_name", "taxonomy_id", "aid"]
    )
    result = retrieve_domain_hits(query, "literature", top_k=4)
    hits = list(result["hits"])
    return {
        "literature_hits": hits,
        "retrieved_rows": [*state.get("retrieved_rows", []), *flatten_hits("literature", hits)],
        "supporting_ids": merge_supporting_ids(
            state.get("supporting_ids", empty_supporting_ids()), collect_supporting_ids(hits)
        ),
        "trace": append_trace(
            state, f"retrieved {len(hits)} literature hits via {result['backend']} for follow-up query"
        ),
    }


def pathway_retrieval_node(state: GraphState) -> dict[str, Any]:
    result = retrieve_domain_hits(state["question"], "pathway", top_k=4)
    hits = list(result["hits"])
    return {
        "domains": ["pathway", "taxonomy"],
        "pathway_hits": hits,
        "retrieved_rows": [*state.get("retrieved_rows", []), *flatten_hits("pathway", hits)],
        "supporting_ids": merge_supporting_ids(
            state.get("supporting_ids", empty_supporting_ids()), collect_supporting_ids(hits)
        ),
        "trace": append_trace(state, f"retrieved {len(hits)} pathway hits via {result['backend']}"),
    }


def taxonomy_followup_node(state: GraphState) -> dict[str, Any]:
    query = build_followup_query(
        state["question"],
        state.get("pathway_hits", []),
        keys=["taxonomy_id", "pathway_accession", "taxonomy_name", "source_pathway"],
    )
    result = retrieve_domain_hits(query, "taxonomy", top_k=4)
    hits = list(result["hits"])
    return {
        "taxonomy_hits": hits,
        "retrieved_rows": [*state.get("retrieved_rows", []), *flatten_hits("taxonomy", hits)],
        "supporting_ids": merge_supporting_ids(
            state.get("supporting_ids", empty_supporting_ids()), collect_supporting_ids(hits)
        ),
        "trace": append_trace(
            state, f"retrieved {len(hits)} taxonomy hits via {result['backend']} for follow-up query"
        ),
    }


def generic_synthesis_node(state: GraphState) -> dict[str, Any]:
    titles = collect_top_titles(state)
    route = state.get("route", {})
    compound_title = state.get("compound_context", {}).get("title", "CID 4")
    answer = (
        f"{compound_title} was routed to {', '.join(route.get('domains', [])) or 'literature'} evidence. "
        f"Top grounded records: {titles or 'no hits retrieved'}."
    )
    return {
        "draft_answer": answer,
        "trace": append_trace(state, "drafted generic routed answer"),
    }


def assay_literature_synthesis_node(state: GraphState) -> dict[str, Any]:
    assay_titles = join_titles(state.get("assay_hits", []))
    literature_titles = join_titles(state.get("literature_hits", []))
    aid_values = state.get("supporting_ids", {}).get("aid", [])[:3]
    citation_values = [
        *state.get("supporting_ids", {}).get("pmid", [])[:2],
        *state.get("supporting_ids", {}).get("doi", [])[:1],
    ]
    compound_title = state.get("compound_context", {}).get("title", "CID 4")
    answer = (
        f"{compound_title} assay evidence is led by {assay_titles or 'no assay hits'}, "
        f"and the linked literature evidence is led by {literature_titles or 'no literature hits'}. "
        f"Supporting assay IDs: {', '.join(aid_values) or 'none'}. "
        f"Supporting citations: {', '.join(citation_values) or 'none'}."
    )
    return {
        "draft_answer": answer,
        "trace": append_trace(state, "drafted assay-plus-literature answer"),
    }


def pathway_taxonomy_synthesis_node(state: GraphState) -> dict[str, Any]:
    pathway_titles = join_titles(state.get("pathway_hits", []))
    taxonomy_titles = join_titles(state.get("taxonomy_hits", []))
    accessions = state.get("supporting_ids", {}).get("pathway_accession", [])[:3]
    taxonomy_ids = state.get("supporting_ids", {}).get("taxonomy_id", [])[:3]
    compound_title = state.get("compound_context", {}).get("title", "CID 4")
    answer = (
        f"{compound_title} pathway evidence is led by {pathway_titles or 'no pathway hits'} and is checked against "
        f"taxonomy evidence from {taxonomy_titles or 'no taxonomy hits'}. "
        f"Supporting accessions: {', '.join(accessions) or 'none'}. "
        f"Supporting taxonomy IDs: {', '.join(taxonomy_ids) or 'none'}."
    )
    return {
        "draft_answer": answer,
        "trace": append_trace(state, "drafted pathway-plus-taxonomy answer"),
    }


def compound_context_synthesis_node(state: GraphState) -> dict[str, Any]:
    context = state.get("compound_context", {})
    product_hits = state.get("product_use_hits", [])
    titles = join_titles(product_hits)
    answer = (
        f"{context.get('title', 'CID 4')} (CID {context.get('cid', '4')}) is grounded by the compound record summary: "
        f"{context.get('summary', 'no summary extracted')}. "
        f"Product-use evidence highlights {titles or 'no product-use hits'}."
    )
    return {
        "draft_answer": answer,
        "trace": append_trace(state, "drafted compound-context answer"),
    }


def generic_validation_node(state: GraphState) -> dict[str, Any]:
    issues: list[str] = []
    if not state.get("retrieved_rows"):
        issues.append("No retrieved rows were present for the answer.")
    if not state.get("supporting_ids", {}).get("source_file"):
        issues.append("No source file provenance was captured.")
    if not state.get("draft_answer"):
        issues.append("No draft answer was produced.")
    return validation_update(state, issues)


def assay_literature_validation_node(state: GraphState) -> dict[str, Any]:
    issues: list[str] = []
    if not state.get("assay_hits"):
        issues.append("Missing assay evidence.")
    if not state.get("literature_hits"):
        issues.append("Missing literature evidence.")
    if not state.get("supporting_ids", {}).get("aid"):
        issues.append("No assay identifiers were captured.")
    if not (state.get("supporting_ids", {}).get("pmid") or state.get("supporting_ids", {}).get("doi")):
        issues.append("No literature citation identifiers were captured.")
    return validation_update(state, issues)


def pathway_taxonomy_validation_node(state: GraphState) -> dict[str, Any]:
    issues: list[str] = []
    if not state.get("pathway_hits"):
        issues.append("Missing pathway evidence.")
    if not state.get("taxonomy_hits"):
        issues.append("Missing taxonomy evidence.")
    if not state.get("supporting_ids", {}).get("pathway_accession"):
        issues.append("No pathway accession was captured.")
    if not state.get("supporting_ids", {}).get("taxonomy_id"):
        issues.append("No taxonomy identifier was captured.")
    return validation_update(state, issues)


def validation_update(state: GraphState, issues: list[str]) -> dict[str, Any]:
    passed = len(issues) == 0
    validated_answer = state.get("draft_answer", "") if passed else ""
    validation = {
        "passed": passed,
        "issues": issues,
        "evidence_families": collect_evidence_families(state),
    }
    trace_message = "validation passed" if passed else f"validation flagged: {'; '.join(issues)}"
    return {
        "validated_answer": validated_answer,
        "validation": validation,
        "trace": append_trace(state, trace_message),
    }


def finalize_state(state: GraphState) -> dict[str, Any]:
    return {
        "status": "ok",
        "workflow": state.get("workflow"),
        "question": state.get("question"),
        "question_type": state.get("question_type"),
        "route": state.get("route", {}),
        "langgraph_runtime": state.get("langgraph_runtime", {}),
        "compound_context": state.get("compound_context", {}),
        "literature_hits": state.get("literature_hits", []),
        "assay_hits": state.get("assay_hits", []),
        "pathway_hits": state.get("pathway_hits", []),
        "taxonomy_hits": state.get("taxonomy_hits", []),
        "product_use_hits": state.get("product_use_hits", []),
        "retrieved_rows": state.get("retrieved_rows", []),
        "supporting_ids": state.get("supporting_ids", empty_supporting_ids()),
        "draft_answer": state.get("draft_answer", ""),
        "validated_answer": state.get("validated_answer", ""),
        "validation": state.get("validation", {"passed": False, "issues": []}),
        "trace": state.get("trace", []),
    }


@lru_cache(maxsize=1)
def load_compound_context() -> dict[str, Any]:
    with cid4_analysis.resolve_data_path("COMPOUND_CID_4.json").open(encoding="utf-8") as file:
        payload = json.load(file)

    record = payload["Record"]
    summary = extract_first_summary(record.get("Section", []))
    return {
        "cid": int(record.get("RecordNumber", 4)),
        "title": str(record.get("RecordTitle", "CID 4")),
        "record_type": str(record.get("RecordType", "CID")),
        "summary": summary,
    }


def extract_first_summary(sections: list[dict[str, Any]]) -> str:
    for section in sections:
        info_values = section.get("Information", [])
        for item in info_values:
            string_values = item.get("Value", {}).get("StringWithMarkup", [])
            for string_value in string_values:
                text = str(string_value.get("String", "")).strip()
                if text:
                    return " ".join(text.split())
        nested = section.get("Section", [])
        if nested:
            nested_summary = extract_first_summary(nested)
            if nested_summary:
                return nested_summary
    return ""


def collect_supporting_ids(hits: list[dict[str, Any]]) -> dict[str, list[str]]:
    collected = empty_supporting_ids()
    for hit in hits:
        metadata = dict(hit.get("metadata", {}))
        maybe_add(collected["aid"], metadata.get("aid") or metadata.get("BioAssay_AID"))
        maybe_add(collected["pmid"], metadata.get("pmid") or metadata.get("PMID"))
        maybe_add(collected["doi"], metadata.get("doi") or metadata.get("DOI"))
        maybe_add(
            collected["pathway_accession"],
            metadata.get("pathway_accession") or metadata.get("Pathway_Accession") or metadata.get("source_pathway"),
        )
        maybe_add(collected["taxonomy_id"], metadata.get("taxonomy_id") or metadata.get("Taxonomy_ID"))
        maybe_add(collected["source_file"], metadata.get("source_file"))
    return collected


def maybe_add(target: list[str], value: Any) -> None:
    text = str(value).strip() if value is not None else ""
    if text and text != "None" and text not in target:
        target.append(text)


def flatten_hits(domain: str, hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    flattened = []
    for hit in hits:
        flattened.append(
            {
                "domain": domain,
                "source_id": hit.get("source_id"),
                "doc_type": hit.get("doc_type"),
                "title": hit.get("title"),
                "score": hit.get("score"),
                "backend": hit.get("backend"),
                "metadata": dict(hit.get("metadata", {})),
            }
        )
    return flattened


def build_followup_query(question: str, hits: list[dict[str, Any]], *, keys: list[str]) -> str:
    terms: list[str] = []
    for hit in hits[:3]:
        metadata = dict(hit.get("metadata", {}))
        for key in keys:
            value = metadata.get(key)
            text = str(value).strip() if value is not None else ""
            if text and text != "None" and text not in terms:
                terms.append(text)
        title = str(hit.get("title", "")).strip()
        if title and title not in terms:
            terms.append(title)
    return " ".join([question, *terms[:6]]).strip()


def join_titles(hits: list[dict[str, Any]]) -> str:
    titles = [str(hit.get("title", "")).strip() for hit in hits[:3] if str(hit.get("title", "")).strip()]
    return "; ".join(titles)


def collect_top_titles(state: GraphState) -> str:
    top_hits = list(state.get("retrieved_rows", []))[:4]
    titles = [str(hit.get("title", "")).strip() for hit in top_hits if str(hit.get("title", "")).strip()]
    return "; ".join(titles)


def collect_evidence_families(state: GraphState) -> list[str]:
    families = []
    for domain, key in (
        ("literature", "literature_hits"),
        ("patent", "patent_hits"),
        ("assay", "assay_hits"),
        ("pathway", "pathway_hits"),
        ("taxonomy", "taxonomy_hits"),
        ("product_use", "product_use_hits"),
    ):
        if state.get(key):
            families.append(domain)
    return families


def get_hits_key(domain: str) -> str:
    return {
        "literature": "literature_hits",
        "patent": "patent_hits",
        "assay": "assay_hits",
        "pathway": "pathway_hits",
        "taxonomy": "taxonomy_hits",
        "product_use": "product_use_hits",
    }[domain]
