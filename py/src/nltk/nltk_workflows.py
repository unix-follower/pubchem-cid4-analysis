from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from math import log2
from typing import Any

from nltk.metrics.association import BigramAssocMeasures
from nltk.probability import FreqDist
from nltk.stem import PorterStemmer

import nltk
from nltk import collocations
from src.pgvector.datasets import (
    load_bioactivity_frame,
    load_literature_frame,
    load_patent_frame,
    load_pathway_reaction_frame,
    load_taxonomy_frame,
)

from .datasets import (
    load_toxicology_frame,
)
from .text_processing import (
    BASE_STOPWORDS,
    CHEMISTRY_ALLOWLIST,
    build_document_text,
    filter_stopwords,
    lowercase_tokens,
    normalize_text,
    stable_top_items,
    tokenize_preserving_chemistry,
)

TOP_TERM_LIMIT = 20
TOP_BIGRAM_LIMIT = 15
TOP_DISTINCTIVE_LIMIT = 12


def run_literature_workflow() -> dict[str, Any]:
    frame = load_literature_frame()
    documents = build_document_text(
        frame,
        ["Title", "Abstract", "Keywords", "Citation", "Subject", "Publication_Name"],
    )
    analysis = analyze_documents(documents)
    analysis.update(
        {
            "workflow": "literature",
            "row_count": int(len(frame)),
            "document_count": int(len(documents)),
            "notable_term_counts": count_specific_terms(
                analysis["tokens"],
                ["isopropanolamine", "fungicide", "pathway", "metabolism"],
            ),
        }
    )
    del analysis["tokens"]
    return analysis


def run_literature_vs_patent_workflow() -> dict[str, Any]:
    literature_documents = build_document_text(load_literature_frame(), ["Title", "Abstract", "Keywords", "Citation"])
    patent_documents = build_document_text(load_patent_frame(), ["title", "abstract"])

    literature_analysis = analyze_documents(literature_documents)
    patent_analysis = analyze_documents(patent_documents)

    literature_counter = Counter(literature_analysis["tokens"])
    patent_counter = Counter(patent_analysis["tokens"])
    return {
        "workflow": "literature-vs-patent",
        "literature_document_count": int(len(literature_documents)),
        "patent_document_count": int(len(patent_documents)),
        "literature_top_terms": literature_analysis["top_terms"],
        "patent_top_terms": patent_analysis["top_terms"],
        "literature_top_bigrams": literature_analysis["top_bigrams"],
        "patent_top_bigrams": patent_analysis["top_bigrams"],
        "distinctive_literature_terms": distinctive_terms(literature_counter, patent_counter),
        "distinctive_patent_terms": distinctive_terms(patent_counter, literature_counter),
    }


def run_bioactivity_workflow() -> dict[str, Any]:
    frame = load_bioactivity_frame()
    documents = build_document_text(
        frame,
        ["BioAssay_Name", "Target_Name", "Activity", "Activity_Type", "citations"],
    )
    analysis = analyze_documents(documents)
    analysis.update(
        {
            "workflow": "bioactivity",
            "row_count": int(len(frame)),
            "notable_term_counts": count_specific_terms(
                analysis["tokens"],
                ["estrogen", "androgen", "cytochrome", "plasmodium", "yeast"],
            ),
        }
    )
    del analysis["tokens"]
    return analysis


def run_taxonomy_workflow() -> dict[str, Any]:
    frame = load_taxonomy_frame()
    source_tokens: list[str] = []
    normalized_pairs: list[dict[str, str | int]] = []
    for _, row in frame.iterrows():
        organism = normalize_text(row.get("Source_Organism", ""))
        taxonomy = normalize_text(row.get("Taxonomy", ""))
        tokens = prepare_tokens(f"{organism} {taxonomy}")
        source_tokens.extend(tokens)
        taxonomy_id = row.get("Taxonomy_ID", -1)
        if str(taxonomy_id).strip() == "":
            taxonomy_id = -1
        normalized_pairs.append(
            {
                "source_organism": organism,
                "taxonomy": taxonomy,
                "normalized_label": " ".join(tokens[:6]),
                "taxonomy_id": int(taxonomy_id),
            }
        )

    return {
        "workflow": "taxonomy",
        "row_count": int(len(frame)),
        "top_terms": stable_top_items(dict(Counter(source_tokens)), TOP_TERM_LIMIT),
        "normalization_preview": normalized_pairs[:10],
    }


def run_toxicology_workflow() -> dict[str, Any]:
    frame = load_toxicology_frame()
    documents = build_document_text(frame, ["Effect", "Route", "Reference"])
    analysis = analyze_documents(documents)
    analysis.update(
        {
            "workflow": "toxicology",
            "row_count": int(len(frame)),
            "route_counts": normalize_value_counts(frame["Route"]),
            "effect_counts": count_specific_terms(
                analysis["tokens"],
                ["behavioral", "somnolence", "diarrhea", "excitement"],
            ),
        }
    )
    del analysis["tokens"]
    return analysis


def run_pathway_workflow() -> dict[str, Any]:
    frame = load_pathway_reaction_frame()
    documents = build_document_text(frame, ["Equation", "Reaction", "Control", "Taxonomy"])
    analysis = analyze_documents(documents)
    analysis.update(
        {
            "workflow": "pathway",
            "row_count": int(len(frame)),
            "notable_term_counts": count_specific_terms(
                analysis["tokens"],
                ["glutathione", "nadh", "aminoacetone", "1-amino-propan-2-ol"],
            ),
        }
    )
    del analysis["tokens"]
    return analysis


def analyze_documents(documents: Iterable[str]) -> dict[str, Any]:
    all_tokens: list[str] = []
    all_stems: list[str] = []

    for document in documents:
        tokens = prepare_tokens(document)
        all_tokens.extend(tokens)
        all_stems.extend(stem_tokens(tokens))

    frequency = FreqDist(all_tokens)
    top_terms = [{"term": term, "count": int(count)} for term, count in frequency.most_common(TOP_TERM_LIMIT)]
    top_bigrams = extract_top_bigrams(all_tokens)

    return {
        "token_count": int(len(all_tokens)),
        "unique_token_count": int(len(set(all_tokens))),
        "top_terms": top_terms,
        "top_bigrams": top_bigrams,
        "top_stems": stable_top_items(dict(Counter(all_stems)), TOP_TERM_LIMIT),
        "tokens": all_tokens,
    }


def prepare_tokens(text: str) -> list[str]:
    raw_tokens = tokenize_preserving_chemistry(text)
    lowered = lowercase_tokens(raw_tokens)
    stopwords = nltk_stopwords()
    filtered = filter_stopwords(lowered, stopwords)
    return [token for token in filtered if token and not token.isdigit()]


def stem_tokens(tokens: Iterable[str]) -> list[str]:
    stemmer = PorterStemmer()
    stems: list[str] = []
    for token in tokens:
        if token in CHEMISTRY_ALLOWLIST or any(character.isdigit() for character in token):
            stems.append(token)
            continue
        stems.append(stemmer.stem(token))
    return stems


def extract_top_bigrams(tokens: list[str]) -> list[dict[str, int | str | float]]:
    if len(tokens) < 2:
        return []
    finder = collocations.BigramCollocationFinder.from_words(tokens)
    finder.apply_freq_filter(2)
    scored = finder.score_ngrams(BigramAssocMeasures().pmi)
    ranked = sorted(scored, key=lambda item: (-float(item[1]), item[0]))[:TOP_BIGRAM_LIMIT]
    return [
        {
            "bigram": f"{left} {right}",
            "pmi": float(score),
        }
        for (left, right), score in ranked
    ]


def count_specific_terms(tokens: list[str], vocabulary: list[str]) -> dict[str, int]:
    counter = Counter(tokens)
    return {term: int(counter.get(term.lower(), 0)) for term in vocabulary}


def distinctive_terms(primary: Counter[str], reference: Counter[str]) -> list[dict[str, float | str | int]]:
    primary_total = max(sum(primary.values()), 1)
    reference_total = max(sum(reference.values()), 1)
    rows: list[dict[str, float | str | int]] = []
    for term, count in primary.items():
        if count < 3:
            continue
        primary_share = count / primary_total
        reference_share = max(reference.get(term, 0) / reference_total, 1e-9)
        rows.append(
            {
                "term": term,
                "count": int(count),
                "log_ratio": float(log2(primary_share / reference_share)),
            }
        )
    rows.sort(key=lambda item: (-float(item["log_ratio"]), str(item["term"])))
    return rows[:TOP_DISTINCTIVE_LIMIT]


def normalize_value_counts(series: Any) -> dict[str, int]:
    normalized = series.astype("string").fillna("Unknown").str.strip()
    normalized = normalized.mask(normalized.eq(""), "Unknown")
    counts = normalized.value_counts().to_dict()
    return {str(key): int(value) for key, value in counts.items()}


def nltk_stopwords() -> set[str]:
    try:
        return set(nltk.corpus.stopwords.words("english"))
    except LookupError:
        download_nltk_resource("corpora/stopwords", "stopwords")
        try:
            return set(nltk.corpus.stopwords.words("english"))
        except LookupError:
            return set(BASE_STOPWORDS)


def download_nltk_resource(locator: str, resource_name: str) -> None:
    try:
        nltk.data.find(locator)
    except LookupError:
        nltk.download(resource_name, quiet=True)
