## Run
```sh
source .venv/bin/activate
export DATA_DIR="$(pwd)/../data"
python src/cid4_analysis.py
```

## FastAPI server
The Python workspace also includes a FastAPI HTTPS server that mirrors the same `/api/...` surface used by the Angular app and by the Scala Tomcat and Netty implementations.

Install the optional server dependencies:

```sh
uv sync --extra fastapi
```

Run it from the `py` workspace:

```sh
source .venv/bin/activate
export DATA_DIR="$(pwd)/../data"
python src/cid4_fastapi.py
```

TLS configuration:
- `FASTAPI_HOST` or `SERVER_HOST` defaults to `0.0.0.0`
- `FASTAPI_PORT`, `SERVER_PORT`, or `PORT` defaults to `8443`
- `TLS_CERT_FILE`, `TLS_KEY_FILE`, and optional `TLS_KEY_PASSWORD` can be set explicitly

If explicit TLS files are not set, the server falls back to the PEM certificate, encrypted private key, and demo password recorded in `data/out/crypto/cid4_crypto.summary.json`.

Quick verification:

```sh
curl -k https://localhost:8443/api/health
curl -k https://localhost:8443/api/cid4/structure/2d
curl -k https://localhost:8443/api/cid4/conformer/1
curl -k https://localhost:8443/api/algorithms/pathway
curl -k "https://localhost:8443/api/health?mode=error"
```

## AsyncIO server
The Python workspace also includes a bare-minimum asyncio HTTPS server that exposes the same `/api/...` surface as the FastAPI, Starlette, Flask, Scala, and C++ backends without adding another web framework.

It uses only stdlib `asyncio` and `ssl`, so there is no extra server dependency to install beyond the base Python environment.

Run it from the `py` workspace:

```sh
source .venv/bin/activate
export DATA_DIR="$(pwd)/../data"
python src/cid4_asyncio.py
```

TLS configuration:
- `ASYNCIO_HOST` or `SERVER_HOST` defaults to `0.0.0.0`
- `ASYNCIO_PORT`, `SERVER_PORT`, or `PORT` defaults to `8443`
- `TLS_CERT_FILE`, `TLS_KEY_FILE`, and optional `TLS_KEY_PASSWORD` can be set explicitly

If explicit TLS files are not set, the asyncio server falls back to the PEM certificate, encrypted private key, and demo password recorded in `data/out/crypto/cid4_crypto.summary.json`.

Quick verification:

```sh
curl -k https://localhost:8443/api/health
curl -k https://localhost:8443/api/cid4/compound
curl -k https://localhost:8443/api/algorithms/taxonomy
curl -k "https://localhost:8443/api/health?mode=error"
```

## Starlette server
The Python workspace also includes a Starlette HTTPS server that exposes the same `/api/...` surface as the FastAPI, Scala Tomcat, and Scala Netty backends.

Install the optional server dependencies:

```sh
uv sync --extra starlette
```

Run it from the `py` workspace:

```sh
source .venv/bin/activate
export DATA_DIR="$(pwd)/../data"
python src/cid4_starlette.py
```

TLS configuration is shared with the FastAPI runner:
- `FASTAPI_HOST` or `SERVER_HOST` defaults to `0.0.0.0`
- `FASTAPI_PORT`, `SERVER_PORT`, or `PORT` defaults to `8443`
- `TLS_CERT_FILE`, `TLS_KEY_FILE`, and optional `TLS_KEY_PASSWORD` can be set explicitly

If explicit TLS files are not set, the Starlette server falls back to the PEM certificate, encrypted private key, and demo password recorded in `data/out/crypto/cid4_crypto.summary.json`.

Quick verification:

```sh
curl -k https://localhost:8443/api/health
curl -k https://localhost:8443/api/cid4/conformer/1
curl -k https://localhost:8443/api/algorithms/taxonomy
curl -k "https://localhost:8443/api/health?mode=error"
```

## Flask server
The Python workspace also includes a Flask HTTPS server that exposes the same `/api/...` surface as the FastAPI, Starlette, Scala Tomcat, and Scala Netty backends.

Install the optional server dependencies:

```sh
uv sync --extra flask
```

Run it from the `py` workspace:

```sh
source .venv/bin/activate
export DATA_DIR="$(pwd)/../data"
python src/cid4_flask.py
```

TLS configuration is shared with the other Python runners:
- `FLASK_HOST` overrides the bind host for the Flask runner
- `FLASK_PORT` overrides the bind port for the Flask runner
- `FASTAPI_HOST` or `SERVER_HOST` defaults to `0.0.0.0`
- `FASTAPI_PORT`, `SERVER_PORT`, or `PORT` defaults to `8443`
- `TLS_CERT_FILE`, `TLS_KEY_FILE`, and optional `TLS_KEY_PASSWORD` can be set explicitly

If explicit TLS files are not set, the Flask server falls back to the PEM certificate, encrypted private key, and demo password recorded in `data/out/crypto/cid4_crypto.summary.json`.

Quick verification:

```sh
curl -k https://localhost:8443/api/health
curl -k https://localhost:8443/api/cid4/compound
curl -k https://localhost:8443/api/algorithms/bioactivity
curl -k "https://localhost:8443/api/health?mode=error"
```

The standard Python run now also writes bioactivity artifacts from `pubchem_cid_4_bioactivity.csv` into `data/out`:
- filtered IC50 rows with computed pIC50
- summary JSON with row counts and descriptive statistics
- a PNG plot of $y = -\log_{10}(x)$ across the observed IC50 range

The same run now also writes a manual gradient-descent analysis from the atom feature matrix derived from `Conformer3D_COMPOUND_CID_4(1).sdf` into `data/out`:
- a CSV trace of per-epoch weight, gradient, summed squared error, and MSE for the no-intercept model $\hat{y} = wx$
- a summary JSON documenting the hand-derived gradient $\frac{\partial}{\partial w}\sum_i(y_i - wx_i)^2 = 2\sum_i x_i(wx_i - y_i)$ with atom mass as the feature and atomic number as the target
- a PNG loss curve across epochs
- a PNG scatter/fit plot for atom mass versus atomic number under the learned weight

This gradient-descent example is intentionally educational rather than general-purpose: it uses the 14 atom rows of the CID 4 conformer as the full dataset, treats `mass` as the single feature, treats `atomicNumber` as the target, optimizes a one-parameter no-intercept regression, and reports the closed-form least-squares solution alongside the iterative result as a numerical check.

The same run now also writes Hill/sigmoidal dose-response reference artifacts from `pubchem_cid_4_bioactivity.csv` into `data/out`:
- a CSV of positive numeric `Activity_Value` rows interpreted as inferred Hill-scale parameters $K$, including trapezoidal-rule AUC values for the inferred reference curves
- a summary JSON documenting the normalized Hill model $f(c) = \frac{c^n}{K^n + c^n}$, its derivatives, midpoint / inflection interpretation, and AUC integration settings
- a PNG plot of representative reference Hill curves using `Activity_Value` as the inferred half-maximal concentration scale

Because the CID 4 bioactivity CSV contains potency-style summary values rather than raw per-concentration response series, this Hill output is a reference-curve analysis rather than a nonlinear fit to experimental dose-response points. The implementation uses each positive numeric `Activity_Value` as an inferred $K$ value, reports that the log-concentration midpoint occurs at $c = K$, and approximates AUC with the trapezoidal rule over an inferred concentration grid scaled relative to each row's $K$. For the default reference coefficient $n = 1$, there is no positive linear-concentration inflection point.

The same run now also writes positive-numeric `Activity_Value` descriptive statistics and normality artifacts from `pubchem_cid_4_bioactivity.csv` into `data/out`:
- a CSV of retained rows where `Activity_Value` is numeric and strictly greater than 0
- a summary JSON with mean, sample variance, skewness, quantiles, and a Shapiro-Wilk normality test result
- a PNG diagnostic plot pairing a log-scale histogram with a normal Q-Q panel when the retained sample supports it

This `Activity_Value` analysis follows the agreed scope exactly: only positive numeric rows are retained. Missing, non-numeric, zero, and negative values are counted in the summary metadata and excluded from the descriptive statistics and Shapiro-Wilk test.

The same run now also writes a Bayesian posterior bioactivity analysis from `pubchem_cid_4_bioactivity.csv` into `data/out`:
- a CSV of retained binary evidence rows where `Activity` is `Active` or `Inactive`
- a summary JSON for the posterior probability $P(\mathrm{Active} \mid \mathrm{CID}=4)$ using a conjugate Beta-Binomial update with prior $\mathrm{Beta}(1,1)$

This posterior output excludes rows with `Activity = Unspecified` from the binary update and reports their count separately in the summary metadata. The posterior parameters are computed as $\alpha_{post} = 1 + n_{active}$ and $\beta_{post} = 1 + n_{inactive}$, and the summary reports the posterior mean, median, variance, a 95% equal-tailed credible interval, and the posterior probability that the latent activity rate exceeds $0.5$.

The same run now also writes an `Activity` versus `Aid_Type` chi-square bioactivity analysis from `pubchem_cid_4_bioactivity.csv` into `data/out`:
- a contingency CSV over retained binary `Activity` rows and observed `Aid_Type` categories
- a summary JSON for a Pearson chi-square test of independence between `Activity` and `Aid_Type`

This chi-square output reuses the same binary `Activity = Active / Inactive` evidence filter as the posterior analysis, excluding `Unspecified` and other non-binary activity labels before the contingency table is built. `Aid_Type` values are trimmed and blank values are normalized to `Unknown`. If fewer than two observed `Activity` levels or fewer than two observed `Aid_Type` levels remain after filtering, the summary records that the chi-square test could not be meaningfully computed on the retained data slice instead of emitting a misleading test statistic.

The same run now also writes an assay-level binomial bioactivity analysis from `pubchem_cid_4_bioactivity.csv` into `data/out`:
- a CSV of the binomial probability mass function over `k = 0..n` active assays
- a summary JSON for $P(K = k \text{ active assays in } n \text{ assays})$ using unique `BioAssay_AID` values as trials

This binomial output first reuses the same `Activity = Active / Inactive` binary evidence filter as the posterior analysis, excluding `Unspecified` rows before grouping by assay. The first-pass assay resolution rule is that an assay is counted as `Active` if any retained row for that `BioAssay_AID` is `Active`; otherwise it is `Inactive`. The success probability is then estimated as the observed assay-level active fraction $p = n_{active\_assays} / n_{assays}$, and the summary reports the PMF at the observed active-assay count, cumulative tail probabilities, the binomial mean $np$, and the variance $np(1-p)$.

The same run now also writes atom-element entropy artifacts from the conformer-derived atom feature matrix into `data/out`:
- a CSV of O/N/C/H element counts, proportions, log proportions, and per-element Shannon contributions
- a summary JSON with the entropy value $H = -\sum p_i \log p_i$, normalized entropy, retained support, and any unexpected atom symbols
- a PNG bar chart of the O/N/C/H proportions with the entropy value in the title

This entropy analysis operates on the `symbol` column produced from `Conformer3D_COMPOUND_CID_4(1).sdf`. The entropy sum is computed over the required O/N/C/H support from the README exercise, while any unexpected symbols are reported separately for transparency.

The same run also writes a bonded-distance comparison artifact from the CID 4 conformer:
- a JSON report comparing bonded vs non-bonded inter-atom distances derived from the SDF 3D coordinates and PubChem bond list

The same run also writes a bonded-angle analysis artifact from the CID 4 conformer:
- a JSON report of bonded angles $A$-$B$-$C$ computed from 3D coordinates using the dot-product formula, where $A$-$B$ and $B$-$C$ are bonded and $B$ is the central atom

The same run also writes a spring-bond partial-derivative artifact from the CID 4 conformer:
- a JSON report of per-bond and per-atom Cartesian partial derivatives for the simple harmonic bond energy $E = \frac{1}{2}k(d - d_0)^2$ using 3D coordinates, chemistry-informed reference bond lengths $d_0$, and bond-order-specific spring constants $k$

## Format code
```sh
uv tool run ruff format
```

## Machine learning runner
The Python workspace now includes a first ML entrypoint that builds shared CID 4 datasets and writes a mixed set of artifacts into `data/out`:
- cross-library comparison summaries for scikit-learn, PyTorch, and TensorFlow where the task is genuinely comparable
- scikit-learn-first summaries for SVM, KNN, Decision Tree, Random Forest, K-Means, hierarchical clustering, PCA, and Naive Bayes
- scaffold summaries for GNN and SMILES-RNN next steps, with explicit dataset requirements and recommended libraries
- CSV exports of the prepared atom, bioactivity, regression, and taxonomy feature tables

Run it from the `py` workspace:

```sh
source .venv/bin/activate
export DATA_DIR="$(pwd)/../data"
python src/cid4_ml.py
```

The runner currently compares these tasks across libraries:
- atom heavy-atom vs hydrogen classification
- atom O/N/C/H element classification
- filtered bioactivity Active vs Inactive classification
- positive `Activity_Value` regression using molecular descriptors plus assay metadata

The bioactivity tabular workflows now also include XGBoost summaries written to `data/out/cid4_ml.xgboost_suite.summary.json`. The boosted-tree features go beyond the earlier constant molecular descriptors and basic assay encodings by adding missingness flags for `Protein_Accession`, `Gene_ID`, `PMID`, and `Activity_Value`, numeric taxonomy IDs, encoded `Bioassay_Data_Source`, and keyword flags derived from `BioAssay_Name`, `Target_Name`, and assay source text.

The current virtual environment may not include PyTorch or TensorFlow yet. In that case, the runner still completes and writes explicit `skipped` results for those libraries instead of failing. To install the optional deep-learning stack through the project metadata, add the `deep-learning` dependency group from `pyproject.toml` to your environment setup.

If XGBoost is not yet installed in the active environment, the runner writes an explicit `skipped` result for the boosted-tree summaries rather than failing the rest of the ML analysis. Install it with `uv sync --extra xgboost` when you want the boosted-tree workflows enabled.

The heavier descriptor and cheminformatics integrations are also optional now, so the default `uv sync --locked` environment stays lightweight enough for CI. Install them only when needed:
- `uv sync --extra descriptor-ml`
- `uv sync --extra nltk`
- `uv sync --extra chem-tools`
```shell
uv sync --locked --extra xgboost --extra descriptor-ml
```

For the mixed deliverable, a notebook companion can inspect the generated JSON summaries and reuse the shared `ml` package directly instead of duplicating feature engineering logic. The runner now also writes `cid4_ml.future_scaffolds.summary.json`, which captures the honest blockers and next code targets for a real graph-neural-network or SMILES-RNN implementation.

Notebook companion:
- `src/cid4_ml_taxonomy_text_baseline.ipynb` reuses `ml.datasets.build_taxonomy_clustering_frame()` to build a small TF-IDF plus logistic-regression baseline over the taxonomy text, then saves notebook artifacts back into `data/out`

## NLTK runner
The Python workspace now also includes a separate NLTK-oriented NLP runner for the text-heavy CID 4 datasets. It writes JSON summaries into `data/out` for:
- literature corpus term and collocation analysis
- literature-versus-patent vocabulary comparison
- bioactivity assay and target vocabulary extraction
- taxonomy name normalization and vocabulary cleanup
- toxicology short-text phrase extraction
- pathway and reaction wording analysis

Run it from the `py` workspace:

```sh
source .venv/bin/activate
export DATA_DIR="$(pwd)/../data"
python src/cid4_nltk.py
```

If NLTK is not installed in the active environment, the runner still completes and writes explicit `skipped` results instead of failing. Enable the optional dependency with:

```sh
uv sync --extra nltk
```

The runner is chemistry-aware at the token-normalization level. It preserves tokens such as `1-amino-2-propanol`, `NADH`, `IC50`, `ER-alpha`, `PMID`, `DOI`, `AID`, `CID`, and `SID` instead of over-cleaning them as generic English text.

Expected outputs under `data/out`:
- `cid4_nltk.literature.summary.json`
- `cid4_nltk.literature_vs_patent.summary.json`
- `cid4_nltk.bioactivity.summary.json`
- `cid4_nltk.taxonomy.summary.json`
- `cid4_nltk.toxicology.summary.json`
- `cid4_nltk.pathway.summary.json`

## pgvector runner
The Python workspace now also includes a pgvector-oriented ingestion runner for semantic-search prototypes over the CID 4 text and row datasets. It normalizes literature, patents, bioactivity rows, pathway records, taxonomy rows, and CPDat rows into a shared document shape, generates deterministic hashed-token embeddings, and writes a JSON summary into `data/out`.

Run it from the `py` workspace:

```sh
source .venv/bin/activate
export DATA_DIR="$(pwd)/../data"
python src/cid4_pgvector.py
```

If the pgvector dependencies are not installed or `PGVECTOR_DSN` is not set, the runner still completes and writes a dry-run summary instead of failing. Enable the optional dependency with:

```sh
uv sync --extra pgvector
```

Environment variables:
- `PGVECTOR_DSN` - PostgreSQL connection string for a database with the `vector` extension available
- `PGVECTOR_TABLE` - optional target table name, default `cid4_documents`
- `PGVECTOR_EMBED_DIM` - optional hashed embedding dimension, default `96`

Expected output under `data/out`:
- `cid4_pgvector.summary.json`

The current embedding provider is intentionally lightweight and deterministic so the pipeline stays testable and CI-friendly. It is good enough for schema, ingestion, and hybrid-query prototyping, and can later be replaced with a stronger embedding model without changing the PostgreSQL storage contract.

## LangChain runner
The Python workspace now also includes a LangChain-oriented RAG and routing runner for CID 4. It sits on top of the existing document shaping and pgvector work, writes JSON summaries into `data/out`, and supports:
- literature RAG over titles, abstracts, and citation metadata
- assay QA over bioactivity rows with metadata-aware retrieval
- pathway and reaction explanation
- taxonomy lookup and explanation
- a small rule-based multi-tool router for multi-source CID 4 questions

Run it from the `py` workspace:

```sh
source .venv/bin/activate
export DATA_DIR="$(pwd)/../data"
python src/cid4_langchain.py
```

Enable the optional dependency with:

```sh
uv sync --extra langchain
```

If LangChain is not installed or `PGVECTOR_DSN` is not set, the runner still completes. It falls back to an in-memory hashed-token retriever and writes explicit runtime metadata showing whether the full LangChain path was active.

Expected outputs under `data/out`:
- `cid4_langchain.literature.summary.json`
- `cid4_langchain.assay.summary.json`
- `cid4_langchain.pathway.summary.json`
- `cid4_langchain.taxonomy.summary.json`
- `cid4_langchain.agent.summary.json`

## LangGraph runner
The Python workspace now also includes a LangGraph-oriented stateful workflow runner for multi-hop CID 4 questions. It reuses the existing LangChain retrieval layer and adds:
- a compound grounding node sourced from `COMPOUND_CID_4.json`
- a router workflow over the main CID 4 evidence families
- an assay-plus-literature evidence chain
- a pathway-plus-taxonomy explainer with explicit validation
- provenance-aware JSON summaries under `data/out`

Run it from the `py` workspace:

```sh
source .venv/bin/activate
export DATA_DIR="$(pwd)/../data"
python src/cid4_langgraph.py
```

Enable the optional dependency with:

```sh
uv sync --extra langgraph
```

If LangGraph is not installed or `PGVECTOR_DSN` is not set, the runner still completes. It falls back to deterministic in-process graph execution and records runtime metadata showing whether the full LangGraph stack was active.

Expected outputs under `data/out`:
- `cid4_langgraph.router.summary.json`
- `cid4_langgraph.assay_literature.summary.json`
- `cid4_langgraph.pathway_taxonomy.summary.json`
- `cid4_langgraph.compound_context.summary.json`

The validation step in the LangGraph workflows checks that the final answer stays grounded in retrieved evidence families and carries identifiers such as AIDs, PMIDs, pathway accessions, or taxonomy IDs when those are expected.

## Apache AGE runner
The Python workspace now also includes an Apache AGE-oriented property-graph runner for CID 4. It reuses the existing conformer and CSV loaders, normalizes the main graph families, generates Cypher ingestion statements, and writes a graph summary into `data/out`.

Run it from the `py` workspace:

```sh
source .venv/bin/activate
export DATA_DIR="$(pwd)/../data"
python src/cid4_age.py
```

Enable the optional PostgreSQL client dependency with:

```sh
uv sync --extra apache-age
```

If `AGE_DSN` is not set or Apache AGE is not available on the target PostgreSQL instance, the runner still completes. It falls back to a dry-run summary that reports node and edge counts, sample Cypher statements, and example multi-hop queries.

Environment variables:
- `AGE_DSN` - PostgreSQL connection string for an instance where the Apache AGE extension is installed
- `AGE_GRAPH_NAME` - optional AGE graph name, default `cid4_graph`

Expected output under `data/out`:
- `cid4_age.summary.json`

The current AGE slice covers the main graph families from the README:
- molecular graph from `Conformer3D_COMPOUND_CID_4(1).json`
- canonical 2D fallback graph from `Structure2D_COMPOUND_CID_4.json`
- compound-to-organism graph from `cid_4.dot` and `pubchem_cid_4_consolidatedcompoundtaxonomy.csv`
- pathway-reaction graph from `pubchem_cid_4_pathway.csv` and `pubchem_cid_4_pathwayreaction.csv`
- assay-target graph from `pubchem_cid_4_bioactivity.csv`
 
## Cryptography runner
The Python workspace now also includes a cryptography-oriented runner for integrity, encryption, signatures, password hashing, and certificate workflows over real CID 4 artifacts.

Run it from the `py` workspace:

```sh
source .venv/bin/activate
export DATA_DIR="$(pwd)/../data"
python src/cid4_crypto.py
```

Enable the optional dependency with:

```sh
uv sync --extra crypto
```

If the crypto dependencies are not installed, the runner still completes and writes explicit `skipped` sections for the unavailable examples instead of failing.

The runner covers these programming-language examples:
- file hashing with SHA-256, SHA-512, BLAKE2b, and MD5 compatibility digests
- HMAC-SHA256 over generated manifest files
- password hashing with Argon2id, bcrypt, scrypt, and PBKDF2-HMAC-SHA256
- symmetric authenticated encryption with AES-256-GCM and ChaCha20-Poly1305
- asymmetric signatures with RSA-PSS, ECDSA P-256, and Ed25519
- asymmetric encryption and key exchange with RSA-OAEP and X25519 hybrid encryption
- X.509 certificate generation and PKCS#12 bundle export for JVM interoperability

Expected outputs under `data/out/crypto`:
- `cid4_crypto.manifest.json`
- `cid4_crypto.summary.json`
- `cid4_crypto.demo.key.pem`
- `cid4_crypto.demo.cert.pem`
- `cid4_crypto.demo.keystore.p12`

Environment variables:
- `CID4_CRYPTO_DEMO_PASSWORD` - optional password used for encrypted private-key and PKCS#12 demo artifacts. If unset, the runner generates a one-time random password and records that it was generated in the summary.

The cryptography section is intentionally split between Python code examples and CLI interoperability examples. The Python runner generates and verifies the artifacts. The CLI examples show how to inspect or consume equivalent materials with common tools.

Representative CLI examples:

```sh
sha256sum data/COMPOUND_CID_4.json
md5 data/COMPOUND_CID_4.json

openssl x509 -in data/out/crypto/cid4_crypto.demo.cert.pem -text -noout
openssl pkcs12 -info -in data/out/crypto/cid4_crypto.demo.keystore.p12 -nokeys
openssl x509 -pubkey -noout -in data/out/crypto/cid4_crypto.demo.cert.pem > cid4_crypto.demo.pubkey.pem
openssl dgst -sha256 -verify cid4_crypto.demo.pubkey.pem -signature data/out/crypto/cid4_crypto.manifest.sig data/out/crypto/cid4_crypto.manifest.json

gpg --armor --detach-sign data/out/crypto/cid4_crypto.manifest.json
age-keygen -o cid4-demo.agekey
age -r <recipient> -o cid4_crypto.manifest.json.age data/out/crypto/cid4_crypto.manifest.json

keytool -list -v -storetype PKCS12 -keystore data/out/crypto/cid4_crypto.demo.keystore.p12
keytool -importkeystore -srckeystore data/out/crypto/cid4_crypto.demo.keystore.p12 -srcstoretype PKCS12 -destkeystore cid4-demo.jks -deststoretype JKS
```

Algorithm guidance:
- Prefer Argon2id for new password hashing.
- Prefer AES-GCM or ChaCha20-Poly1305 for symmetric encryption.
- Prefer Ed25519 and X25519 for new signature or key-exchange examples where interoperability allows it.
- Keep RSA, ECDSA, PKCS#12, and `keytool` because they are still common in enterprise and JVM environments.
- Treat MD5 as compatibility-only. It is included for legacy checksum examples, not for security.


def tokenize_preserving_chemistry(text: str) -> list[str]:
	normalized = normalize_text(text)
	return TOKEN_PATTERN.findall(normalized)


def lowercase_tokens(tokens: Iterable[str]) -> list[str]:
	return [token.lower() for token in tokens if token]


def filter_stopwords(tokens: Iterable[str], stopwords: set[str] | None = None) -> list[str]:
	vocabulary = BASE_STOPWORDS if stopwords is None else stopwords
	filtered: list[str] = []
	for token in tokens:
		lowered = token.lower()
		if lowered in CHEMISTRY_ALLOWLIST:
			filtered.append(lowered)
			continue
		if lowered in vocabulary:
			continue
		filtered.append(lowered)
	return filtered


def build_document_text(frame: Any, columns: list[str]) -> list[str]:
	documents: list[str] = []
	for _, row in frame.iterrows():
		parts = [normalize_text(row.get(column, "")) for column in columns]
		joined = " ".join(part for part in parts if part)
		if joined:
			documents.append(joined)
	return documents


def stable_top_items(items: dict[str, int | float], limit: int) -> list[dict[str, int | float | str]]:
	ranked = sorted(items.items(), key=lambda item: (-float(item[1]), item[0]))
	return [{"item": key, "value": value} for key, value in ranked[:limit]]
*** Add File: /Users/Artsem_Nikitsenka/projects/pubchem-cid4-analysis/py/src/nlp/nltk_workflows.py
from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from math import log2
from typing import Any

from nlp.datasets import (
	load_bioactivity_frame,
	load_literature_frame,
	load_pathway_reaction_frame,
	load_patent_frame,
	load_taxonomy_frame,
	load_toxicology_frame,
)
from nlp.text_processing import (
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
	nltk_module = import_nltk()
	if isinstance(nltk_module, dict):
		return nltk_module

	frame = load_literature_frame()
	documents = build_document_text(
		frame,
		["Title", "Abstract", "Keywords", "Citation", "Subject", "Publication_Name"],
	)
	analysis = analyze_documents(nltk_module, documents)
	analysis.update(
		{
			"status": "ok",
			"workflow": "literature",
			"row_count": int(len(frame)),
			"document_count": int(len(documents)),
			"notable_term_counts": count_specific_terms(
				analysis["tokens"], ["isopropanolamine", "fungicide", "pathway", "metabolism"]
			),
		}
	)
	del analysis["tokens"]
	return analysis


def run_literature_vs_patent_workflow() -> dict[str, Any]:
	nltk_module = import_nltk()
	if isinstance(nltk_module, dict):
		return nltk_module

	literature_documents = build_document_text(load_literature_frame(), ["Title", "Abstract", "Keywords", "Citation"])
	patent_documents = build_document_text(load_patent_frame(), ["title", "abstract"])

	literature_analysis = analyze_documents(nltk_module, literature_documents)
	patent_analysis = analyze_documents(nltk_module, patent_documents)

	literature_counter = Counter(literature_analysis["tokens"])
	patent_counter = Counter(patent_analysis["tokens"])
	distinctive_patent = distinctive_terms(patent_counter, literature_counter)
	distinctive_literature = distinctive_terms(literature_counter, patent_counter)

	result = {
		"status": "ok",
		"workflow": "literature-vs-patent",
		"literature_document_count": int(len(literature_documents)),
		"patent_document_count": int(len(patent_documents)),
		"literature_top_terms": literature_analysis["top_terms"],
		"patent_top_terms": patent_analysis["top_terms"],
		"literature_top_bigrams": literature_analysis["top_bigrams"],
		"patent_top_bigrams": patent_analysis["top_bigrams"],
		"distinctive_literature_terms": distinctive_literature,
		"distinctive_patent_terms": distinctive_patent,
	}
	return result


def run_bioactivity_workflow() -> dict[str, Any]:
	nltk_module = import_nltk()
	if isinstance(nltk_module, dict):
		return nltk_module

	frame = load_bioactivity_frame()
	documents = build_document_text(
		frame,
		["BioAssay_Name", "Target_Name", "Activity", "Activity_Type", "citations"],
	)
	analysis = analyze_documents(nltk_module, documents)
	analysis.update(
		{
			"status": "ok",
			"workflow": "bioactivity",
			"row_count": int(len(frame)),
			"notable_term_counts": count_specific_terms(
				analysis["tokens"], ["estrogen", "androgen", "cytochrome", "plasmodium", "yeast"]
			),
		}
	)
	del analysis["tokens"]
	return analysis


def run_taxonomy_workflow() -> dict[str, Any]:
	nltk_module = import_nltk()
	if isinstance(nltk_module, dict):
		return nltk_module

	frame = load_taxonomy_frame()
	source_tokens: list[str] = []
	normalized_pairs: list[dict[str, str | int]] = []
	for _, row in frame.iterrows():
		organism = normalize_text(row.get("Source_Organism", ""))
		taxonomy = normalize_text(row.get("Taxonomy", ""))
		tokens = prepare_tokens(nltk_module, f"{organism} {taxonomy}")
		source_tokens.extend(tokens)
		normalized_pairs.append(
			{
				"source_organism": organism,
				"taxonomy": taxonomy,
				"normalized_label": " ".join(tokens[:6]),
				"taxonomy_id": int(row.get("Taxonomy_ID")) if str(row.get("Taxonomy_ID", "")).strip() else -1,
			}
		)

	token_counter = Counter(source_tokens)
	return {
		"status": "ok",
		"workflow": "taxonomy",
		"row_count": int(len(frame)),
		"top_terms": stable_top_items(dict(token_counter), TOP_TERM_LIMIT),
		"normalization_preview": normalized_pairs[:10],
	}


def run_toxicology_workflow() -> dict[str, Any]:
	nltk_module = import_nltk()
	if isinstance(nltk_module, dict):
		return nltk_module

	frame = load_toxicology_frame()
	documents = build_document_text(frame, ["Effect", "Route", "Reference"])
	analysis = analyze_documents(nltk_module, documents)
	analysis.update(
		{
			"status": "ok",
			"workflow": "toxicology",
			"row_count": int(len(frame)),
			"route_counts": normalize_value_counts(frame["Route"]),
			"effect_counts": count_specific_terms(analysis["tokens"], ["behavioral", "somnolence", "diarrhea", "excitement"]),
		}
	)
	del analysis["tokens"]
	return analysis


def run_pathway_workflow() -> dict[str, Any]:
	nltk_module = import_nltk()
	if isinstance(nltk_module, dict):
		return nltk_module

	frame = load_pathway_reaction_frame()
	documents = build_document_text(frame, ["Equation", "Reaction", "Control", "Taxonomy"])
	analysis = analyze_documents(nltk_module, documents)
	analysis.update(
		{
			"status": "ok",
			"workflow": "pathway",
			"row_count": int(len(frame)),
			"notable_term_counts": count_specific_terms(
				analysis["tokens"], ["glutathione", "nadh", "aminoacetone", "1-amino-propan-2-ol"]
			),
		}
	)
	del analysis["tokens"]
	return analysis


def analyze_documents(nltk_module: Any, documents: Iterable[str]) -> dict[str, Any]:
	all_tokens: list[str] = []
	all_stems: list[str] = []

	for document in documents:
		tokens = prepare_tokens(nltk_module, document)
		all_tokens.extend(tokens)
		all_stems.extend(stem_tokens(nltk_module, tokens))

	frequency = nltk_module.FreqDist(all_tokens)
	top_terms = [{"term": term, "count": int(count)} for term, count in frequency.most_common(TOP_TERM_LIMIT)]
	top_bigrams = extract_top_bigrams(nltk_module, all_tokens)

	return {
		"token_count": int(len(all_tokens)),
		"unique_token_count": int(len(set(all_tokens))),
		"top_terms": top_terms,
		"top_bigrams": top_bigrams,
		"top_stems": stable_top_items(dict(Counter(all_stems)), TOP_TERM_LIMIT),
		"tokens": all_tokens,
	}


def prepare_tokens(nltk_module: Any, text: str) -> list[str]:
	raw_tokens = tokenize_preserving_chemistry(text)
	lowered = lowercase_tokens(raw_tokens)
	stopwords = nltk_stopwords(nltk_module)
	filtered = filter_stopwords(lowered, stopwords)
	return [token for token in filtered if token and not token.isdigit()]


def stem_tokens(nltk_module: Any, tokens: Iterable[str]) -> list[str]:
	stemmer = nltk_module.PorterStemmer()
	stems: list[str] = []
	for token in tokens:
		if token in CHEMISTRY_ALLOWLIST or any(character.isdigit() for character in token):
			stems.append(token)
			continue
		stems.append(stemmer.stem(token))
	return stems


def extract_top_bigrams(nltk_module: Any, tokens: list[str]) -> list[dict[str, int | str]]:
	if len(tokens) < 2:
		return []
	finder = nltk_module.collocations.BigramCollocationFinder.from_words(tokens)
	finder.apply_freq_filter(2)
	scored = finder.score_ngrams(nltk_module.BigramAssocMeasures().pmi)
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
		score = log2(primary_share / reference_share)
		rows.append(
			{
				"term": term,
				"count": int(count),
				"log_ratio": float(score),
			}
		)
	rows.sort(key=lambda item: (-float(item["log_ratio"]), str(item["term"])))
	return rows[:TOP_DISTINCTIVE_LIMIT]


def normalize_value_counts(series: Any) -> dict[str, int]:
	normalized = series.astype("string").fillna("Unknown").str.strip().replace("", "Unknown")
	counts = normalized.value_counts().to_dict()
	return {str(key): int(value) for key, value in counts.items()}


def nltk_stopwords(nltk_module: Any) -> set[str]:
	try:
		return set(nltk_module.corpus.stopwords.words("english"))
	except LookupError:
		download_nltk_resource(nltk_module, "corpora/stopwords", "stopwords")
		try:
			return set(nltk_module.corpus.stopwords.words("english"))
		except LookupError:
			from nlp.text_processing import BASE_STOPWORDS

			return set(BASE_STOPWORDS)


def import_nltk() -> Any:
	try:
		import nltk
		from nltk import FreqDist
		from nltk import PorterStemmer
		from nltk.metrics import BigramAssocMeasures
		from nltk import collocations

		nltk.FreqDist = FreqDist
		nltk.PorterStemmer = PorterStemmer
		nltk.BigramAssocMeasures = BigramAssocMeasures
		nltk.collocations = collocations
		return nltk
	except (ImportError, ModuleNotFoundError) as exc:
		return {
			"status": "skipped",
			"reason": f"NLTK is not installed in the current environment: {exc}",
		}


def download_nltk_resource(nltk_module: Any, locator: str, resource_name: str) -> None:
	try:
		nltk_module.data.find(locator)
		return
	except LookupError:
		nltk_module.download(resource_name, quiet=True)
*** Add File: /Users/Artsem_Nikitsenka/projects/pubchem-cid4-analysis/py/src/cid4_nltk.py
from __future__ import annotations

import json
import logging as log
from pathlib import Path

import env_utils
import fs_utils
import log_settings
from ml.common import to_builtin
from nlp.nltk_workflows import (
	run_bioactivity_workflow,
	run_literature_vs_patent_workflow,
	run_literature_workflow,
	run_pathway_workflow,
	run_taxonomy_workflow,
	run_toxicology_workflow,
)


def resolve_output_directory() -> Path:
	data_dir = Path(env_utils.get_data_dir())
	output_directory = data_dir / "out"
	fs_utils.create_dir_if_doesnt_exist(str(output_directory))
	return output_directory


def write_json(path: Path, payload: dict) -> None:
	with path.open("w", encoding="utf-8") as file:
		json.dump(to_builtin(payload), file, indent=2)


def write_nltk_analysis() -> None:
	output_directory = resolve_output_directory()
	outputs = {
		"cid4_nltk.literature.summary.json": run_literature_workflow(),
		"cid4_nltk.literature_vs_patent.summary.json": run_literature_vs_patent_workflow(),
		"cid4_nltk.bioactivity.summary.json": run_bioactivity_workflow(),
		"cid4_nltk.taxonomy.summary.json": run_taxonomy_workflow(),
		"cid4_nltk.toxicology.summary.json": run_toxicology_workflow(),
		"cid4_nltk.pathway.summary.json": run_pathway_workflow(),
	}

	for filename, payload in outputs.items():
		write_json(output_directory / filename, payload)
		log.info("NLTK summary written to %s", output_directory / filename)


if __name__ == "__main__":
	log_settings.configure_logging()
	write_nltk_analysis()
*** Add File: /Users/Artsem_Nikitsenka/projects/pubchem-cid4-analysis/py/tests/test_nltk_workflows.py
from __future__ import annotations

import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
	sys.path.insert(0, str(SRC_ROOT))

from nlp.nltk_workflows import analyze_documents, import_nltk, run_literature_workflow  # noqa: E402
from nlp.text_processing import filter_stopwords, tokenize_preserving_chemistry  # noqa: E402


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
		original_import = __import__

		def fake_import(name: str, *args: object, **kwargs: object) -> object:
			if name == "nltk":
				raise ModuleNotFoundError("No module named 'nltk'")
			return original_import(name, *args, **kwargs)

		with patch("builtins.__import__", side_effect=fake_import):
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
		fake_frame = types.SimpleNamespace(
			iterrows=lambda: iter(
				[
					(
						0,
						{
							"Title": "Isopropanolamine fungicide report",
							"Abstract": "Pathway metabolism study",
							"Keywords": "fungicide, metabolism",
							"Citation": "PMID 1",
							"Subject": "Chemistry",
							"Publication_Name": "Journal",
						},
					)
				]
			),
			__len__=lambda self: 1,
		)

		with patch("nlp.nltk_workflows.import_nltk", return_value=fake_nltk), patch(
			"nlp.nltk_workflows.load_literature_frame", return_value=fake_frame
		):
			result = run_literature_workflow()

		self.assertEqual(result["status"], "ok")
		self.assertEqual(result["workflow"], "literature")


if __name__ == "__main__":
	unittest.main()
