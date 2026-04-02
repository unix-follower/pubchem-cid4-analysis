# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

C++ implementation for analyzing PubChem compound CID 4 (1-Amino-2-propanol). Part of a multi-language educational project covering mathematics, algorithms, data structures, graph theory, and machine learning using molecular chemistry data.

## Build System

Uses CMake 4.3.0+ with vcpkg for dependency management.
RDKit is supplied separately from a micromamba or conda environment and discovered via `PUBCHEM_RDKIT_PREFIX`.

### Building

```bash
# Full rebuild (recommended)
./build.sh

# Manual build steps
micromamba create -y -p ./.micromamba/rdkit -c conda-forge librdkit-dev libboost-devel
export PUBCHEM_RDKIT_PREFIX="$PWD/.micromamba/rdkit"
vcpkg install                 # Install dependencies from vcpkg.json
cmake --preset=vcpkg          # Configure with vcpkg toolchain and external RDKit
cmake --build --preset=vcpkg  # Build project

# Disable the optional Vulkan bootstrap target if needed
cmake --preset=vcpkg -DPUBCHEM_ENABLE_VULKAN_APP=OFF

# Disable the optional OpenGL bootstrap target if needed
cmake --preset=vcpkg -DPUBCHEM_ENABLE_OPENGL_APP=OFF

# Disable the optional CUDA geometry analyzer if needed
cmake --preset=vcpkg -DPUBCHEM_ENABLE_CUDA_APP=OFF

# Disable the optional OpenCV image diagnostics tool if needed
cmake --preset=vcpkg -DPUBCHEM_ENABLE_OPENCV_APP=OFF

# Enable the OpenCV manifest feature before configuring if you want real image processing
export PUBCHEM_VCPKG_FEATURES=opencv-app
./build.sh

# Run the application
./build/app

# Run the optional Vulkan bootstrap
./build/vulkan_app
./build/vulkan_app --skip-runtime-probe

# Run the optional OpenGL bootstrap
./build/opengl_app
./build/opengl_app --skip-runtime-probe

# Run the optional CUDA geometry analyzer
./build/cuda_app
./build/cuda_app --skip-runtime-probe

# Run the optional OpenCV image diagnostics tool
./build/opencv_app --task segment-2d
./build/opencv_app --task compare-conformers
./build/opencv_app --task overlay-structure

# Run the bare-minimum plain OpenSSL API server
./build/plain_openssl_api_server --host 127.0.0.1 --port 9446

# Run the bare-minimum Boost.Asio API server
./build/boost_asio_api_server --host 127.0.0.1 --port 9447

# Run with an explicit adjacency method
./build/app --method arrays
./build/app --method armadillo
./build/app --method boost-graph

# Run with an explicit eigendecomposition method
./build/app --eigenmethod armadillo
./build/app --eigenmethod boost

# Run with an explicit Laplacian analysis method
./build/app --laplacian-method armadillo
./build/app --laplacian-method boost

# Run with an explicit distance-matrix source method
./build/app --distance-method json
./build/app --distance-method sdf

# Run with an explicit bioactivity CSV path
./build/app --bioactivity pubchem_cid_4_bioactivity.csv
```

### Testing

```bash
# Run all tests
ctest --preset=vcpkg

# Or run the test executable directly
./build/tests

# Run tests with verbose output
./build/tests --gtest_verbose=1

# Run specific tests by filter
./build/tests --gtest_filter=SampleTest.*
```

Tests are located in `test/` directory and use GoogleTest framework. The test executable is built automatically when running the build commands above.

### CMake Presets

- **vcpkg preset**: Uses vcpkg toolchain, Ninja generator, builds to `build/` directory
- **PUBCHEM_RDKIT_PREFIX**: Optional environment variable pointing to the micromamba or conda prefix that contains RDKit and Boost development packages

The `CMakeUserPresets.json` file is user-specific and contains the local vcpkg root path. When setting up on a new machine, ensure `VCPKG_ROOT` points to your vcpkg installation.

## Dependencies

Managed via `vcpkg.json`:
- **Armadillo**: Linear algebra library (matrices, vectors, decompositions)

## Dataset Location

Data files are in `../data/`:
- Molecular structure: `Conformer3D_COMPOUND_CID_4(1).json`, `Conformer3D_COMPOUND_CID_4(1).sdf`
- Bioactivity: `pubchem_cid_4_bioactivity.csv` (34 columns, IC50/potency values, assay classifications)
- Taxonomy: `pubchem_cid_4_consolidatedcompoundtaxonomy.csv` (17 food sources)
- Graph: `cid_4.dot` (compound-species associations)
- Full compound data: `COMPOUND_CID_4.json`

## Code Style

Defined in `.editorconfig`:
- Indent size: 4 spaces
- Pointer/reference alignment: left (`int* ptr`, not `int *ptr`)
- Function braces: new line
- Namespace braces: same line

### Format code
```shell
find src -type f \( -name '*.cpp' -o -name '*.hpp' -o -name '*.h' \) -exec clang-format -style=file -i {} \;
find test -type f \( -name '*.cpp' -o -name '*.hpp' -o -name '*.h' \) -exec clang-format -style=file -i {} \;
```

## C++ Standard

Project uses C++23 (`CMAKE_CXX_STANDARD 23`).

## Typical Development Tasks

Since this is an educational project, implementations typically involve:

1. **Linear algebra operations**: Build adjacency matrices, feature matrices, compute eigenvalues/eigenvectors
2. **Graph algorithms**: Molecular graph (14 atoms, 13 bonds) - BFS, DFS, shortest path, Laplacian
3. **Data parsing**: Read JSON/CSV/SDF files, extract molecular properties
4. **Statistical analysis**: Mean, variance, distributions on bioactivity data
5. **Machine learning**: Feature engineering from molecular descriptors, regression/classification

The main executable is `app` (built from `src/app.cpp`). Add new implementation files as needed and update `CMakeLists.txt` to link them.

The repository now also exposes an optional `vulkan_app` executable for compile-first native graphics work. It always builds when `PUBCHEM_ENABLE_VULKAN_APP=ON`, but it only enables Vulkan runtime probing when `find_package(Vulkan)` succeeds during CMake configuration. On machines without a Vulkan SDK or loader, the target falls back to a stub mode that still parses CID 4 geometry and compiles cleanly.

The repository also exposes an optional `opengl_app` executable for the lower-complexity native graphics path. It always builds when `PUBCHEM_ENABLE_OPENGL_APP=ON`, but it only enables OpenGL runtime probing when both `find_package(OpenGL)` and `find_package(glfw3 CONFIG)` succeed during CMake configuration. On machines without a usable OpenGL and GLFW development stack, the target falls back to a stub mode that still parses CID 4 geometry and compiles cleanly.

The repository also exposes an optional `cuda_app` executable for CUDA-oriented geometry analysis. It always builds when `PUBCHEM_ENABLE_CUDA_APP=ON`, but it only enables CUDA runtime execution when CMake can enable the CUDA language and find a CUDA toolkit. On machines without an NVIDIA CUDA toolchain, the target falls back to a stub mode that still batches CID 4 conformer coordinates and computes CPU reference distance matrices so the integration remains compile-safe.

The repository also exposes an optional `opencv_app` executable for OpenCV-driven image diagnostics. It always builds when `PUBCHEM_ENABLE_OPENCV_APP=ON`, but it only enables real image workflows when `find_package(OpenCV)` succeeds during CMake configuration. On machines without OpenCV available, the target falls back to a stub mode that still validates CID 4 scene loading and CLI wiring so the integration remains compile-safe. To install the OpenCV dependency through vcpkg manifest mode, enable the `opencv-app` feature before running `vcpkg install` or `build.sh`.

The repository also exposes two minimal HTTPS backends for transport-level comparison work: `plain_openssl_api_server` uses raw sockets plus OpenSSL directly, while `boost_asio_api_server` uses Boost.Asio with OpenSSL-backed TLS streams. Both reuse the shared `cid4_http` route/config helpers and support the same runtime mode surface with `thread-per-request` and `thread-pool` execution modes.

The current adjacency-matrix implementation exposes a method-string strategy surface with `arrays`, `armadillo`, and `boost-graph`. The eigendecomposition flow exposes a separate `--eigenmethod` selector with `armadillo` and `boost`. The Laplacian flow also exposes a strategy selector with `--laplacian-method <armadillo|boost>`.

The distance-matrix flow exposes a dedicated `--distance-method <json|sdf>` selector. The `json` strategy reads `PC_Compounds[0].coords[0].conformers[0]` from the numbered conformer JSON file, while the `sdf` strategy reads the first valid RDKit conformer from the numbered SDF file.

Use Armadillo as the default eigensolver. The `boost` eigendecomposition path uses `boost-ublas` for matrix representation together with an in-repo symmetric solver implementation, so keep the JSON output contract library-agnostic.

Use the same strategy split for Laplacian analysis. The Laplacian artifact is written separately from the adjacency and eigendecomposition outputs so downstream consumers can inspect degree values, null-space basis vectors, and connected-component metadata independently.

The distance-matrix artifact is also written separately from the atom-record, adjacency, eigendecomposition, and Laplacian outputs so downstream consumers can compare geometric distances without coupling to graph structure choices.

The C++ app also writes a bonded-distance comparison JSON artifact derived from the distance matrix and PubChem bond list. It reports bonded atom pairs, bonded and non-bonded pair distances, and summary statistics so downstream consumers can compare local bond geometry with longer-range separations without changing the distance-matrix contract.

The C++ app also writes a bond-angle analysis JSON artifact derived from the aligned 3D coordinates and PubChem bond list. It reports unique triplets A-B-C where A-B and B-C are bonded and B is the central atom, together with angle statistics in degrees, as a separate artifact so downstream consumers can inspect local valence geometry without changing the distance-matrix contract.

The C++ app now also writes a spring-bond potential JSON artifact derived from the aligned 3D coordinates and PubChem bond list. It reports per-bond harmonic spring records using `E_ij = 0.5 * k_ij * (d_ij - d0_ij)^2`, chemistry-informed reference distances `d0` keyed by atom symbols and bond order with a covalent-radius fallback, bond-order-specific spring constants `k`, per-bond Cartesian partial derivatives for both bonded atoms, per-atom aggregated gradients, and gradient-balance statistics.

The bioactivity flow now reads `pubchem_cid_4_bioactivity.csv`, filters to positive numeric `Activity_Type == IC50` rows, computes `pIC50 = -log10(IC50_uM)`, and writes three additive artifacts under `data/out`: a filtered CSV, a summary JSON file, and an SVG plot of the transform curve over the observed IC50 range.

The C++ app now also writes a Bayesian posterior bioactivity analysis under `data/out`: a CSV of retained binary evidence rows where `Activity` is `Active` or `Inactive`, plus a summary JSON for `P(Active | CID=4)` using a conjugate Beta-Binomial update with prior `Beta(1,1)`. Rows labeled `Unspecified` are excluded from the binary update and reported separately in the row counts.

The C++ app now also writes an assay-level binomial bioactivity analysis under `data/out`: a PMF CSV for `P(K = k)` across `k = 0..n` active assays and a summary JSON for `P(K = k active assays in n assays)` using one Bernoulli trial per unique `BioAssay_AID`. This feature reuses the same `Activity = Active / Inactive` binary evidence filter as the posterior analysis, excludes `Unspecified` before assay-level collapsing, resolves an assay to `Active` if any retained row for that assay is `Active`, and uses the observed active-assay fraction as the plug-in binomial success probability.

The C++ app now also writes an `Activity` versus `Aid_Type` chi-square bioactivity analysis under `data/out`: a contingency CSV over retained binary `Activity` rows and observed `Aid_Type` categories, plus a summary JSON for a Pearson chi-square test of independence between `Activity` and `Aid_Type`. This feature reuses the same `Activity = Active / Inactive` binary evidence filter as the posterior analysis, trims `Aid_Type`, normalizes blank values to `Unknown`, and records a non-computed result instead of a misleading statistic when fewer than two observed `Activity` levels or fewer than two observed `Aid_Type` levels remain after filtering.

The C++ app now also writes Hill/sigmoidal dose-response reference artifacts under `data/out`: a CSV of positive numeric `Activity_Value` rows interpreted as inferred Hill-scale parameters `K`, including trapezoidal-rule AUC values for the inferred reference curves; a summary JSON that documents the normalized Hill model `f(c) = c^n / (K^n + c^n)` together with midpoint, inflection, and AUC integration interpretation; and an SVG plot of representative reference curves. Because the CID 4 bioactivity CSV contains potency-style summary values rather than raw per-concentration response series, this is a reference-curve analysis rather than a nonlinear fit to experimental dose-response points.

The C++ app now also writes positive-numeric `Activity_Value` descriptive statistics artifacts under `data/out`: a CSV of retained rows where `Activity_Value` is numeric and strictly greater than 0; a summary JSON with mean, sample variance, skewness, quantiles, and a Shapiro-Wilk status block; and an SVG diagnostic plot with a log-scale histogram and a normality-status panel. For the current CID 4 dataset, only two rows are retained, so Shapiro-Wilk is not computable on sample-size grounds. The C++ implementation keeps the Shapiro-Wilk section structurally present but marks it as not computed until a dedicated implementation is added.

The C++ app now also writes atom-element entropy artifacts under `data/out`: a CSV of O/N/C/H element counts, proportions, log proportions, and per-element Shannon contributions; a summary JSON with entropy `H = -sum p_i log p_i`, normalized entropy, retained support, and any unexpected atom symbols; and an SVG bar chart of the O/N/C/H proportions. This entropy analysis derives element symbols from the RDKit-backed atom records for the active conformer and computes the entropy sum only over the required O/N/C/H support from the README exercise.

## CI/CD

GitHub Actions workflow (`.github/workflows/build-cpp.yaml`) builds on Ubuntu using:
- lukka/get-cmake for CMake/Ninja
- lukka/run-vcpkg for vcpkg setup
- Configures and builds using the vcpkg preset
