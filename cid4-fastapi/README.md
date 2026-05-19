## FastAPI server
```bash
# export SERVER_HOST='0.0.0.0'
# export SERVER_PORT=8443
export DATA_DIR="$(pwd)/../data"
export TLS_CERT_FILE=$DATA_DIR/out/crypto/cid4_crypto.demo.cert.pem
export TLS_KEY_FILE=$DATA_DIR/out/crypto/cid4_crypto.demo.key.pem
export TLS_KEY_PASSWORD=test
export DB_URL='postgresql+psycopg_async://chemist:chemist@192.168.64.2:5432/cid4_analysis?options=-csearch_path%3Dcid4,public,ag_catalog'
source .venv/bin/activate
# --wait-for-client
uv run python -Xfrozen_modules=off -m debugpy --listen 0.0.0.0:5678 src/cid4_fastapi.py

export SERVER_URL=https://localhost:18443
```

- `FASTAPI_OBSERVABILITY_ENABLED` or `OBSERVABILITY_ENABLED` toggle the FastAPI observability runtime
- `FASTAPI_LOGGING_ENABLED`, `FASTAPI_METRICS_ENABLED`, and `FASTAPI_TRACING_ENABLED` override the generic observability toggles for FastAPI
- `FASTAPI_LOG_LEVEL` overrides the observability logger level
- `FASTAPI_METRICS_HOST` and `FASTAPI_METRICS_PORT` configure the separate Prometheus scrape listener, which defaults to `0.0.0.0:9464`
- `FASTAPI_SERVICE_NAME` overrides the default service label `pubchem-cid4-fastapi`

If explicit TLS files are not set, the server falls back to the PEM certificate, encrypted private key, and demo password recorded in `data/out/crypto/cid4_crypto.summary.json`.

```bash
curl -vk $SERVER_URL/health/liveness
curl -vk $SERVER_URL/health/readiness
curl -s http://localhost:9464/metrics | grep -E 'cid4_http_requests_total|cid4_http_request_errors_total|cid4_http_request_duration_milliseconds|cid4_process_up'

curl -vk https://localhost:18443/api/v1/auth/me
curl -vk https://localhost:18443/api/v1/auth/basic/login
curl -vk -X POST https://localhost:18443/api/v1/auth/logout
curl -vk https://localhost:18443/api/v1/auth/digest/login
curl -vk https://localhost:18443/api/v1/auth/digest/challenge
curl -vk https://localhost:18443/api/v1/auth/session
curl -vk https://localhost:18443/api/v1/compound
curl -vk https://localhost:18443/api/v1/structure/2d
curl -vk https://localhost:18443/api/v1/conformer/1
curl -vk https://localhost:18443/api/v1/pathway
curl -vk https://localhost:18443/api/v1/bioactivity
curl -vk https://localhost:18443/api/v1/taxonomy
curl -vk https://localhost:18443/api/v1/reaction-network
curl -vk $SERVER_URL/api/v1/graph/oxygen-neighbors
curl -vk $SERVER_URL/api/v1/graph/oxygen-to-nitrogen-shortest-path
curl -vk $SERVER_URL/api/v1/graph/compound-assay-target-taxon-relation
curl -vk $SERVER_URL/api/v1/graph/compound-pathway-reaction-enzyme
curl -vk $SERVER_URL/api/v1/graph/count-organisms-by-source
curl -vk -X POST $SERVER_URL/api/v1/nlp/ask -H 'Content-Type: application/json' \
  -d '{
    "question": "What does the literature say about isopropanolamine fungicide activity?",
    "domains": ["literature"],
    "workflow": "literature-rag"
    }'
curl -vk -X POST $SERVER_URL/api/v1/nlp/ask -H 'Content-Type: application/json' \
  -d '{
    "question": "Which CID 4 assays involve estrogen receptor signaling?",
    "domains": ["assay"],
    "workflow": "assay-qa"
    }'
curl -vk -X POST $SERVER_URL/api/v1/nlp/ask -H 'Content-Type: application/json' \
  -d '{
    "question": "Which pathways involving CID 4 are linked to Trypanosoma brucei?",
    "domains": ["pathway"],
    "workflow": "pathway-explainer"
    }'
curl -vk -X POST $SERVER_URL/api/v1/nlp/ask -H 'Content-Type: application/json' \
  -d '{
    "question": "Which organisms in the dataset are birds?",
    "domains": ["taxonomy"],
    "workflow": "taxonomy-assistant"
    }'
curl -vk -X POST $SERVER_URL/api/v1/nlp/ask -H 'Content-Type: application/json' \
  -d '{
    "question": "Find literature and assays related to Plasmodium falciparum",
    "domains": ["literature", "assay"],
    "workflow": "multi-tool-agent"
    }'
curl -vk -X POST $SERVER_URL/api/v1/nlp/ask -H 'Content-Type: application/json' \
  -d '{
    "question": "Summarize pathway evidence for CID 4 in Trypanosoma brucei",
    "domains": ["pathway"],
    "workflow": "multi-tool-agent"
    }'
curl -vk -X POST $SERVER_URL/api/v1/nlp/ask -H 'Content-Type: application/json' \
  -d '{
    "question": "List likely product-use categories and supporting descriptions",
    "domains": [],
    "workflow": "multi-tool-agent"
    }'
curl -vk -X POST $SERVER_URL/api/v1/nlp/execute-graph -H 'Content-Type: application/json' \
  -d '{
    "question": "Find assays related to Plasmodium falciparum and summarize supporting literature",
    "workflow": "assay-plus-literature"
    }'
curl -vk -X POST $SERVER_URL/api/v1/nlp/execute-graph -H 'Content-Type: application/json' \
  -d '{
    "question": "What pathway evidence links CID 4 to Trypanosoma brucei?",
    "workflow": "pathway-plus-taxonomy"
    }'
curl -vk -X POST $SERVER_URL/api/v1/nlp/execute-graph -H 'Content-Type: application/json' \
  -d '{
    "question": "List likely product-use categories for CID 4 while keeping the answer grounded in the compound record",
    "workflow": "compound-context-assistant"
    }'
curl -vk -X POST $SERVER_URL/api/v1/nlp/execute-graph -H 'Content-Type: application/json' \
  -d '{
    "question": "",
    "workflow": "router-graph"
    }'
```

Example requests:

```bash
curl -ik https://localhost:18443/api/v1/llm/status
curl -ik 'https://localhost:18443/api/v1/llm/status?framework=tensorflow'
curl -ik -X POST https://localhost:18443/api/v1/llm/train \
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
curl -k -X POST https://localhost:18443/api/v1/llm/train \
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
curl -k -X POST https://localhost:18443/api/v1/llm/generate \
	-H 'Content-Type: application/json' \
	-d '{
		"framework": "pytorch",
		"model_name": "cid4_demo_lm",
		"prompt": "CID 4 literature summary:",
		"max_new_tokens": 120,
		"temperature": 0.8,
		"top_k": 8
	}'
curl -N -k -X POST https://localhost:18443/api/v1/llm/generate/stream \
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

Streaming response contracts:
- SSE emits `event: start`, repeated `event: token`, and a final `event: complete` frame, or `event: error` if generation cannot start.
- WebSocket accepts one JSON request after connect and responds with the same logical event payloads as JSON messages.

## MCP server

CID4 MCP server with two entry modes:

- Embedded Streamable HTTP under the FastAPI app at `https://localhost:18443/mcp/`
- Local stdio mode via `python src/cid4_mcp.py`

Run the local stdio server:

```sh
export DATA_DIR="$(pwd)/../data"
uv run python src/cid4_mcp.py
uv run python -m src.mcp_cid4.stdio_client
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

### Request example
#### Step 1. Initialize
```sh
curl -kv https://localhost:18443/mcp/ \
  -X POST \
  -u 'analyst:cid4-basic-password' \
  -H 'X-CID4-Auth-Method: basic' \
  -H 'Accept: application/json, text/event-stream' \
  -H 'Content-Type: application/json' \
  -H 'MCP-Protocol-Version: 2025-06-18' \
  -d '{
    "jsonrpc": "2.0",
    "id": "init-1",
    "method": "initialize",
    "params": {
      "protocolVersion": "2025-06-18",
      "capabilities": {},
      "clientInfo": {
        "name": "manual-curl",
        "version": "1.0.0"
      }
    }
  }'
```

#### Step 2. Send the initialized notification
```sh
# mcpSessionId=xxx
curl -kv https://localhost:18443/mcp/ \
  -X POST \
  -u 'analyst:cid4-basic-password' \
  -H 'X-CID4-Auth-Method: basic' \
  -H 'Accept: application/json, text/event-stream' \
  -H 'Content-Type: application/json' \
  -H 'MCP-Protocol-Version: 2025-06-18' \
  -H "Mcp-Session-Id: $mcpSessionId" \
  -d '{
    "jsonrpc": "2.0",
    "method": "notifications/initialized",
    "params": {}
  }'
```

#### List tools
```sh
curl -kv https://localhost:18443/mcp/ \
  -X POST \
  -u 'analyst:cid4-basic-password' \
  -H 'X-CID4-Auth-Method: basic' \
  -H 'Accept: application/json, text/event-stream' \
  -H 'Content-Type: application/json' \
  -H 'MCP-Protocol-Version: 2025-06-18' \
  -H "Mcp-Session-Id: $mcpSessionId" \
  -d '{
    "jsonrpc": "2.0",
    "id": "tools-1",
    "method": "tools/list",
    "params": {}
  }' | jq
```

#### Call get_compound_metadata
```sh
curl -kv https://localhost:18443/mcp/ \
  -X POST \
  -u 'analyst:cid4-basic-password' \
  -H 'X-CID4-Auth-Method: basic' \
  -H 'Accept: application/json, text/event-stream' \
  -H 'Content-Type: application/json' \
  -H 'MCP-Protocol-Version: 2025-06-18' \
  -H "Mcp-Session-Id: $mcpSessionId" \
  -d '{
    "jsonrpc": "2.0",
    "id": "call-1",
    "method": "tools/call",
    "params": {
      "name": "get_compound_metadata",
      "arguments": {}
    }
  }' | jq
```

#### Read the cid4://compound/4 resource
```sh
curl -kv https://localhost:18443/mcp/ \
  -X POST \
  -u 'analyst:cid4-basic-password' \
  -H 'X-CID4-Auth-Method: basic' \
  -H 'Accept: application/json, text/event-stream' \
  -H 'Content-Type: application/json' \
  -H 'MCP-Protocol-Version: 2025-06-18' \
  -H "Mcp-Session-Id: $mcpSessionId" \
  -d '{
    "jsonrpc": "2.0",
    "id": "resource-1",
    "method": "resources/read",
    "params": {
      "uri": "cid4://compound/4"
    }
  }' | jq
```

## LangGraph runner
Adds:
- a compound grounding node sourced from `COMPOUND_CID_4.json`
- a router workflow over the main CID 4 evidence families
- an assay-plus-literature evidence chain
- a pathway-plus-taxonomy explainer with explicit validation
- provenance-aware JSON summaries under `data/out`

```bash
export DATA_DIR="$(pwd)/../data"
uv run python src/cid4_langgraph.py
```

If LangGraph is not installed or `PGVECTOR_DSN` is not set, the runner still completes. It falls back to deterministic in-process graph execution and records runtime metadata showing whether the full LangGraph stack was active.

Expected outputs under `data/out`:
- `cid4_langgraph.router.summary.json`
- `cid4_langgraph.assay_literature.summary.json`
- `cid4_langgraph.pathway_taxonomy.summary.json`
- `cid4_langgraph.compound_context.summary.json`

The validation step in the LangGraph workflows checks that the final answer stays grounded in retrieved evidence families and carries identifiers such as AIDs, PMIDs, pathway accessions, or taxonomy IDs when those are expected.
