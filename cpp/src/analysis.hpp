#pragma once

#include <cstddef>
#include <filesystem>
#include <optional>
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

struct BondAngleTriplet {
    int atomIdA;
    int atomIdBCenter;
    int atomIdC;
};

struct BondAngleMeasurement {
    int atomIdA;
    int atomIdBCenter;
    int atomIdC;
    double angleDegrees;
};

struct BondAngleStatistics {
    std::size_t count;
    double minAngleDegrees;
    double meanAngleDegrees;
    double stdAngleDegrees;
    double q25AngleDegrees;
    double medianAngleDegrees;
    double q75AngleDegrees;
    double maxAngleDegrees;
};

struct BondAngleMetadata {
    std::size_t atomCount;
    std::size_t bondedAngleTripletCount;
    std::string sourceDistanceMethod;
    std::string units;
    std::string selectionRule;
};

struct BondAngleAnalysisResult {
    std::vector<int> atomIds;
    std::vector<BondAngleTriplet> bondAngleTriplets;
    std::vector<BondAngleMeasurement> bondAngles;
    BondAngleStatistics statistics;
    BondAngleMetadata metadata;
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

struct HillDoseResponseRowCounts {
    std::size_t totalRows;
    std::size_t rowsWithNumericActivityValue;
    std::size_t rowsWithPositiveActivityValue;
    std::size_t rowsFlaggedHasDoseResponseCurve;
    std::size_t retainedRows;
    std::size_t retainedRowsFlaggedHasDoseResponseCurve;
    std::size_t retainedUniqueBioassays;
};

struct HillDoseResponseStatistic {
    double min;
    double median;
    double max;
};

struct HillDoseResponseStatistics {
    HillDoseResponseStatistic activityValueAsInferredK;
    HillDoseResponseStatistic midpointFirstDerivative;
    HillDoseResponseStatistic aucTrapezoidReferenceCurve;
};

struct HillDoseResponseActivityTypeCount {
    std::string activityType;
    std::size_t count;
};

struct HillDoseResponseRepresentativeRow {
    long long bioactivityId;
    long long bioAssayAid;
    std::string activityType;
    std::string targetName;
    double activityValue;
    double inferredKActivityValue;
    double aucTrapezoidReferenceCurve;
    double log10MidpointConcentration;
};

struct HillDoseResponseAucSummary {
    std::string integrationMethod;
    std::string curveBasis;
    std::string concentrationBoundsDefinition;
    std::size_t gridSize;
    std::string concentrationUnits;
    std::string interpretation;
};

struct HillDoseResponseMidpointSummary {
    std::string condition;
    double response;
    std::string interpretation;
};

struct HillDoseResponseLinearInflectionSummary {
    std::string formula;
    std::string responseFormula;
    double relativeToK;
    double normalizedResponse;
};

struct HillDoseResponseSummary {
    std::string model;
    std::string equation;
    std::string firstDerivative;
    std::string secondDerivative;
    double referenceHillCoefficientN;
    std::string parameterInterpretation;
    HillDoseResponseMidpointSummary midpointInLogConcentrationSpace;
    HillDoseResponseAucSummary aucTrapezoidReferenceCurve;
    std::optional<HillDoseResponseLinearInflectionSummary> linearConcentrationInflection;
    std::string fitStatus;
    std::vector<HillDoseResponseRepresentativeRow> representativeRows;
    std::vector<std::string> notes;
};

struct HillDoseResponseAnalysisResult {
    std::string sourceFile;
    std::vector<std::string> headers;
    std::vector<std::vector<std::string>> rows;
    HillDoseResponseRowCounts rowCounts;
    HillDoseResponseStatistics statistics;
    std::vector<HillDoseResponseActivityTypeCount> activityTypeCounts;
    HillDoseResponseSummary analysis;
};

struct GradientDescentAtomRow {
    int index;
    std::string symbol;
    double mass;
    int atomicNumber;
};

struct GradientDescentTraceRow {
    std::size_t epoch;
    double weight;
    double gradient;
    double sumSquaredError;
    double meanSquaredError;
};

struct GradientCheck {
    double analytic;
    double finiteDifference;
};

struct GradientCheckSummary {
    GradientCheck initialWeight;
    GradientCheck finalWeight;
};

struct GradientDescentLossTraceSummary {
    bool monotonicNonincreasingMeanSquaredError;
    std::size_t bestEpoch;
};

struct GradientDescentDatasetSummary {
    std::size_t rowCount;
    std::string feature;
    std::string target;
    std::vector<int> featureMatrixShape;
    std::vector<double> massRange;
    std::vector<int> atomicNumberRange;
    std::vector<GradientDescentAtomRow> atomRows;
};

struct GradientDescentModelSummary {
    std::string predictionEquation;
    std::string objectiveName;
    std::string objectiveEquation;
    std::string meanSquaredErrorEquation;
    std::string gradientEquation;
    std::string featureName;
    std::string targetName;
};

struct GradientDescentOptimizationSummary {
    double initialWeight;
    double finalWeight;
    double learningRate;
    std::size_t epochs;
    double closedFormWeight;
    double initialSumSquaredError;
    double finalSumSquaredError;
    double initialMeanSquaredError;
    double finalMeanSquaredError;
    double weightErrorVsClosedForm;
    GradientCheckSummary gradientChecks;
    GradientDescentLossTraceSummary lossTrace;
};

struct GradientDescentSummary {
    GradientDescentDatasetSummary dataset;
    GradientDescentModelSummary model;
    GradientDescentOptimizationSummary optimization;
};

struct GradientDescentAnalysisResult {
    std::string sourceFile;
    std::vector<std::string> headers;
    std::vector<GradientDescentTraceRow> traceRows;
    GradientDescentSummary summary;
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
HillDoseResponseAnalysisResult buildHillDoseResponseAnalysis(const std::filesystem::path& csvPath,
                                                             double hillCoefficient = 1.0);
void writeHillDoseResponseCsv(const HillDoseResponseAnalysisResult& result,
                              const std::filesystem::path& outputPath);
void writeHillDoseResponsePlotSvg(const HillDoseResponseAnalysisResult& result,
                                  const std::filesystem::path& outputPath);
GradientDescentAnalysisResult buildGradientDescentAnalysis(const std::vector<AtomRecord>& atoms,
                                                           std::string_view sourceFile,
                                                           double learningRate = 5.0e-5,
                                                           std::size_t epochs = 250U,
                                                           double initialWeight = 0.0);
void writeGradientDescentCsv(const GradientDescentAnalysisResult& result,
                             const std::filesystem::path& outputPath);
void writeGradientDescentLossPlotSvg(const GradientDescentAnalysisResult& result,
                                     const std::filesystem::path& outputPath);
void writeGradientDescentFitPlotSvg(const GradientDescentAnalysisResult& result,
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
BondAngleAnalysisResult buildBondAngleAnalysis(const DistanceMatrixResult& distanceMatrix,
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
std::filesystem::path bondAngleOutputJsonPath(const std::filesystem::path& outputDirectory,
                                              const std::filesystem::path& sourceFile,
                                              std::string_view distanceMethod);
std::filesystem::path bioactivityFilteredCsvPath(const std::filesystem::path& outputDirectory,
                                                 const std::filesystem::path& sourceFile);
std::filesystem::path bioactivitySummaryJsonPath(const std::filesystem::path& outputDirectory,
                                                 const std::filesystem::path& sourceFile);
std::filesystem::path bioactivityPlotSvgPath(const std::filesystem::path& outputDirectory,
                                             const std::filesystem::path& sourceFile);
std::filesystem::path hillDoseResponseCsvPath(const std::filesystem::path& outputDirectory,
                                              const std::filesystem::path& sourceFile);
std::filesystem::path hillDoseResponseSummaryJsonPath(const std::filesystem::path& outputDirectory,
                                                      const std::filesystem::path& sourceFile);
std::filesystem::path hillDoseResponsePlotSvgPath(const std::filesystem::path& outputDirectory,
                                                  const std::filesystem::path& sourceFile);
std::filesystem::path gradientDescentCsvPath(const std::filesystem::path& outputDirectory,
                                             const std::filesystem::path& sourceFile);
std::filesystem::path gradientDescentSummaryJsonPath(const std::filesystem::path& outputDirectory,
                                                     const std::filesystem::path& sourceFile);
std::filesystem::path gradientDescentLossPlotSvgPath(const std::filesystem::path& outputDirectory,
                                                     const std::filesystem::path& sourceFile);
std::filesystem::path gradientDescentFitPlotSvgPath(const std::filesystem::path& outputDirectory,
                                                    const std::filesystem::path& sourceFile);
} // namespace pubchem
