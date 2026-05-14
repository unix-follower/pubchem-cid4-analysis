## Format code
```shell
sbt scalafmt
```

## Run Scalafix
```shell
sbt scalafixAll
```

For consistent results with import rewrites, run Scalafix before Scalafmt.

## Run HTTPS API
```shell
sbt "run server"
sbt "run tomcat"
sbt "run netty"
sbt "run jdk"
```

The embedded Apache Tomcat server, the Netty 4 server, and the pure-JDK virtual-thread server all expose the same `/api/...` routes currently defined in the Angular MSW layer and serve them over TLS.

Server modes:
- `server` and `tomcat` start the embedded Tomcat implementation
- `netty` starts the Netty 4 implementation with the same endpoint surface
- `jdk`, `virtual`, and `loom` start the pure-JDK HTTPS implementation with virtual-thread request handling and JDK concurrency primitives only

Runtime configuration:
- `JDK_HOST` and `JDK_PORT` override bind address and port for the pure-JDK server
- `VTHREAD_HOST` and `VTHREAD_PORT` are also accepted by the pure-JDK server
- `JDK_IO_MODE` controls file-response I/O mode for the pure-JDK server and supports `blocking`, `nonblocking`, and `hybrid`
- `SERVER_HOST` defaults to `0.0.0.0`
- `SERVER_PORT` defaults to `8443`
- `TOMCAT_OBSERVABILITY_ENABLED` or `OBSERVABILITY_ENABLED` toggle the Tomcat observability runtime
- `TOMCAT_LOGGING_ENABLED`, `TOMCAT_METRICS_ENABLED`, and `TOMCAT_TRACING_ENABLED` override the generic observability toggles for Tomcat
- `TOMCAT_LOG_LEVEL` overrides the observability logger level
- `TOMCAT_METRICS_HOST` and `TOMCAT_METRICS_PORT` configure the separate Prometheus scrape listener, which defaults to `0.0.0.0:9464`
- `TOMCAT_SERVICE_NAME` overrides the default service label `pubchem-cid4-tomcat`
- `KEYSTORE_PATH` and `KEYSTORE_PASSWORD` can be set explicitly for TLS
- `KEYSTORE_TYPE` defaults to `PKCS12`
- `SECURITY_CONFIG_PATH` optionally points to the startup security properties file for the Tomcat server

If `KEYSTORE_PATH` and `KEYSTORE_PASSWORD` are not set, the server falls back to the PKCS#12 bundle recorded in `data/out/crypto/cid4_crypto.summary.json`.

## Tomcat security toggles

The Tomcat server now reads feature toggles from `conf/security.properties` before startup. Exactly one auth mode may be enabled at a time.

Available booleans:
- `security.cors.enabled`
- `security.xssHeaders.enabled`
- `security.csrf.enabled`
- `security.ssrf.enabled`
- `security.auth.oauth2.enabled`
- `security.auth.basic.enabled`
- `security.auth.digest.enabled`

Typical values in `conf/security.properties`:

```properties
security.cors.enabled=true
security.cors.allowedOrigins=https://ui.example.test
security.xssHeaders.enabled=true
security.csrf.enabled=false
security.ssrf.enabled=true

security.auth.oauth2.enabled=true
security.auth.oauth2.issuer=https://keycloak.example.test/realms/cid4
security.auth.oauth2.audience=cid4-api
security.auth.oauth2.realm=CID4 API

security.auth.basic.enabled=false
security.auth.digest.enabled=false
```

Basic and Digest auth can also read credentials from the properties file, but environment variables remain preferable for secrets.

## Security verification

### XSS headers

```shell
curl -isk https://localhost:8443/api/health \
&& printf '\n---\n' \
&& curl -isk https://localhost:8443/api/cid4/compound | grep -E 'Content-Security-Policy|X-Content-Type-Options|X-Frame-Options|Referrer-Policy'
```

### CSRF guidance

The current Tomcat API serves only `GET` and `OPTIONS`, so the `security.csrf.enabled` flag is documentation-oriented in this first pass rather than a token-enforcement mechanism. Use the following output format to confirm the current risk profile and response headers while reviewing browser-auth assumptions for Basic and Digest modes:

```shell
curl -isk https://localhost:8443/api/health \
&& printf '\n---\n' \
&& curl -isk -X OPTIONS -H 'Origin: https://ui.example.test' https://localhost:8443/api/cid4/compound
```

### CORS allowlist

```shell
curl -isk -H 'Origin: https://ui.example.test' https://localhost:8443/api/cid4/compound \
&& printf '\n---\n' \
&& curl -isk -H 'Origin: https://blocked.example.test' https://localhost:8443/api/cid4/compound
```

### OAuth2 / OpenID Connect with Keycloak

Acquire a Keycloak access token first, then run the protected-route checks:

```shell
export KC_TOKEN="$(curl -sk -X POST 'https://keycloak.example.test/realms/cid4/protocol/openid-connect/token' \
	-H 'Content-Type: application/x-www-form-urlencoded' \
	--data-urlencode 'grant_type=password' \
	--data-urlencode 'client_id=cid4-api' \
	--data-urlencode 'username=demo' \
	--data-urlencode 'password=demo-password' | jq -r '.access_token')" \
&& curl -isk https://localhost:8443/api/cid4/compound \
&& printf '\n---\n' \
&& curl -isk -H "Authorization: Bearer ${KC_TOKEN}" https://localhost:8443/api/cid4/compound
```

### Basic auth

```shell
curl -isk https://localhost:8443/api/cid4/compound \
&& printf '\n---\n' \
&& curl -isk -u demo:demo-password https://localhost:8443/api/cid4/compound
```

### Digest auth

```shell
curl -isk https://localhost:8443/api/cid4/compound \
&& printf '\n---\n' \
&& curl -isk --digest -u demo:demo-password https://localhost:8443/api/cid4/compound
```

### SSRF policy for Solr and Elasticsearch

When `security.ssrf.enabled=true`, only allowlisted schemes, hosts, and ports from `conf/security.properties` are accepted.

```shell
SOLR_URL=http://127.0.0.1:8983/solr sbt "run solr query" \
&& printf '\n---\n' \
&& ELASTICSEARCH_URL=http://127.0.0.1:9200 sbt "run elasticsearch query"
```

Data resolution:
- `DATA_DIR` is used when set
- otherwise the server looks for the repository `data/` directory relative to the Scala project

Quick verification:
```shell
curl -k https://localhost:8443/api/health \
&& printf '\n---\n' \
&& curl -k "https://localhost:8443/api/health?mode=error" \
&& printf '\n---\n' \
&& curl -k https://localhost:8443/api/cid4/structure/2d \
&& printf '\n---\n' \
&& curl -k https://localhost:8443/api/cid4/conformer/1 \
&& printf '\n---\n' \
&& curl -k https://localhost:8443/api/algorithms/pathway \
&& printf '\n---\n' \
&& curl -k https://localhost:8443/api/algorithms/bioactivity \
&& printf '\n---\n' \
&& curl -k https://localhost:8443/api/algorithms/taxonomy
```

Observability verification:
```shell
curl -isk https://localhost:8443/api/health \
&& printf '\n---\n' \
curl -isk 'https://localhost:8443/api/cid4/conformer/99' \
&& printf '\n---\n' \
curl -s http://localhost:9464/metrics | grep -E 'cid4_http_requests_total|cid4_http_request_errors_total|cid4_http_request_duration_milliseconds|cid4_process_up'
```

Successful and handled-error responses now include `X-Request-Id`, `X-Trace-Id`, `X-Span-Id`, and `traceparent` headers. The Tomcat runtime emits request-completed log lines with route, status, duration, and correlation identifiers, and exposes Prometheus text format on the separate metrics listener.

The Netty server and the pure-JDK server both reuse the same Scala route logic as Tomcat, so route behavior and payloads stay aligned.

The pure-JDK server avoids Servlet and other HTTP frameworks entirely. It uses:
- `com.sun.net.httpserver.HttpsServer` for HTTPS request handling
- `Executors.newVirtualThreadPerTaskExecutor()` for blocking-friendly request execution on virtual threads
- `CompletableFuture` plus `AsynchronousFileChannel` for non-blocking file-backed JSON responses

In `hybrid` mode, small file responses stay on the request virtual thread while larger file responses are read with asynchronous file I/O.

## Run adjacency matrix generation
```shell
sbt "run arrays json"
sbt "run guava json"
sbt "run tinkerpop json"
sbt "run jgrapht json"
sbt "run scala-graph json"
sbt "run jgrapht sdf"
```

The first argument is the adjacency `method` string parameter. The optional second argument is the distance-source selector and supports `json` and `sdf`.

Each run writes a distance-matrix JSON file, an adjacency-matrix JSON file, a matching eigendecomposition JSON file, and a Laplacian-analysis JSON file under `DATA_DIR/out`.

The same run also writes a bonded-distance comparison JSON artifact for the active conformer:
- bonded vs non-bonded inter-atom distance statistics derived from the 3D distance matrix and PubChem bond list

## Run Lucene indexing and example queries
```shell
sbt "run lucene"
sbt "run lucene all"
sbt "run lucene build"
sbt "run lucene query"
```

The Lucene mode builds one mixed index from the CID 4 literature, patent, bioactivity, taxonomy, pathway, pathway-reaction, and flattened compound-record sources listed in the top-level README.

Artifacts are written under `DATA_DIR/out/lucene`:
- `index/` — mixed Lucene index
- `cid4.lucene.index.summary.json` — document counts by `doc_type` and source file
- `cid4.lucene.query_examples.summary.json` — fixed example-query results for literature, patents, bioactivity, and pathway lookup

## Run Solr export and optional live queries
```shell
sbt "run solr"
sbt "run solr all"
sbt "run solr export"
sbt "run solr post"
sbt "run solr query"
```

The Solr mode reuses the Lucene document loaders to build one mixed Solr-ready corpus from literature, patents, bioactivity, taxonomy, pathway, pathway-reaction, CPDat, curated citations, and flattened compound-record data.

Artifacts are written under `DATA_DIR/out/solr`:
- `cid4.solr.docs.jsonl` — newline-delimited mixed Solr documents ready for `/update`
- `configsets/cid4/conf/` — exported Solr configset with schema, analyzers, and synonym rules
- `cid4.solr.summary.json` — export counts plus optional live ingest/query status and example query results

Optional live Solr settings:
- `SOLR_URL` — base Solr URL such as `http://localhost:8983/solr`
- `SOLR_COLLECTION` — target collection name, defaults to `cid4`

If `SOLR_URL` is not set, `sbt "run solr"` still writes the JSONL export and configset, then records the live ingest/query phase as `skipped` in the summary.

## Run Elasticsearch export and optional live queries
```shell
sbt "run elasticsearch"
sbt "run elasticsearch all"
sbt "run elasticsearch export"
sbt "run elasticsearch post"
sbt "run elasticsearch query"
```

The Elasticsearch mode reuses the Lucene document loaders to build one mixed JSON corpus from literature, patents, bioactivity, taxonomy, pathway, pathway-reaction, CPDat, curated citations, and flattened compound-record data.

Artifacts are written under `DATA_DIR/out/elasticsearch`:
- `cid4.elasticsearch.bulk.ndjson` — bulk-ready mixed Elasticsearch documents
- `config/` — exported index template, settings, and synonym rules
- `cid4.elasticsearch.summary.json` — export counts plus optional live ingest/query status and example query results

Optional live Elasticsearch settings:
- `ELASTICSEARCH_URL` — base Elasticsearch URL such as `http://localhost:9200`
- `ELASTICSEARCH_INDEX` — target index name, defaults to `cid4`
- `ELASTICSEARCH_API_KEY` — optional API key used as an `Authorization: ApiKey ...` header

If `ELASTICSEARCH_URL` is not set, `sbt "run elasticsearch"` still writes the NDJSON export and bundled config, then records the live ingest/query phase as `skipped` in the summary.

## Run OpenNLP corpus workflows
```shell
sbt "run opennlp"
sbt "run opennlp all"
sbt "run opennlp literature"
sbt "run opennlp patent"
sbt "run opennlp assay"
sbt "run opennlp pathway"
sbt "run opennlp taxonomy"
sbt "run opennlp cpdat"
sbt "run opennlp toxicology"
sbt "run opennlp springer"
```

The OpenNLP mode builds lightweight corpus summaries for literature, patents, assay text, pathway and reaction text, taxonomy strings, CPDat product-use rows, ChemIDplus toxicology rows, and Springer metadata.

Artifacts are written under `DATA_DIR/out/opennlp`:
- `cid4.opennlp.summary.json` — runtime configuration plus per-workflow summary paths
- `cid4.opennlp.<workflow>.summary.json` — token, sentence, phrase, and optional categorization summaries for each workflow

Optional OpenNLP settings:
- `OPENNLP_MODEL_DIR` — directory containing model binaries such as `en-sent.bin`, `en-token.bin`, `en-pos-maxent.bin`, and `en-chunker.bin`

If `OPENNLP_MODEL_DIR` is not set or some model binaries are missing, the workflows still run with a hybrid fallback strategy using regex sentence splitting, `SimpleTokenizer`, and n-gram phrase extraction. Document categorization is trained only for workflows that have useful labels in the underlying dataset.

The default `sbt "run lucene"` mode rebuilds the index and then executes the example query set. The existing adjacency, distance-matrix, spectrum, and bioactivity analysis runs remain unchanged when the first argument is not one of the Lucene modes.
