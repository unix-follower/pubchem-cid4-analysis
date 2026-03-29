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

# Run the application
./build/app

# Run with an explicit adjacency method
./build/app --method arrays
./build/app --method armadillo
./build/app --method boost-graph
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
- Molecular structure: `Conformer3D_COMPOUND_CID_4.json`, `Conformer3D_COMPOUND_CID_4.sdf`
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

## C++ Standard

Project uses C++23 (`CMAKE_CXX_STANDARD 23`).

## Typical Development Tasks

Since this is an educational project, implementations typically involve:

1. **Linear algebra operations**: Build adjacency matrices, feature matrices, compute eigenvalues/eigenvectors (use Armadillo)
2. **Graph algorithms**: Molecular graph (14 atoms, 13 bonds) - BFS, DFS, shortest path, Laplacian
3. **Data parsing**: Read JSON/CSV/SDF files, extract molecular properties
4. **Statistical analysis**: Mean, variance, distributions on bioactivity data
5. **Machine learning**: Feature engineering from molecular descriptors, regression/classification

The main executable is `app` (built from `src/app.cpp`). Add new implementation files as needed and update `CMakeLists.txt` to link them.

The current adjacency-matrix implementation exposes a method-string strategy surface with `arrays`, `armadillo`, and `boost-graph`. Keep the shared output model library-agnostic if additional graph strategies are added later.

## CI/CD

GitHub Actions workflow (`.github/workflows/build-cpp.yaml`) builds on Ubuntu using:
- lukka/get-cmake for CMake/Ninja
- lukka/run-vcpkg for vcpkg setup
- Configures and builds using the vcpkg preset
