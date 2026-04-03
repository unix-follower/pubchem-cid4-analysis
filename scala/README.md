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

The same run also writes a bond-angle analysis JSON artifact for the active conformer:
- bonded angles $A$-$B$-$C$ derived from the 3D coordinates using the dot-product formula, where $A$-$B$ and $B$-$C$ are bonded and $B$ is the central atom

The same run now also writes a spring-bond potential JSON artifact for the active conformer:
- per-bond harmonic spring records using $E_{ij} = 0.5 k_{ij}(d_{ij} - d0_{ij})^2$ with chemistry-informed reference lengths keyed by atom symbols and bond order
- Cartesian partial derivatives $\partial E / \partial x_i$, $\partial E / \partial y_i$, and $\partial E / \partial z_i$ for each bonded atom pair, along with per-atom aggregated gradient vectors and gradient-balance statistics

This spring-bond analysis is an educational local-geometry diagnostic rather than a production force field: it uses bond-order-specific spring constants, uses a small lookup table of common reference bond lengths with a covalent-radius fallback, and reports how the current 3D CID 4 conformer would change the harmonic bond energy under infinitesimal Cartesian displacements.

The same run now also writes a manual gradient-descent analysis from the atom feature matrix of the active CID 4 conformer:
- a CSV trace of per-epoch weight, gradient, summed squared error, and MSE for the no-intercept model $\hat{y} = wx$
- a summary JSON documenting the hand-derived gradient $\frac{\partial}{\partial w}\sum_i(y_i - wx_i)^2 = 2\sum_i x_i(wx_i - y_i)$ with atom mass as the feature and atomic number as the target
- a PNG loss curve across epochs
- a PNG scatter/fit plot for atom mass versus atomic number under the learned weight

This gradient-descent example is intentionally educational rather than general-purpose: it uses the full atom feature matrix of the CID 4 conformer as the dataset, treats `mass` as the single feature, treats `atomicNumber` as the target, optimizes a one-parameter no-intercept regression, and reports the closed-form least-squares solution alongside the iterative result as a numerical check.

The same run now also writes Scala bioactivity artifacts from `pubchem_cid_4_bioactivity.csv` under `DATA_DIR/out`:
- filtered IC50 rows with computed pIC50 as CSV
- summary JSON with row counts and descriptive statistics
- a PNG plot of `y = -log10(x)` across the observed IC50 range

The same run now also writes Hill/sigmoidal dose-response reference artifacts from `pubchem_cid_4_bioactivity.csv` under `DATA_DIR/out`:
- a CSV of positive numeric `Activity_Value` rows interpreted as inferred Hill-scale parameters `K`, including trapezoidal-rule AUC values for the inferred reference curves
- a summary JSON documenting the normalized Hill model `f(c) = c^n / (K^n + c^n)`, its derivatives, midpoint / inflection interpretation, and AUC integration settings
- a PNG plot of representative reference Hill curves using `Activity_Value` as the inferred half-maximal concentration scale

Because the CID 4 bioactivity CSV contains potency-style summary values rather than raw per-concentration response series, this Hill output is a reference-curve analysis rather than a nonlinear fit to experimental dose-response points. The implementation uses each positive numeric `Activity_Value` as an inferred `K` value, reports that the log-concentration midpoint occurs at `c = K`, and approximates AUC with the trapezoidal rule over an inferred concentration grid scaled relative to each row's `K`. For the default reference coefficient `n = 1`, there is no positive linear-concentration inflection point.

The same run now also writes positive-numeric `Activity_Value` descriptive statistics artifacts from `pubchem_cid_4_bioactivity.csv` under `DATA_DIR/out`:
- a CSV of retained rows where `Activity_Value` is numeric and strictly greater than 0
- a summary JSON with mean, sample variance, skewness, quantiles, and a Shapiro-Wilk status block
- a PNG diagnostic plot with a log-scale histogram and a normality-status panel

This Scala implementation matches the agreed positive-numeric filtering semantics from Python. For the current CID 4 dataset, only two rows are retained, so Shapiro-Wilk is not computable on sample-size grounds. The summary reports that explicitly. For larger datasets, the Scala service currently keeps the Shapiro-Wilk section structurally present but marks it as not computed until a dedicated Scala implementation is added.

The same run now also writes a Bayesian posterior bioactivity analysis from `pubchem_cid_4_bioactivity.csv` under `DATA_DIR/out`:
- a CSV of retained binary evidence rows where `Activity` is `Active` or `Inactive`
- a summary JSON for the posterior probability $P(\mathrm{Active} \mid \mathrm{CID}=4)$ using a conjugate Beta-Binomial update with prior $\mathrm{Beta}(1,1)$

This posterior output excludes rows with `Activity = Unspecified` from the binary update and reports their count separately in the summary metadata. The posterior parameters are computed as $\alpha_{post} = 1 + n_{active}$ and $\beta_{post} = 1 + n_{inactive}$, and the summary reports the posterior mean, median, variance, a 95% equal-tailed credible interval, and the posterior probability that the latent activity rate exceeds $0.5$.

The same run now also writes an `Activity` versus `Aid_Type` chi-square bioactivity analysis from `pubchem_cid_4_bioactivity.csv` under `DATA_DIR/out`:
- a contingency CSV over retained binary `Activity` rows and observed `Aid_Type` categories
- a summary JSON for a Pearson chi-square test of independence between `Activity` and `Aid_Type`

This chi-square output reuses the same binary `Activity = Active / Inactive` evidence filter as the posterior analysis, excluding `Unspecified` and other non-binary activity labels before the contingency table is built. `Aid_Type` values are trimmed and blank values are normalized to `Unknown`. If fewer than two observed `Activity` levels or fewer than two observed `Aid_Type` levels remain after filtering, the summary records that the chi-square test could not be meaningfully computed on the retained data slice instead of emitting a misleading test statistic.

The same run now also writes an assay-level binomial bioactivity analysis from `pubchem_cid_4_bioactivity.csv` under `DATA_DIR/out`:
- a CSV PMF table for $P(K = k)$ across $k = 0, \dots, n$ active assays
- a summary JSON documenting the assay-level trial definition, plug-in success probability, observed-tail probabilities, and representative assays

This binomial output operates on one Bernoulli trial per unique `BioAssay_AID` after excluding rows with `Activity = Unspecified`, consistent with the posterior feature. Each assay is resolved to `Active` if any retained row for that assay is `Active`; otherwise it is resolved to `Inactive`. The model uses the observed active-assay fraction $p = n_{active\ assays} / n_{assays}$ as a plug-in estimate and reports the full binomial PMF, cumulative probabilities at the observed active-assay count, the binomial mean and variance, and the PMF probability sum as a numerical check. This is a frequentist plug-in binomial model rather than a posterior-predictive model.

The same run now also writes atom-element entropy artifacts from the active CID 4 conformer under `DATA_DIR/out`:
- a CSV of O/N/C/H element counts, proportions, log proportions, and per-element Shannon contributions
- a summary JSON with entropy $H = -\sum p_i \log p_i$, normalized entropy, retained support, and any unexpected atom symbols
- a PNG bar chart of the O/N/C/H proportions with the entropy value in the title

This entropy analysis derives element symbols from the conformer atom model and computes the entropy sum only over the required O/N/C/H support from the README exercise. Unexpected elements are excluded from the entropy sum and reported separately.
