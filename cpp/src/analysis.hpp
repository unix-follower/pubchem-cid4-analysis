#pragma once

#include <cstddef>
#include <filesystem>
#include <map>
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

struct CartesianPartialDerivatives {
    double dEDx;
    double dEDy;
    double dEDz;
    double gradientNorm;
};

struct BondedPairSpringRecord {
    int atomId1;
    int atomId2;
    std::string atomSymbol1;
    std::string atomSymbol2;
    int bondOrder;
    double distanceAngstrom;
    double referenceDistanceAngstrom;
    std::string referenceDistanceSource;
    double distanceResidualAngstrom;
    double springConstant;
    double springEnergy;
    double dEDDistance;
    CartesianPartialDerivatives atom1PartialDerivatives;
    CartesianPartialDerivatives atom2PartialDerivatives;
};

struct AtomGradientRecord {
    int atomId;
    std::string atomSymbol;
    std::size_t incidentBondCount;
    double dEDx;
    double dEDy;
    double dEDz;
    double gradientNorm;
};

struct DistanceResidualStatistics {
    std::size_t count;
    double min;
    double mean;
    double std;
    double q25;
    double median;
    double q75;
    double max;
    std::size_t zeroResidualBondCount;
};

struct SpringEnergyStatistics {
    std::size_t count;
    double total;
    double min;
    double mean;
    double std;
    double q25;
    double median;
    double q75;
    double max;
};

struct AtomGradientNormStatistics {
    std::size_t count;
    double min;
    double mean;
    double std;
    double q25;
    double median;
    double q75;
    double max;
};

struct NetCartesianGradient {
    double dEDx;
    double dEDy;
    double dEDz;
    double gradientNorm;
};

struct SpringBondPotentialStatistics {
    DistanceResidualStatistics distanceResidualAngstrom;
    SpringEnergyStatistics springEnergy;
    AtomGradientNormStatistics atomGradientNorm;
    NetCartesianGradient gradientBalance;
};

struct SpringBondPotentialAnalysis {
    std::string energyEquation;
    std::string distanceEquation;
    std::string distanceDerivativeEquation;
    std::string cartesianGradientEquation;
    std::string reactionGradientEquation;
    std::string referenceDistancePolicy;
    std::string springConstantPolicy;
    std::vector<std::pair<std::string, double>> bondOrderSpringConstants;
    std::vector<std::pair<std::string, double>> referenceDistanceLookupExamplesAngstrom;
    std::string interpretation;
};

struct SpringBondPotentialMetadata {
    std::size_t atomCount;
    std::size_t bondedPairCount;
    std::string sourceDistanceMethod;
    std::string sourceAdjacencyMethod;
    std::string distanceUnits;
    std::string referenceDistanceUnits;
    std::string springConstantUnits;
    std::string springEnergyUnits;
    std::string coordinatePartialDerivativeUnits;
    std::vector<std::pair<std::string, std::size_t>> referenceDistanceSourceCounts;
};

struct SpringBondPotentialAnalysisResult {
    std::vector<int> atomIds;
    std::vector<BondedPairSpringRecord> bondedPairSpringRecords;
    std::vector<AtomGradientRecord> atomGradientRecords;
    SpringBondPotentialStatistics statistics;
    SpringBondPotentialAnalysis analysis;
    SpringBondPotentialMetadata metadata;
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

struct ActivityValueStatisticsRowCounts {
    std::size_t totalRows;
    std::size_t rowsWithNumericActivityValue;
    std::size_t positiveNumericRows;
    std::size_t zeroActivityValueRows;
    std::size_t negativeActivityValueRows;
    std::size_t nonNumericOrMissingActivityValueRows;
    std::size_t retainedPositiveNumericRows;
    std::size_t droppedRows;
    std::size_t retainedUniqueBioassays;
};

struct ActivityValueDescriptiveStatistics {
    std::size_t sampleSize;
    double mean;
    double variance;
    std::string varianceDefinition;
    std::optional<double> skewness;
    double min;
    double q25;
    double median;
    double q75;
    double max;
};

struct ActivityValueNormalityTest {
    std::string name;
    bool computed;
    std::optional<std::string> reasonNotComputed;
    std::size_t sampleSize;
    double alpha;
    std::optional<double> statistic;
    std::optional<double> pValue;
    std::optional<bool> rejectNormality;
    std::string interpretation;
};

struct ActivityValueRepresentativeRow {
    long long bioactivityId;
    long long bioAssayAid;
    std::string activity;
    std::string aidType;
    std::string activityType;
    double activityValue;
};

struct ActivityValueRetainedRowDefinition {
    std::string predicate;
    std::vector<std::string> excludedRows;
};

struct ActivityValueAnalysis {
    std::string targetQuantity;
    ActivityValueRetainedRowDefinition retainedRowDefinition;
    std::vector<ActivityValueRepresentativeRow> representativeRows;
    std::vector<std::string> notes;
};

struct ActivityValueStatisticsAnalysisResult {
    std::string sourceFile;
    std::vector<std::string> headers;
    std::vector<std::vector<std::string>> rows;
    ActivityValueStatisticsRowCounts rowCounts;
    ActivityValueDescriptiveStatistics statistics;
    ActivityValueNormalityTest normalityTest;
    ActivityValueAnalysis analysis;
};

struct PosteriorBioactivityRowCounts {
    std::size_t totalRows;
    std::size_t activeRows;
    std::size_t inactiveRows;
    std::size_t unspecifiedRows;
    std::size_t otherActivityRows;
    std::size_t retainedBinaryRows;
    std::size_t droppedNonBinaryRows;
    std::size_t retainedUniqueBioassays;
};

struct PosteriorBioactivityPrior {
    std::string family;
    double alpha;
    double beta;
};

struct PosteriorBioactivityLikelihood {
    std::string family;
    std::string successLabel;
    std::string failureLabel;
};

struct PosteriorBioactivityDistribution {
    std::string family;
    double alpha;
    double beta;
};

struct PosteriorBioactivityCredibleInterval {
    double mass;
    double lower;
    double upper;
};

struct PosteriorBioactivitySummaryStatistics {
    double posteriorMeanProbabilityActive;
    double posteriorMedianProbabilityActive;
    std::optional<double> posteriorModeProbabilityActive;
    double posteriorVariance;
    PosteriorBioactivityCredibleInterval credibleIntervalProbabilityActive;
    double posteriorProbabilityActiveGt0_5;
    double observedActiveFractionInRetainedRows;
};

struct PosteriorBioactivityPosteriorSection {
    PosteriorBioactivityPrior prior;
    PosteriorBioactivityLikelihood likelihood;
    PosteriorBioactivityDistribution posteriorDistribution;
    PosteriorBioactivitySummaryStatistics summary;
};

struct PosteriorBioactivityUpdateEquations {
    std::string posteriorAlpha;
    std::string posteriorBeta;
    std::string posteriorMean;
};

struct PosteriorBioactivityBinaryEvidenceDefinition {
    std::vector<std::string> retainedLabels;
    std::vector<std::string> excludedLabels;
    std::string interpretation;
};

struct PosteriorBioactivityRepresentativeRow {
    long long bioactivityId;
    long long bioAssayAid;
    std::string activity;
    std::string activityType;
    std::string targetName;
    std::string bioAssayName;
};

struct PosteriorBioactivityAnalysis {
    std::string targetQuantity;
    std::string model;
    PosteriorBioactivityUpdateEquations updateEquations;
    PosteriorBioactivityBinaryEvidenceDefinition binaryEvidenceDefinition;
    std::vector<PosteriorBioactivityRepresentativeRow> representativeRows;
    std::vector<std::string> notes;
};

struct PosteriorBioactivityAnalysisResult {
    std::string sourceFile;
    std::vector<std::string> headers;
    std::vector<std::vector<std::string>> rows;
    PosteriorBioactivityRowCounts rowCounts;
    PosteriorBioactivityPosteriorSection posterior;
    PosteriorBioactivityAnalysis analysis;
};

struct BinomialActivityRowCounts {
    std::size_t totalRows;
    std::size_t activeRows;
    std::size_t inactiveRows;
    std::size_t unspecifiedRows;
    std::size_t otherActivityRows;
    std::size_t retainedBinaryRows;
    std::size_t droppedNonBinaryRows;
    std::size_t retainedUniqueBioassays;
    std::size_t assayTrials;
    std::size_t activeAssayTrials;
    std::size_t inactiveAssayTrials;
    std::size_t mixedEvidenceAssayTrials;
    std::size_t unanimousActiveAssayTrials;
    std::size_t unanimousInactiveAssayTrials;
};

struct BinomialActivityTrialDefinition {
    std::string unit;
    std::string successLabel;
    std::string failureLabel;
    std::string assayResolutionRule;
};

struct BinomialActivityParameters {
    std::size_t nAssays;
    std::size_t observedActiveAssays;
    double successProbabilityActiveAssay;
};

struct BinomialActivitySummaryStatistics {
    double pmfAtObservedActiveAssayCount;
    double cumulativeProbabilityLeqObservedActiveAssayCount;
    double cumulativeProbabilityGeqObservedActiveAssayCount;
    double binomialMeanActiveAssays;
    double binomialVarianceActiveAssays;
    double pmfProbabilitySum;
};

struct BinomialActivityRepresentativeAssay {
    long long bioAssayAid;
    std::string assayActivity;
    std::size_t retainedBinaryRows;
    std::size_t activeRows;
    std::size_t inactiveRows;
    bool mixedEvidence;
    std::string activityType;
    std::string targetName;
    std::string bioAssayName;
};

struct BinomialActivityDistributionSection {
    BinomialActivityTrialDefinition trialDefinition;
    BinomialActivityParameters parameters;
    BinomialActivitySummaryStatistics summary;
};

struct BinomialActivityAnalysis {
    std::string targetQuantity;
    std::string model;
    std::string equation;
    std::string parameterEstimation;
    std::vector<BinomialActivityRepresentativeAssay> representativeAssays;
    std::vector<std::string> notes;
};

struct BinomialActivityDistributionAnalysisResult {
    std::string sourceFile;
    std::vector<std::string> headers;
    std::vector<std::vector<std::string>> rows;
    BinomialActivityRowCounts rowCounts;
    BinomialActivityDistributionSection binomial;
    BinomialActivityAnalysis analysis;
};

struct ChiSquareActivityAidTypeRowCounts {
    std::size_t totalRows;
    std::size_t activeRows;
    std::size_t inactiveRows;
    std::size_t unspecifiedRows;
    std::size_t otherActivityRows;
    std::size_t retainedBinaryRows;
    std::size_t droppedNonBinaryRows;
    std::size_t retainedUniqueBioassays;
    std::size_t retainedRowsWithAidType;
    std::size_t activityLevelsTested;
    std::size_t aidTypeLevelsTested;
};

struct ChiSquareContingencyTable {
    std::vector<std::string> activityLevels;
    std::vector<std::string> aidTypeLevels;
    std::map<std::string, std::map<std::string, std::size_t>> observedCounts;
    std::map<std::string, std::map<std::string, std::optional<double>>> expectedCounts;
};

struct ChiSquareVariables {
    std::string row;
    std::string column;
};

struct ChiSquareTestMetrics {
    ChiSquareVariables variables;
    std::string nullHypothesis;
    std::string alternativeHypothesis;
    bool computed;
    std::optional<std::string> reasonNotComputed;
    std::optional<double> chi2Statistic;
    std::optional<double> pValue;
    std::optional<std::size_t> degreesOfFreedom;
    double minimumExpectedCountThreshold;
    std::optional<std::size_t> sparseExpectedCellCount;
    std::optional<double> sparseExpectedCellFraction;
};

struct ChiSquareRepresentativeCell {
    std::string activity;
    std::string aidType;
    std::size_t observedCount;
    std::optional<double> expectedCount;
};

struct ChiSquareBinaryEvidenceDefinition {
    std::vector<std::string> retainedLabels;
    std::vector<std::string> excludedLabels;
    std::string interpretation;
};

struct ChiSquareActivityAidTypeAnalysis {
    std::string targetQuantity;
    std::string model;
    ChiSquareBinaryEvidenceDefinition binaryEvidenceDefinition;
    std::vector<ChiSquareRepresentativeCell> representativeCells;
    std::vector<std::string> notes;
};

struct ChiSquareActivityAidTypeAnalysisResult {
    std::string sourceFile;
    std::vector<std::string> headers;
    std::vector<std::vector<std::string>> rows;
    ChiSquareActivityAidTypeRowCounts rowCounts;
    ChiSquareContingencyTable contingencyTable;
    ChiSquareTestMetrics chiSquareTest;
    ChiSquareActivityAidTypeAnalysis analysis;
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

struct AtomElementEntropyRowCounts {
    std::size_t totalAtomRows;
    std::size_t retainedAtomRows;
    std::size_t requiredElementCategories;
    std::size_t observedRequiredElementCategories;
    std::size_t unexpectedElementRows;
    std::size_t unexpectedElementCategories;
};

struct AtomElementEntropyMetrics {
    std::string formula;
    std::string logBase;
    double value;
    double maximumEntropyForObservedSupport;
    double normalizedEntropy;
};

struct AtomElementDistributionEntry {
    std::size_t count;
    double proportion;
    double logProportion;
    double shannonContribution;
};

struct AtomElementDominantElement {
    std::string element;
    std::size_t count;
    double proportion;
};

struct AtomElementEntropyAnalysis {
    std::string targetQuantity;
    std::vector<std::string> requiredElements;
    std::size_t uniqueRetainedElements;
    AtomElementDominantElement dominantElement;
    std::map<std::string, std::size_t> unexpectedElements;
    std::vector<std::string> notes;
};

struct AtomElementEntropyAnalysisResult {
    std::string sourceFile;
    std::vector<std::string> headers;
    std::vector<std::vector<std::string>> rows;
    AtomElementEntropyRowCounts rowCounts;
    AtomElementEntropyMetrics entropy;
    std::map<std::string, AtomElementDistributionEntry> distribution;
    AtomElementEntropyAnalysis analysis;
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
PosteriorBioactivityAnalysisResult
buildPosteriorBioactivityAnalysis(const std::filesystem::path& csvPath,
                                  double priorAlpha = 1.0,
                                  double priorBeta = 1.0,
                                  double credibleIntervalMass = 0.95);
void writePosteriorBioactivityCsv(const PosteriorBioactivityAnalysisResult& result,
                                  const std::filesystem::path& outputPath);
BinomialActivityDistributionAnalysisResult
buildBinomialActivityDistributionAnalysis(const std::filesystem::path& csvPath);
void writeBinomialActivityDistributionCsv(const BinomialActivityDistributionAnalysisResult& result,
                                          const std::filesystem::path& outputPath);
ChiSquareActivityAidTypeAnalysisResult
buildChiSquareActivityAidTypeAnalysis(const std::filesystem::path& csvPath,
                                      double expectedCountThreshold = 5.0);
void writeChiSquareActivityAidTypeCsv(const ChiSquareActivityAidTypeAnalysisResult& result,
                                      const std::filesystem::path& outputPath);
HillDoseResponseAnalysisResult buildHillDoseResponseAnalysis(const std::filesystem::path& csvPath,
                                                             double hillCoefficient = 1.0);
void writeHillDoseResponseCsv(const HillDoseResponseAnalysisResult& result,
                              const std::filesystem::path& outputPath);
void writeHillDoseResponsePlotSvg(const HillDoseResponseAnalysisResult& result,
                                  const std::filesystem::path& outputPath);
ActivityValueStatisticsAnalysisResult
buildActivityValueStatisticsAnalysis(const std::filesystem::path& csvPath,
                                     double shapiroAlpha = 0.05);
void writeActivityValueStatisticsCsv(const ActivityValueStatisticsAnalysisResult& result,
                                     const std::filesystem::path& outputPath);
void writeActivityValueStatisticsPlotSvg(const ActivityValueStatisticsAnalysisResult& result,
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
AtomElementEntropyAnalysisResult buildAtomElementEntropyAnalysis(const std::vector<AtomRecord>& atoms,
                                                                std::string_view sourceFile);
void writeAtomElementEntropyCsv(const AtomElementEntropyAnalysisResult& result,
                                const std::filesystem::path& outputPath);
void writeAtomElementEntropyPlotSvg(const AtomElementEntropyAnalysisResult& result,
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
SpringBondPotentialAnalysisResult
buildSpringBondPotentialAnalysis(const DistanceMatrixResult& distanceMatrix,
                                 const AdjacencyMatrix& adjacencyMatrix,
                                 const std::vector<AtomRecord>& atoms);
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
std::filesystem::path
springBondPotentialOutputJsonPath(const std::filesystem::path& outputDirectory,
                                  const std::filesystem::path& sourceFile,
                                  std::string_view distanceMethod);
std::filesystem::path bioactivityFilteredCsvPath(const std::filesystem::path& outputDirectory,
                                                 const std::filesystem::path& sourceFile);
std::filesystem::path bioactivitySummaryJsonPath(const std::filesystem::path& outputDirectory,
                                                 const std::filesystem::path& sourceFile);
std::filesystem::path bioactivityPlotSvgPath(const std::filesystem::path& outputDirectory,
                                             const std::filesystem::path& sourceFile);
std::filesystem::path posteriorBioactivityCsvPath(const std::filesystem::path& outputDirectory,
                                                  const std::filesystem::path& sourceFile);
std::filesystem::path
posteriorBioactivitySummaryJsonPath(const std::filesystem::path& outputDirectory,
                                    const std::filesystem::path& sourceFile);
std::filesystem::path
binomialActivityDistributionCsvPath(const std::filesystem::path& outputDirectory,
                                    const std::filesystem::path& sourceFile);
std::filesystem::path
binomialActivityDistributionSummaryJsonPath(const std::filesystem::path& outputDirectory,
                                            const std::filesystem::path& sourceFile);
std::filesystem::path chiSquareActivityAidTypeCsvPath(const std::filesystem::path& outputDirectory,
                                                      const std::filesystem::path& sourceFile);
std::filesystem::path
chiSquareActivityAidTypeSummaryJsonPath(const std::filesystem::path& outputDirectory,
                                        const std::filesystem::path& sourceFile);
std::filesystem::path hillDoseResponseCsvPath(const std::filesystem::path& outputDirectory,
                                              const std::filesystem::path& sourceFile);
std::filesystem::path hillDoseResponseSummaryJsonPath(const std::filesystem::path& outputDirectory,
                                                      const std::filesystem::path& sourceFile);
std::filesystem::path hillDoseResponsePlotSvgPath(const std::filesystem::path& outputDirectory,
                                                  const std::filesystem::path& sourceFile);
std::filesystem::path activityValueStatisticsCsvPath(const std::filesystem::path& outputDirectory,
                                                     const std::filesystem::path& sourceFile);
std::filesystem::path
activityValueStatisticsSummaryJsonPath(const std::filesystem::path& outputDirectory,
                                       const std::filesystem::path& sourceFile);
std::filesystem::path
activityValueStatisticsPlotSvgPath(const std::filesystem::path& outputDirectory,
                                   const std::filesystem::path& sourceFile);
std::filesystem::path gradientDescentCsvPath(const std::filesystem::path& outputDirectory,
                                             const std::filesystem::path& sourceFile);
std::filesystem::path gradientDescentSummaryJsonPath(const std::filesystem::path& outputDirectory,
                                                     const std::filesystem::path& sourceFile);
std::filesystem::path gradientDescentLossPlotSvgPath(const std::filesystem::path& outputDirectory,
                                                     const std::filesystem::path& sourceFile);
std::filesystem::path gradientDescentFitPlotSvgPath(const std::filesystem::path& outputDirectory,
                                                    const std::filesystem::path& sourceFile);
std::filesystem::path atomElementEntropyCsvPath(const std::filesystem::path& outputDirectory,
                                                const std::filesystem::path& sourceFile);
std::filesystem::path atomElementEntropySummaryJsonPath(const std::filesystem::path& outputDirectory,
                                                        const std::filesystem::path& sourceFile);
std::filesystem::path atomElementEntropyPlotSvgPath(const std::filesystem::path& outputDirectory,
                                                    const std::filesystem::path& sourceFile);
} // namespace pubchem
