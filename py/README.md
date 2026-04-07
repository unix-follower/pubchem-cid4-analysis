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
- `FASTAPI_OBSERVABILITY_ENABLED` or `OBSERVABILITY_ENABLED` toggle the FastAPI observability runtime
- `FASTAPI_LOGGING_ENABLED`, `FASTAPI_METRICS_ENABLED`, and `FASTAPI_TRACING_ENABLED` override the generic observability toggles for FastAPI
- `FASTAPI_LOG_LEVEL` overrides the observability logger level
- `FASTAPI_METRICS_HOST` and `FASTAPI_METRICS_PORT` configure the separate Prometheus scrape listener, which defaults to `0.0.0.0:9464`
- `FASTAPI_SERVICE_NAME` overrides the default service label `pubchem-cid4-fastapi`

If explicit TLS files are not set, the server falls back to the PEM certificate, encrypted private key, and demo password recorded in `data/out/crypto/cid4_crypto.summary.json`.

Quick verification:

```sh
curl -k https://localhost:8443/api/health
curl -k https://localhost:8443/api/cid4/structure/2d
curl -k https://localhost:8443/api/cid4/conformer/1
curl -k https://localhost:8443/api/algorithms/pathway
curl -k "https://localhost:8443/api/health?mode=error"
curl -isk https://localhost:8443/api/health
curl -s http://localhost:9464/metrics | grep -E 'cid4_http_requests_total|cid4_http_request_errors_total|cid4_http_request_duration_milliseconds|cid4_process_up'
```

Successful and handled-error responses now include `X-Request-Id`, `X-Trace-Id`, `X-Span-Id`, and `traceparent` headers. FastAPI request-completed log lines include the normalized route, status, duration, and correlation identifiers, and Prometheus metrics are exposed on the separate listener.

FastAPI also now includes a small custom LLM workflow behind three shared endpoints plus two streaming transports:
- `GET /api/llm/status` reports backend availability, whether a trained artifact exists, and where the checkpoint and metadata files are expected for the selected framework.
- `POST /api/llm/train` trains a small GRU-based character language model from the existing CID4 domain documents and writes artifacts under `data/out`.
- `POST /api/llm/generate` loads the trained artifact and generates text continuations from a prompt.
- `POST /api/llm/generate/stream` streams generation events over Server-Sent Events.
- `WS /ws/llm/generate` streams generation events over WebSocket.

The LLM feature reuses the existing CID4 text corpora from the literature, patent, assay, pathway, taxonomy, and product-use datasets. It is intentionally narrow: the current implementation is a small repo-local model, not a general-purpose foundation model. The same FastAPI routes now support both `pytorch` and `tensorflow` backends through a `framework` selector, and requests default to `pytorch` when the field is omitted. The new streaming routes emit a shared event model with `start`, `token`, `complete`, and `error` messages.

FastAPI now also mounts a first MCP server at `POST/GET /mcp/`. The first implementation exposes read-oriented CID4 tools and resources over MCP Streamable HTTP and reuses the existing FastAPI auth model. HTTP clients should authenticate first through the existing auth routes, then connect to the MCP endpoint with the session cookie. The initial tool set is intentionally narrow and grounded: compound metadata, question routing, domain retrieval, grounded answer synthesis, and grounded-answer validation.

To enable the training and generation endpoints, install both the FastAPI extra and the existing deep-learning dependency group:

```sh
uv sync --extra fastapi --group deep-learning
```

To enable local MCP development tooling, also install the MCP extra:

```sh
uv sync --extra fastapi --extra mcp
```

If the selected backend is not installed in the active environment, `GET /api/llm/status` still works and reports the backend-specific availability field such as `torch_available: false` or `tensorflow_available: false`, while the train and generate endpoints return an explicit JSON error instead of failing at import time.

Example requests:

```sh
curl -k https://localhost:8443/api/llm/status
curl -k 'https://localhost:8443/api/llm/status?framework=tensorflow'
curl -k -X POST https://localhost:8443/api/llm/train \
	-H 'Content-Type: application/json' \
	-d '{
		"framework": "pytorch",
		"domains": ["literature", "assay", "pathway"],
		"output_name": "cid4_demo_lm",
		"epochs": 4,
		"sequence_length": 48,
		"batch_size": 16,
		"max_chars": 20000
	}'
curl -k -X POST https://localhost:8443/api/llm/train \
	-H 'Content-Type: application/json' \
	-d '{
		"framework": "tensorflow",
		"domains": ["literature", "taxonomy"],
		"output_name": "cid4_demo_tf_lm",
		"epochs": 4,
		"sequence_length": 48,
		"batch_size": 16,
		"max_chars": 20000
	}'
curl -k -X POST https://localhost:8443/api/llm/generate \
	-H 'Content-Type: application/json' \
	-d '{
		"framework": "pytorch",
		"model_name": "cid4_demo_lm",
		"prompt": "CID 4 literature summary:",
		"max_new_tokens": 120,
		"temperature": 0.8,
		"top_k": 8
	}'
curl -N -k -X POST https://localhost:8443/api/llm/generate/stream \
	-H 'Content-Type: application/json' \
	-d '{
		"framework": "pytorch",
		"model_name": "cid4_demo_lm",
		"prompt": "CID 4 literature summary:",
		"max_new_tokens": 40,
		"temperature": 0.8,
		"top_k": 8
	}'
```

Artifacts are written to `data/out` using framework-specific names so both backends can coexist. PyTorch uses `pytorch_llm_<model_name>.pt` plus metadata JSON, and TensorFlow uses `tensorflow_llm_<model_name>.keras` plus metadata JSON. The status route reports the exact artifact paths for the selected framework and model name.

Streaming response contracts:
- SSE emits `event: start`, repeated `event: token`, and a final `event: complete` frame, or `event: error` if generation cannot start.
- WebSocket accepts one JSON request after connect and responds with the same logical event payloads as JSON messages.

## MCP server

The Python workspace now includes a CID4 MCP server with two entry modes:

- Embedded Streamable HTTP under the FastAPI app at `https://localhost:8443/mcp/`
- Local stdio mode via `python src/cid4_mcp.py`

Install the MCP dependencies:

```sh
uv sync --extra fastapi --extra mcp
```

Run the local stdio server from the `py` workspace:

```sh
source .venv/bin/activate
export DATA_DIR="$(pwd)/../data"
python src/cid4_mcp.py
```

The initial MCP surface is read-focused:

- Resource `cid4://compound/4`
- Resource `cid4://capabilities`
- Tool `get_compound_metadata`
- Tool `route_question`
- Tool `retrieve_documents`
- Tool `answer_question`
- Tool `validate_grounded_answer`

HTTP MCP access reuses the existing CID4 auth model. For browser or HTTP clients, authenticate first with the existing FastAPI auth flow, then connect to `/mcp/` with the issued session cookie. The mounted MCP endpoint rejects unauthenticated requests with `401` instead of redirecting.

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
