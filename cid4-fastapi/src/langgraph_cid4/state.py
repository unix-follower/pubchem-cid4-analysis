from __future__ import annotations

from typing import Any, TypedDict


class GraphState(TypedDict, total=False):
    workflow: str
    question: str
    question_type: str
    domains: list[str]
    route: dict[str, Any]
    compound_context: dict[str, Any]
    retrieved_rows: list[dict[str, Any]]
    literature_hits: list[dict[str, Any]]
    patent_hits: list[dict[str, Any]]
    assay_hits: list[dict[str, Any]]
    pathway_hits: list[dict[str, Any]]
    taxonomy_hits: list[dict[str, Any]]
    product_use_hits: list[dict[str, Any]]
    supporting_ids: dict[str, list[str]]
    draft_answer: str
    validated_answer: str
    validation: dict[str, Any]
    trace: list[str]
    langgraph_runtime: dict[str, Any]


SUPPORTING_ID_KEYS = (
    "aid",
    "pmid",
    "doi",
    "pathway_accession",
    "taxonomy_id",
    "source_file",
)


def build_initial_state(
    question: str, workflow: str, *, question_type: str = ""
) -> GraphState:
    return {
        "workflow": workflow,
        "question": question,
        "question_type": question_type,
        "domains": [],
        "route": {},
        "compound_context": {},
        "retrieved_rows": [],
        "literature_hits": [],
        "patent_hits": [],
        "assay_hits": [],
        "pathway_hits": [],
        "taxonomy_hits": [],
        "product_use_hits": [],
        "supporting_ids": empty_supporting_ids(),
        "draft_answer": "",
        "validated_answer": "",
        "validation": {"passed": False, "issues": []},
        "trace": [],
        "langgraph_runtime": {},
    }


def empty_supporting_ids() -> dict[str, list[str]]:
    return {key: [] for key in SUPPORTING_ID_KEYS}


def append_trace(state: GraphState, message: str) -> list[str]:
    return [*state.get("trace", []), message]


def merge_supporting_ids(
    current: dict[str, list[str]],
    additions: dict[str, list[str]],
) -> dict[str, list[str]]:
    merged = {key: list(current.get(key, [])) for key in SUPPORTING_ID_KEYS}
    for key in SUPPORTING_ID_KEYS:
        for value in additions.get(key, []):
            if value not in merged[key]:
                merged[key].append(value)
    return merged
