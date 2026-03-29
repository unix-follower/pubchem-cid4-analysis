#pragma once

#include <cstddef>
#include <filesystem>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

namespace pubchem {
struct AtomRecord {
    int index;
    int bondCount;
    int charge;
    int implicitHydrogenCount;
    int totalHydrogenCount;
    int atomicNumber;
    std::string symbol;
    int valency;
    bool isAromatic;
    double mass;
    std::string hybridization;
};

struct AnalysisResult {
    std::string sourceFile;
    double averageMolecularWeight;
    double exactMolecularMass;
    std::size_t moleculeCount;
    std::vector<AtomRecord> atoms;
};

struct WeightedBond {
    int sourceAtomId;
    int targetAtomId;
    int weight;
    std::size_t sourceIndex;
    std::size_t targetIndex;
};

struct NormalizedAdjacencyInput {
    std::vector<int> atomIds;
    std::vector<WeightedBond> bonds;

    [[nodiscard]] std::size_t size() const noexcept;
};

struct AdjacencyMatrix {
    std::string sourceFile;
    std::string method;
    std::vector<int> atomIds;
    std::vector<std::vector<int>> values;
};

struct EigendecompositionResult {
    std::string sourceFile;
    std::string method;
    std::vector<int> atomIds;
    std::vector<double> eigenvalues;
    std::vector<std::vector<double>> eigenvectors;
};

class AdjacencyMatrixStrategy {
  public:
    virtual ~AdjacencyMatrixStrategy() = default;

    [[nodiscard]] virtual std::string_view method() const noexcept = 0;
    [[nodiscard]] virtual AdjacencyMatrix build(const NormalizedAdjacencyInput& input,
                                                std::string_view sourceFile) const = 0;
};

class EigendecompositionStrategy {
  public:
    virtual ~EigendecompositionStrategy() = default;

    [[nodiscard]] virtual std::string_view method() const noexcept = 0;
    [[nodiscard]] virtual EigendecompositionResult compute(const AdjacencyMatrix& matrix) const = 0;
};

double averageOrZero(const std::vector<double>& values);
std::vector<std::string> supportedAdjacencyMethods();
std::string parseAdjacencyMethod(std::string_view method);
std::vector<std::string> supportedEigendecompositionMethods();
std::string parseEigendecompositionMethod(std::string_view method);
NormalizedAdjacencyInput loadAdjacencyInput(const std::filesystem::path& jsonPath);
AdjacencyMatrix buildAdjacencyMatrix(const NormalizedAdjacencyInput& input,
                                     std::string_view sourceFile,
                                     std::string_view method);
EigendecompositionResult buildEigendecomposition(const AdjacencyMatrix& matrix,
                                                 std::string_view method);
std::filesystem::path outputDirectoryFor(const std::filesystem::path& dataDirectory);
std::filesystem::path outputJsonPath(const std::filesystem::path& outputDirectory,
                                     const std::filesystem::path& sourceFile);
std::filesystem::path adjacencyOutputJsonPath(const std::filesystem::path& outputDirectory,
                                              const std::filesystem::path& sourceFile,
                                              std::string_view method);
std::filesystem::path eigendecompositionOutputJsonPath(const std::filesystem::path& outputDirectory,
                                                       const std::filesystem::path& sourceFile,
                                                       std::string_view method);
} // namespace pubchem
