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

struct NullSpaceBasis {
    std::vector<double> eigenvalues;
    std::vector<std::vector<double>> eigenvectors;
    double tolerance;
    std::size_t numZeroEigenvalues;
    double smallestNonZeroEigenvalue;
};

struct ConnectedComponentsResult {
    std::vector<int> labels;
    std::size_t numComponents;
    std::vector<std::vector<int>> componentAtomIds;
    std::size_t verificationBoostGraphCount;
};

struct LaplacianMetadata {
    std::size_t atomCount;
    std::size_t bondCount;
    std::size_t laplacianRank;
    bool graphIsConnected;
};

struct LaplacianAnalysisResult {
    std::string sourceFile;
    std::string method;
    std::vector<int> atomIds;
    std::vector<double> degreeVector;
    std::vector<std::vector<double>> laplacianMatrix;
    std::vector<double> laplacianEigenvalues;
    std::vector<std::vector<double>> laplacianEigenvectors;
    NullSpaceBasis nullSpace;
    ConnectedComponentsResult connectedComponents;
    LaplacianMetadata metadata;
};

struct DistanceMatrixMetadata {
    std::size_t atomCount;
    std::size_t coordinateDimension;
    std::string units;
};

struct DistanceMatrixInput {
    std::vector<int> atomIds;
    std::filesystem::path jsonPath;
    std::filesystem::path sdfPath;
};

struct DistanceMatrixResult {
    std::string sourceFile;
    std::string method;
    std::vector<int> atomIds;
    std::vector<std::vector<double>> xyzCoordinates;
    std::vector<std::vector<double>> distanceMatrix;
    DistanceMatrixMetadata metadata;
};

struct BondedAtomPair {
    int atomId1;
    int atomId2;
};

struct AtomPairDistance {
    int atomId1;
    int atomId2;
    double distanceAngstrom;
};

struct BondedDistanceStatistics {
    std::size_t count;
    double minDistanceAngstrom;
    double meanDistanceAngstrom;
    double stdDistanceAngstrom;
    double q25DistanceAngstrom;
    double medianDistanceAngstrom;
    double q75DistanceAngstrom;
    double maxDistanceAngstrom;
};

struct BondedDistanceComparison {
    double meanDistanceDifferenceAngstrom;
    double nonbondedToBondedMeanRatio;
};

struct BondedDistanceMetadata {
    std::size_t atomCount;
    std::size_t bondedPairCount;
    std::size_t nonbondedPairCount;
    std::size_t totalUniquePairCount;
    std::string sourceDistanceMethod;
    std::string units;
};

struct BondedDistanceAnalysisResult {
    std::vector<int> atomIds;
    std::vector<BondedAtomPair> bondedAtomPairs;
    std::vector<AtomPairDistance> bondedPairDistances;
    std::vector<AtomPairDistance> nonbondedPairDistances;
    BondedDistanceStatistics bondedDistances;
    BondedDistanceStatistics nonbondedDistances;
    BondedDistanceComparison comparison;
    BondedDistanceMetadata metadata;
};

struct BioactivityRowCounts {
    std::size_t totalRows;
    std::size_t rowsWithNumericActivityValue;
    std::size_t rowsWithIc50ActivityType;
    std::size_t retainedIc50Rows;
    std::size_t droppedRows;
};

struct BioactivityStatistic {
    double min;
    double median;
    double max;
};

struct BioactivityStatistics {
    BioactivityStatistic ic50Um;
    BioactivityStatistic pIC50;
};

struct BioactivityMeasurement {
    long long bioactivityId;
    long long bioAssayAid;
    double ic50Um;
    double pIC50;
};

struct BioactivitySummary {
    std::string transform;
    std::string interpretation;
    std::vector<double> observedIc50DomainUm;
    BioactivityMeasurement strongestRetainedMeasurement;
    BioactivityMeasurement weakestRetainedMeasurement;
};

struct BioactivityAnalysisResult {
    std::string sourceFile;
    std::vector<std::string> headers;
    std::vector<std::vector<std::string>> filteredRows;
    BioactivityRowCounts rowCounts;
    BioactivityStatistics statistics;
    BioactivitySummary analysis;
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

class LaplacianAnalysisStrategy {
  public:
    virtual ~LaplacianAnalysisStrategy() = default;

    [[nodiscard]] virtual std::string_view method() const noexcept = 0;
    [[nodiscard]] virtual LaplacianAnalysisResult analyze(const AdjacencyMatrix& matrix,
                                                          double zeroTolerance) const = 0;
};

class DistanceMatrixStrategy {
  public:
    virtual ~DistanceMatrixStrategy() = default;

    [[nodiscard]] virtual std::string_view method() const noexcept = 0;
    [[nodiscard]] virtual DistanceMatrixResult build(const DistanceMatrixInput& input) const = 0;
};

double averageOrZero(const std::vector<double>& values);
std::vector<std::string> supportedAdjacencyMethods();
std::string parseAdjacencyMethod(std::string_view method);
std::vector<std::string> supportedEigendecompositionMethods();
std::string parseEigendecompositionMethod(std::string_view method);
std::vector<std::string> supportedLaplacianMethods();
std::string parseLaplacianMethod(std::string_view method);
std::vector<std::string> supportedDistanceMethods();
std::string parseDistanceMethod(std::string_view method);
NormalizedAdjacencyInput loadAdjacencyInput(const std::filesystem::path& jsonPath);
BioactivityAnalysisResult buildBioactivityAnalysis(const std::filesystem::path& csvPath);
void writeBioactivityFilteredCsv(const BioactivityAnalysisResult& result,
                                 const std::filesystem::path& outputPath);
void writeBioactivityPlotSvg(const BioactivityAnalysisResult& result,
                             const std::filesystem::path& outputPath);
AdjacencyMatrix buildAdjacencyMatrix(const NormalizedAdjacencyInput& input,
                                     std::string_view sourceFile,
                                     std::string_view method);
EigendecompositionResult buildEigendecomposition(const AdjacencyMatrix& matrix,
                                                 std::string_view method);
LaplacianAnalysisResult buildLaplacianAnalysis(const AdjacencyMatrix& matrix,
                                               std::string_view method,
                                               double zeroTolerance = 1.0e-10);
DistanceMatrixResult buildDistanceMatrix(const DistanceMatrixInput& input, std::string_view method);
BondedDistanceAnalysisResult buildBondedDistanceAnalysis(const DistanceMatrixResult& distanceMatrix,
                                                         const AdjacencyMatrix& adjacencyMatrix);
std::filesystem::path outputDirectoryFor(const std::filesystem::path& dataDirectory);
std::filesystem::path outputJsonPath(const std::filesystem::path& outputDirectory,
                                     const std::filesystem::path& sourceFile);
std::filesystem::path adjacencyOutputJsonPath(const std::filesystem::path& outputDirectory,
                                              const std::filesystem::path& sourceFile,
                                              std::string_view method);
std::filesystem::path eigendecompositionOutputJsonPath(const std::filesystem::path& outputDirectory,
                                                       const std::filesystem::path& sourceFile,
                                                       std::string_view method);
std::filesystem::path laplacianOutputJsonPath(const std::filesystem::path& outputDirectory,
                                              const std::filesystem::path& sourceFile,
                                              std::string_view method);
std::filesystem::path distanceOutputJsonPath(const std::filesystem::path& outputDirectory,
                                             const std::filesystem::path& sourceFile,
                                             std::string_view method);
std::filesystem::path bondedDistanceOutputJsonPath(const std::filesystem::path& outputDirectory,
                                                   const std::filesystem::path& sourceFile,
                                                   std::string_view distanceMethod);
std::filesystem::path bioactivityFilteredCsvPath(const std::filesystem::path& outputDirectory,
                                                 const std::filesystem::path& sourceFile);
std::filesystem::path bioactivitySummaryJsonPath(const std::filesystem::path& outputDirectory,
                                                 const std::filesystem::path& sourceFile);
std::filesystem::path bioactivityPlotSvgPath(const std::filesystem::path& outputDirectory,
                                             const std::filesystem::path& sourceFile);
} // namespace pubchem
