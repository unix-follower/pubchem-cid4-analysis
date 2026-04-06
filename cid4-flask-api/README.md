## Flask server
Install the dependencies:
```sh
uv sync
```

Run it from the `cid4-flask-api` directory:

```sh
source .venv/bin/activate
export DATA_DIR="$(pwd)/../data"
python src/main.py
```

TLS configuration is shared with the other Python runners:
- `FLASK_HOST` overrides the bind host for the Flask runner
- `FLASK_PORT` overrides the bind port for the Flask runner
- `SERVER_HOST` defaults to `0.0.0.0`
- `SERVER_PORT`, or `PORT` defaults to `8443`
- `TLS_CERT_FILE`, `TLS_KEY_FILE`, and optional `TLS_KEY_PASSWORD` can be set explicitly
- `OBSERVABILITY_ENABLED` toggle the Flask observability runtime
- `LOGGING_ENABLED`, `METRICS_ENABLED`, and `TRACING_ENABLED` override the generic observability toggles for Flask
- `LOG_LEVEL` overrides the observability logger level
- `METRICS_HOST` and `METRICS_PORT` configure the separate Prometheus scrape listener, which defaults to `0.0.0.0:9464`
- `SERVICE_NAME` overrides the default service label `pubchem-cid4-flask`

If explicit TLS files are not set, the Flask server falls back to the PEM certificate, encrypted private key, and demo password recorded in `data/out/crypto/cid4_crypto.summary.json`.

Quick verification:

```sh
curl -k https://localhost:8443/api/health
curl -k https://localhost:8443/api/cid4/compound
curl -k https://localhost:8443/api/algorithms/bioactivity
curl -k "https://localhost:8443/api/health?mode=error"
curl -isk https://localhost:8443/api/health
curl -s http://localhost:9464/metrics | grep -E 'cid4_http_requests_total|cid4_http_request_errors_total|cid4_http_request_duration_milliseconds|cid4_process_up'
```

Successful and handled-error responses include `X-Request-Id`, `X-Trace-Id`, `X-Span-Id`, and `traceparent` headers. Flask request-completed log lines include the normalized route, status, duration, and correlation identifiers, and Prometheus metrics are exposed on the separate listener.

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
- a PNG plot of representative reference Hill curves using `Activity_Value` as the inferred half-maximal concentration scale.

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
