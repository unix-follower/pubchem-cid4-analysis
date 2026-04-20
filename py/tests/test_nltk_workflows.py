from __future__ import annotations

import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from nltk_workflows import analyze_documents, import_nltk, run_literature_workflow  # noqa: E402
from text_processing import filter_stopwords, tokenize_preserving_chemistry  # noqa: E402


class FakeFreqDist(dict):
    def __init__(self, tokens: list[str]) -> None:
        counts: dict[str, int] = {}
        for token in tokens:
            counts[token] = counts.get(token, 0) + 1
        super().__init__(counts)

    def most_common(self, limit: int) -> list[tuple[str, int]]:
        return sorted(self.items(), key=lambda item: (-item[1], item[0]))[:limit]


class FakeStemmer:
    def stem(self, token: str) -> str:
        return token.rstrip("s")


class FakeBigramAssocMeasures:
    @property
    def pmi(self) -> str:
        return "pmi"


class FakeBigramCollocationFinder:
    def __init__(self, tokens: list[str]) -> None:
        self.tokens = tokens

    @classmethod
    def from_words(cls, tokens: list[str]) -> FakeBigramCollocationFinder:
        return cls(tokens)

    def apply_freq_filter(self, minimum_frequency: int) -> None:
        del minimum_frequency

    def score_ngrams(self, measure: object) -> list[tuple[tuple[str, str], float]]:
        del measure
        pairs: list[tuple[tuple[str, str], float]] = []
        for index in range(len(self.tokens) - 1):
            pairs.append(((self.tokens[index], self.tokens[index + 1]), float(index + 1)))
        return pairs


class FakeStopwords:
    @staticmethod
    def words(language: str) -> list[str]:
        if language != "english":
            return []
        return ["the", "and", "for", "of"]


def build_fake_nltk_module() -> types.SimpleNamespace:
    return types.SimpleNamespace(
        FreqDist=FakeFreqDist,
        PorterStemmer=FakeStemmer,
        BigramAssocMeasures=FakeBigramAssocMeasures,
        collocations=types.SimpleNamespace(BigramCollocationFinder=FakeBigramCollocationFinder),
        corpus=types.SimpleNamespace(stopwords=FakeStopwords()),
        data=types.SimpleNamespace(find=lambda locator: locator),
        download=lambda resource_name, quiet=True: None,
    )


class NltkWorkflowTests(unittest.TestCase):
    def test_tokenizer_preserves_chemistry_tokens(self) -> None:
        text = "1-Amino-2-propanol with NADH, IC50, ER-alpha, PMID 123 and CID 4."

        tokens = tokenize_preserving_chemistry(text)

        self.assertIn("1-Amino-2-propanol", tokens)
        self.assertIn("NADH", tokens)
        self.assertIn("IC50", tokens)
        self.assertIn("ER-alpha", tokens)
        self.assertIn("PMID", tokens)
        self.assertIn("CID", tokens)

    def test_stopword_filter_preserves_chemistry_allowlist(self) -> None:
        filtered = filter_stopwords(["the", "and", "isopropanolamine", "NADH", "fungicide"])

        self.assertEqual(filtered, ["isopropanolamine", "nadh", "fungicide"])

    def test_import_nltk_returns_skipped_when_library_missing(self) -> None:
        with patch(
            "importlib.import_module",
            side_effect=ModuleNotFoundError("No module named 'nltk'"),
        ):
            result = import_nltk()

        self.assertEqual(result["status"], "skipped")

    def test_analyze_documents_uses_expected_result_shape(self) -> None:
        fake_nltk = build_fake_nltk_module()

        result = analyze_documents(fake_nltk, ["isopropanolamine fungicide pathway", "fungicide pathway"])

        self.assertIn("top_terms", result)
        self.assertIn("top_bigrams", result)
        self.assertGreater(result["token_count"], 0)

    def test_literature_workflow_can_run_with_fake_nltk(self) -> None:
        fake_nltk = build_fake_nltk_module()
        fake_frame = pd.DataFrame(
            [
                {
                    "Title": "Isopropanolamine fungicide report",
                    "Abstract": "Pathway metabolism study",
                    "Keywords": "fungicide, metabolism",
                    "Citation": "PMID 1",
                    "Subject": "Chemistry",
                    "Publication_Name": "Journal",
                }
            ]
        )

        with (
            patch("nltk_workflows.import_nltk", return_value=fake_nltk),
            patch("nltk_workflows.load_literature_frame", return_value=fake_frame),
        ):
            result = run_literature_workflow()

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["workflow"], "literature")


if __name__ == "__main__":
    unittest.main()
