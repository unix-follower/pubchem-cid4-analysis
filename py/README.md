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

The same run now also writes a Bayesian posterior bioactivity analysis from `pubchem_cid_4_bioactivity.csv` into `data/out`:
- a CSV of retained binary evidence rows where `Activity` is `Active` or `Inactive`
- a summary JSON for the posterior probability $P(\mathrm{Active} \mid \mathrm{CID}=4)$ using a conjugate Beta-Binomial update with prior $\mathrm{Beta}(1,1)$

This posterior output excludes rows with `Activity = Unspecified` from the binary update and reports their count separately in the summary metadata. The posterior parameters are computed as $\alpha_{post} = 1 + n_{active}$ and $\beta_{post} = 1 + n_{inactive}$, and the summary reports the posterior mean, median, variance, a 95% equal-tailed credible interval, and the posterior probability that the latent activity rate exceeds $0.5$.

The same run now also writes an assay-level binomial bioactivity analysis from `pubchem_cid_4_bioactivity.csv` into `data/out`:
- a CSV of the binomial probability mass function over `k = 0..n` active assays
- a summary JSON for $P(K = k \text{ active assays in } n \text{ assays})$ using unique `BioAssay_AID` values as trials

This binomial output first reuses the same `Activity = Active / Inactive` binary evidence filter as the posterior analysis, excluding `Unspecified` rows before grouping by assay. The first-pass assay resolution rule is that an assay is counted as `Active` if any retained row for that `BioAssay_AID` is `Active`; otherwise it is `Inactive`. The success probability is then estimated as the observed assay-level active fraction $p = n_{active\_assays} / n_{assays}$, and the summary reports the PMF at the observed active-assay count, cumulative tail probabilities, the binomial mean $np$, and the variance $np(1-p)$.

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
