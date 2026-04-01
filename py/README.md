## Run
```sh
source .venv/bin/activate
export DATA_DIR="$(pwd)/../data"
python src/cid4_analysis.py
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

If XGBoost is not yet installed in the active environment, the runner writes an explicit `skipped` result for the boosted-tree summaries rather than failing the rest of the ML analysis.

For the mixed deliverable, a notebook companion can inspect the generated JSON summaries and reuse the shared `ml` package directly instead of duplicating feature engineering logic. The runner now also writes `cid4_ml.future_scaffolds.summary.json`, which captures the honest blockers and next code targets for a real graph-neural-network or SMILES-RNN implementation.

Notebook companion:
- `src/cid4_ml_taxonomy_text_baseline.ipynb` reuses `ml.datasets.build_taxonomy_clustering_frame()` to build a small TF-IDF plus logistic-regression baseline over the taxonomy text, then saves notebook artifacts back into `data/out`
