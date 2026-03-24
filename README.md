# pubchem-cid4-analysis

## Dataset: CID 4 — 1-Amino-2-propanol (C₃H₉NO)

The dataset contains:
- **Molecular structure** — 14 atoms (1 O, 1 N, 3 C, 9 H), 13 single bonds, 1 chiral center (R), 2D and 3D coordinates, per-atom properties (hybridization, mass, bond count, CIP rank)
- **Bioactivity** — 34-column CSV: activity values (IC50, potency), active/inactive classifications across multiple assays (Tox21 ER-alpha, NCI, ChEMBL)
- **Food taxonomy** — 17 animal food sources (9 mammals, 8 birds) with NCBI taxonomy IDs
- **Graph** — DOT directed graph: compound → species associations with two subgraph clusters (mammals, birds)
- **Pathway** — Glutathione Metabolism III (E. coli)

---

## 1. Mathematics

### Algebra
| Exercise | Data used |
|---|---|
| Compute molecular weight: $M = 3(12.011) + 9(1.008) + 14.007 + 15.999$ | `out/cid4-sdf-extracted.json` → per-atom mass values |
| Write and balance chemical equations for reactions of the amino alcohol | Atom counts from Conformer3D_COMPOUND_CID_4.json |
| Set operations on taxonomy IDs: union/intersection of mammal vs bird taxon ID sets | `pubchem_cid_4_consolidatedcompoundtaxonomy.csv` → `Taxonomy_ID` column |
| Polynomial: fit a degree-2 polynomial to `Activity_Value` vs `BioAssay_AID` (numerical index) | `pubchem_cid_4_bioactivity.csv` |

### Linear Algebra
| Exercise | Data used |
|---|---|
| Build a **14×14 adjacency matrix** of the molecular graph (atoms as nodes, `aid1`/`aid2` as edges) | Conformer3D_COMPOUND_CID_4.json → `bonds` |
| Build the **feature matrix** $X \in \mathbb{R}^{5 \times 6}$ for heavy atoms: columns = [atomic\_number, bond\_count, total\_H, valency, mass, hybridization\_encoded] | `out/cid4-sdf-extracted.json` |
| Compute **eigenvalues/eigenvectors** of the molecular adjacency matrix (graph spectrum — relates to molecular orbital theory) | adjacency matrix above |
| Build the **Laplacian** $L = D - A$ and find its null space (connected components) | same adjacency matrix |
| Build **18×18 adjacency matrix** for the taxonomy graph: 1 compound node + 17 species nodes | cid_4.dot |
| Compute the **distance matrix** between 3D atoms once you extract xyz coordinates from `Conformer3D_COMPOUND_CID_4.sdf` | `Conformer3D_COMPOUND_CID_4.sdf` |

### Pre-calculus
| Exercise | Data used |
|---|---|
| **Logarithmic transformation**: convert `Activity_Value` (IC50 in µM) to pIC50 = $-\log_{10}(\text{IC50})$ | `pubchem_cid_4_bioactivity.csv` → `Activity_Value` |
| Plot and analyze log-scale dose-response: sketch of $y = -\log_{10}(x)$ over IC50 range | same |
| Compute **3D inter-atom distances** using $d = \sqrt{(x_2-x_1)^2 + (y_2-y_1)^2 + (z_2-z_1)^2}$, compare bonded vs non-bonded atom pairs | SDF 3D coordinates + bond list |
| **Angle** between two bond vectors (e.g., N–C–O angle) via dot product formula | 3D atom coordinates |

### Calculus
| Exercise | Data used |
|---|---|
| Model the **Hill/sigmoidal dose-response** curve $f(c) = \frac{c^n}{K^n + c^n}$ and differentiate to find inflection point | `pubchem_cid_4_bioactivity.csv` → `Activity_Value` |
| **Gradient descent by hand**: derive gradient of MSE loss $\frac{\partial}{\partial w}\sum(y_i - wx_i)^2$ using atom mass as feature and atomic number as target | atom feature matrix |
| **Numerical integration** (trapezoidal rule) to approximate AUC (area under a dose-response curve) | activity values |
| Partial derivatives: $\frac{\partial E}{\partial x_i}$ for a simple spring bond potential $E = \frac{1}{2}k(d - d_0)^2$ between bonded atoms | 3D coordinates |

### Probability & Statistics
| Exercise | Data used |
|---|---|
| **Posterior probability** $P(\text{Active} \mid \text{CID=4})$ — Bayesian update over bioassay results | `pubchem_cid_4_bioactivity.csv` → `Activity` column (Active / Inactive / Unspecified) |
| **Binomial distribution**: model Active/Inactive outcomes across assays; compute $P(k \text{ actives in } n \text{ assays})$ | same |
| **Chi-square test**: Is `Activity` statistically independent of `Aid_Type`? | `bioactivity.csv` → `Activity` + `Aid_Type` |
| **Marginal/joint distributions** of taxonomy class (mammal vs bird) and species count | `consolidatedcompoundtaxonomy.csv` + cid_4.dot |
| Compute **mean, variance, skewness** of `Activity_Value`; test normality (Shapiro-Wilk) | `bioactivity.csv` → `Activity_Value` |
| **Entropy** $H = -\sum p_i \log p_i$ of atom element distribution: O, N, C, H proportions | atom element array |

---

## 2. Data Structures, Algorithms, Graph Theory & Machine Learning

### Data Structures
| Structure | Exercise |
|---|---|
| **Adjacency list** | Represent the 14-atom molecular graph (atom ID → list of bonded neighbors) from `bonds.aid1`/`bonds.aid2` |
| **Adjacency matrix** | Same molecular graph as a matrix; compare space/time trade-offs |
| **Hash map** | Atom ID → properties map (element, mass, hybridization) from `cid4-sdf-extracted.json` |
| **Nested dict / tree** | Parse `COMPOUND_CID_4.json`'s nested `Section` tree; write a recursive traversal |
| **Priority queue** | Dijkstra's on the taxonomy graph weighting edges by taxonomic distance |
| **Disjoint set (Union-Find)** | Find connected components of the molecular graph; useful if you zero out some bonds |

### Algorithms
| Algorithm | Exercise |
|---|---|
| **BFS** | Starting from atom 1 (O), traverse all atoms in breadth-first order; output atom sequence |
| **DFS** | Same; detect back-edges (would indicate ring closure — none here, but generalizes) |
| **Topological sort** | Apply to the DOT directed graph `cid4 → species`; apply to pathway reaction steps |
| **Shortest path (BFS/Dijkstra)** | Shortest bond path between O (atom 1) and N (atom 2) in the molecular graph |
| **Cycle detection** | Verify 1-Amino-2-propanol is **acyclic** using DFS coloring |
| **Minimum spanning tree (Kruskal/Prim)** | Use 3D inter-atom distances as edge weights to find the MST of the complete atom graph (should approximate bond skeleton) |
| **Sorting** | Sort bioassay records by `Activity_Value`; benchmark quicksort vs mergesort; sort organisms by `Taxonomy_ID` |
| **Binary search** | After sorting `Activity_Value`, binary-search for a threshold (e.g., find first IC50 ≤ 100 µM) |
| **Hash-based dedup** | Deduplicate `pubchem_cid_4_consolidatedcompoundtaxonomy.csv` by `Source_Organism` |

### Graph Theory (Deep Dive)
The dataset gives you **two distinct graphs** to work with:

**Graph 1 — Molecular graph** (from Conformer3D_COMPOUND_CID_4.json)
- 14 nodes (atoms), 13 edges (bonds), undirected, unweighted → or weight by bond length from 3D SDF
- Compute: degree sequence, diameter, eccentricity of each atom, graph density
- Compute **graph Laplacian** $L = D - A$; its second-smallest eigenvalue (Fiedler value) measures connectivity
- Apply **Morgan algorithm** (iterative node-label propagation) — basis of circular fingerprints (ECFP)
- 3D SDF: weight edges by actual bond lengths → weighted shortest path

**Graph 2 — Taxonomy graph** (from cid_4.dot)
- 13 nodes (1 compound + 12 species visible in DOT), directed edges from compound to species, two subgraph clusters (mammals, birds)
- In- and out-degree analysis; the compound node has out-degree 12, species have in-degree 1
- Partition the species nodes: are mammal nodes and bird nodes distinguishable using **spectral clustering** on the adjacency matrix?
- Add NCBI `Taxonomy_ID` values from the CSV as node attributes → compute taxonomic distance between species pairs as a tree-distance problem on the NCBI taxonomy tree

### Machine Learning

**Feature engineering** — build a feature matrix from these sources:
- Per-atom features from `cid4-sdf-extracted.json`: `[atomic_number, bond_count, total_H, mass, hybridization_encoded, is_aromatic, charge]`
- Molecular-level descriptor: `[C_count, H_count, N_count, O_count, bond_count_total, mol_weight, has_chiral_center]`
- For bioactivity rows: `[Aid_Type_encoded, Has_Dose_Response, RNAi_BioAssay, Activity_Type_encoded]`

| ML Technique | Setup |
|---|---|
| **Linear Regression** | Target: `Activity_Value` (IC50/potency). Feature: mol weight derived from atom masses; extend with atom counts. Derive normal equations $w = (X^TX)^{-1}X^Ty$ by hand first, then use sklearn |
| **Logistic Regression** | Binary target: `Activity` → Active=1, Inactive=0. Features: molecular descriptors + assay metadata |
| **SVM** | Same binary classification; try RBF kernel; compare decision boundary to logistic |
| **KNN** | Given one molecule's atom vector, find the k-nearest atoms or assay records by Euclidean distance; discuss effect of k and distance metric |
| **Decision Tree / Random Forest** | Predict `Activity` from bioassay metadata; interpret feature importances |
| **K-Means Clustering** | Cluster atoms by `[atomic_number, mass, bond_count]` into chemical groups (expect: O cluster, N cluster, C cluster, H cluster); evaluate with silhouette score |
| **Hierarchical Clustering** | Cluster the 17 species using Euclidean distance on `[Taxonomy_ID]`; see if mammals and birds naturally separate |
| **PCA** | Apply to the 5×7 heavy-atom feature matrix; plot PC1 vs PC2; interpret loadings |
| **Graph Neural Network (GNN)** | Represent the molecular graph natively; implement 1-2 rounds of message passing where each atom aggregates neighbor features → node embedding → graph-level readout → predict activity |
| **LSTM / RNN on SMILES** | Encode SMILES string `CC(N)O` (for 1-Amino-2-propanol) character by character; train a seq-to-property model (extend with PubChem's other CID SMILES data) |
| **Naive Bayes** | Categorical features (hybridization type, element) → predict whether atom is a heavy atom or H |

---

## Practical Starting Points by File

| File | Best entry point |
|---|---|
| cid4-sdf-extracted.json | Linear algebra (feature matrix), clustering, PCA, GNN node features |
| Conformer3D_COMPOUND_CID_4.json | Graph construction (adjacency matrix/list), BFS/DFS, shortest path, Laplacian |
| pubchem_cid_4_bioactivity.csv | Regression, classification (SVM/KNN/logistic), statistics, probability |
| pubchem_cid_4_consolidatedcompoundtaxonomy.csv | Clustering (k-means/hierarchical), set theory, taxonomic tree |
| cid_4.dot | Graph theory (directed graph, BFS, topological sort, spectral clustering) |
| Conformer3D_COMPOUND_CID_4.sdf | 3D geometry (distance matrix, bond angles, MST), calculus (bond potential) |
