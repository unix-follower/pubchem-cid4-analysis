#include "analysis.hpp"

#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>

#include <GraphMol/Atom.h>
#include <GraphMol/Descriptors/MolDescriptors.h>
#include <GraphMol/FileParsers/MolSupplier.h>
#include <nlohmann/json.hpp>

namespace {
class SdfReadError : public std::runtime_error {
  public:
    using std::runtime_error::runtime_error;
};

struct CommandLineOptions {
    std::filesystem::path sdfFile = "Conformer3D_COMPOUND_CID_4(1).sdf";
    std::filesystem::path adjacencyJsonFile = "Conformer3D_COMPOUND_CID_4(1).json";
    std::filesystem::path bioactivityFile = "pubchem_cid_4_bioactivity.csv";
    std::string adjacencyMethod = "armadillo";
    std::string eigenMethod = "armadillo";
    std::string laplacianMethod = "armadillo";
    std::string distanceMethod = "json";
};

std::filesystem::path defaultDataDir()
{
    return std::filesystem::path(PUBCHEM_DEFAULT_DATA_DIR);
}

std::filesystem::path resolveDataDir()
{
    if (const char* value = std::getenv("DATA_DIR"); value != nullptr && *value != '\0') {
        return std::filesystem::path(value);
    }

    return defaultDataDir();
}

std::string hybridizationToString(const RDKit::Atom::HybridizationType hybridization)
{
    switch (hybridization) {
    case RDKit::Atom::HybridizationType::UNSPECIFIED:
        return "UNSPECIFIED";
    case RDKit::Atom::HybridizationType::S:
        return "S";
    case RDKit::Atom::HybridizationType::SP:
        return "SP";
    case RDKit::Atom::HybridizationType::SP2:
        return "SP2";
    case RDKit::Atom::HybridizationType::SP3:
        return "SP3";
    case RDKit::Atom::HybridizationType::SP2D:
        return "SP2D";
    case RDKit::Atom::HybridizationType::SP3D:
        return "SP3D";
    case RDKit::Atom::HybridizationType::SP3D2:
        return "SP3D2";
    case RDKit::Atom::HybridizationType::OTHER:
        return "OTHER";
    }

    return "UNKNOWN";
}

void printUsage(std::ostream& output)
{
    output << "Usage: app [--sdf <file>] [--json <file>] [--bioactivity <file>]"
           << " [--method <arrays|armadillo|boost-graph>]"
           << " [--eigenmethod <armadillo|boost>] [--laplacian-method <armadillo|boost>]"
           << " [--distance-method <json|sdf>]\n";
}

CommandLineOptions parseArguments(int argc, char* argv[])
{
    CommandLineOptions options;

    for (int index = 1; index < argc; ++index) {
        const std::string argument = argv[index];

        if (argument == "--help") {
            printUsage(std::cout);
            std::exit(0);
        }

        auto readValue = [&](const std::string_view flagName) -> std::string {
            if (index + 1 >= argc) {
                throw std::invalid_argument("Missing value for " + std::string(flagName));
            }

            ++index;
            return argv[index];
        };

        if (argument == "--sdf") {
            options.sdfFile = readValue("--sdf");
            continue;
        }

        if (argument == "--json") {
            options.adjacencyJsonFile = readValue("--json");
            continue;
        }

        if (argument == "--bioactivity") {
            options.bioactivityFile = readValue("--bioactivity");
            continue;
        }

        if (argument == "--method") {
            options.adjacencyMethod = pubchem::parseAdjacencyMethod(readValue("--method"));
            continue;
        }

        if (argument == "--eigenmethod") {
            options.eigenMethod =
                pubchem::parseEigendecompositionMethod(readValue("--eigenmethod"));
            continue;
        }

        if (argument == "--laplacian-method") {
            options.laplacianMethod =
                pubchem::parseLaplacianMethod(readValue("--laplacian-method"));
            continue;
        }

        if (argument == "--distance-method") {
            options.distanceMethod = pubchem::parseDistanceMethod(readValue("--distance-method"));
            continue;
        }

        throw std::invalid_argument("Unknown argument: " + argument);
    }

    return options;
}

pubchem::AnalysisResult analyzeSdf(const std::filesystem::path& sdfPath)
{
    RDKit::v1::SDMolSupplier supplier(sdfPath.string(), true, false, true);

    std::vector<double> molecularWeights;
    std::vector<double> exactMasses;
    std::vector<pubchem::AtomRecord> atoms;

    while (!supplier.atEnd()) {
        std::unique_ptr<RDKit::ROMol> molecule(supplier.next());
        if (!molecule) {
            continue;
        }

        molecularWeights.push_back(RDKit::Descriptors::calcAMW(*molecule));
        exactMasses.push_back(RDKit::Descriptors::calcExactMW(*molecule));

        for (const RDKit::Atom* atom : molecule->atoms()) {
            atoms.push_back(pubchem::AtomRecord{
                .index = static_cast<int>(atom->getIdx()),
                .bondCount = static_cast<int>(atom->getDegree()),
                .charge = atom->getFormalCharge(),
                .implicitHydrogenCount = static_cast<int>(atom->getNumImplicitHs()),
                .totalHydrogenCount = static_cast<int>(atom->getTotalNumHs()),
                .atomicNumber = atom->getAtomicNum(),
                .symbol = atom->getSymbol(),
                .valency = static_cast<int>(atom->getValence(RDKit::Atom::ValenceType::EXPLICIT)),
                .isAromatic = atom->getIsAromatic(),
                .mass = atom->getMass(),
                .hybridization = hybridizationToString(atom->getHybridization()),
            });
        }
    }

    if (molecularWeights.empty()) {
        throw SdfReadError("No valid molecules were read from the SDF file");
    }

    return pubchem::AnalysisResult{
        .sourceFile = sdfPath.filename().string(),
        .averageMolecularWeight = pubchem::averageOrZero(molecularWeights),
        .exactMolecularMass = pubchem::averageOrZero(exactMasses),
        .moleculeCount = molecularWeights.size(),
        .atoms = std::move(atoms),
    };
}

nlohmann::json toJson(const pubchem::AnalysisResult& result)
{
    nlohmann::json atoms = nlohmann::json::array();
    for (const auto& atom : result.atoms) {
        atoms.push_back({
            {"index", atom.index},
            {"bondCount", atom.bondCount},
            {"charge", atom.charge},
            {"implicitHydrogenCount", atom.implicitHydrogenCount},
            {"totalHydrogenCount", atom.totalHydrogenCount},
            {"atomicNumber", atom.atomicNumber},
            {"symbol", atom.symbol},
            {"valency", atom.valency},
            {"isAromatic", atom.isAromatic},
            {"mass", atom.mass},
            {"hybridization", atom.hybridization},
        });
    }

    return {
        {"sourceFile", result.sourceFile},
        {"moleculeCount", result.moleculeCount},
        {"averageMolecularWeight", result.averageMolecularWeight},
        {"exactMolecularMass", result.exactMolecularMass},
        {"atoms", atoms},
    };
}

nlohmann::json toJson(const pubchem::AdjacencyMatrix& adjacencyMatrix)
{
    return {
        {"sourceFile", adjacencyMatrix.sourceFile},
        {"method", adjacencyMatrix.method},
        {"atomIds", adjacencyMatrix.atomIds},
        {"adjacencyMatrix", adjacencyMatrix.values},
    };
}

nlohmann::json toJson(const pubchem::EigendecompositionResult& eigendecomposition)
{
    return {
        {"sourceFile", eigendecomposition.sourceFile},
        {"method", eigendecomposition.method},
        {"atomIds", eigendecomposition.atomIds},
        {"eigenvalues", eigendecomposition.eigenvalues},
        {"eigenvectors", eigendecomposition.eigenvectors},
    };
}

nlohmann::json toJson(const pubchem::LaplacianAnalysisResult& laplacianAnalysis)
{
    return {
        {"sourceFile", laplacianAnalysis.sourceFile},
        {"method", laplacianAnalysis.method},
        {"atomIds", laplacianAnalysis.atomIds},
        {"degreeVector", laplacianAnalysis.degreeVector},
        {"laplacianMatrix", laplacianAnalysis.laplacianMatrix},
        {"laplacianEigenvalues", laplacianAnalysis.laplacianEigenvalues},
        {"laplacianEigenvectors", laplacianAnalysis.laplacianEigenvectors},
        {"nullSpace",
         {
             {"eigenvalues", laplacianAnalysis.nullSpace.eigenvalues},
             {"eigenvectors", laplacianAnalysis.nullSpace.eigenvectors},
             {"tolerance", laplacianAnalysis.nullSpace.tolerance},
             {"numZeroEigenvalues", laplacianAnalysis.nullSpace.numZeroEigenvalues},
             {"smallestNonZeroEigenvalue", laplacianAnalysis.nullSpace.smallestNonZeroEigenvalue},
         }},
        {"connectedComponents",
         {
             {"labels", laplacianAnalysis.connectedComponents.labels},
             {"numComponents", laplacianAnalysis.connectedComponents.numComponents},
             {"componentAtomIds", laplacianAnalysis.connectedComponents.componentAtomIds},
             {"verificationBoostGraphCount",
              laplacianAnalysis.connectedComponents.verificationBoostGraphCount},
         }},
        {"metadata",
         {
             {"atomCount", laplacianAnalysis.metadata.atomCount},
             {"bondCount", laplacianAnalysis.metadata.bondCount},
             {"laplacianRank", laplacianAnalysis.metadata.laplacianRank},
             {"graphIsConnected", laplacianAnalysis.metadata.graphIsConnected},
         }},
    };
}

nlohmann::json toJson(const pubchem::DistanceMatrixResult& distanceMatrix)
{
    return {
        {"sourceFile", distanceMatrix.sourceFile},
        {"method", distanceMatrix.method},
        {"atomIds", distanceMatrix.atomIds},
        {"xyzCoordinates", distanceMatrix.xyzCoordinates},
        {"distanceMatrix", distanceMatrix.distanceMatrix},
        {"metadata",
         {
             {"atomCount", distanceMatrix.metadata.atomCount},
             {"coordinateDimension", distanceMatrix.metadata.coordinateDimension},
             {"units", distanceMatrix.metadata.units},
         }},
    };
}

nlohmann::json toJson(const pubchem::BondedDistanceAnalysisResult& bondedDistanceAnalysis)
{
    nlohmann::json bondedAtomPairs = nlohmann::json::array();
    for (const auto& pair : bondedDistanceAnalysis.bondedAtomPairs) {
        bondedAtomPairs.push_back({{"atomId1", pair.atomId1}, {"atomId2", pair.atomId2}});
    }

    auto pairDistancesToJson = [](const std::vector<pubchem::AtomPairDistance>& pairDistances) {
        nlohmann::json values = nlohmann::json::array();
        for (const auto& pairDistance : pairDistances) {
            values.push_back({{"atomId1", pairDistance.atomId1},
                              {"atomId2", pairDistance.atomId2},
                              {"distanceAngstrom", pairDistance.distanceAngstrom}});
        }
        return values;
    };

    auto statisticsToJson = [](const pubchem::BondedDistanceStatistics& statistics) {
        return nlohmann::json{{"count", statistics.count},
                              {"minDistanceAngstrom", statistics.minDistanceAngstrom},
                              {"meanDistanceAngstrom", statistics.meanDistanceAngstrom},
                              {"stdDistanceAngstrom", statistics.stdDistanceAngstrom},
                              {"q25DistanceAngstrom", statistics.q25DistanceAngstrom},
                              {"medianDistanceAngstrom", statistics.medianDistanceAngstrom},
                              {"q75DistanceAngstrom", statistics.q75DistanceAngstrom},
                              {"maxDistanceAngstrom", statistics.maxDistanceAngstrom}};
    };

    return {
        {"atomIds", bondedDistanceAnalysis.atomIds},
        {"bondedAtomPairs", bondedAtomPairs},
        {"bondedPairDistances", pairDistancesToJson(bondedDistanceAnalysis.bondedPairDistances)},
        {"nonbondedPairDistances",
         pairDistancesToJson(bondedDistanceAnalysis.nonbondedPairDistances)},
        {"bondedDistances", statisticsToJson(bondedDistanceAnalysis.bondedDistances)},
        {"nonbondedDistances", statisticsToJson(bondedDistanceAnalysis.nonbondedDistances)},
        {"comparison",
         {{"meanDistanceDifferenceAngstrom",
           bondedDistanceAnalysis.comparison.meanDistanceDifferenceAngstrom},
          {"nonbondedToBondedMeanRatio",
           bondedDistanceAnalysis.comparison.nonbondedToBondedMeanRatio}}},
        {"metadata",
         {{"atomCount", bondedDistanceAnalysis.metadata.atomCount},
          {"bondedPairCount", bondedDistanceAnalysis.metadata.bondedPairCount},
          {"nonbondedPairCount", bondedDistanceAnalysis.metadata.nonbondedPairCount},
          {"totalUniquePairCount", bondedDistanceAnalysis.metadata.totalUniquePairCount},
          {"sourceDistanceMethod", bondedDistanceAnalysis.metadata.sourceDistanceMethod},
          {"units", bondedDistanceAnalysis.metadata.units}}},
    };
}

nlohmann::json toJson(const pubchem::BondAngleAnalysisResult& bondAngleAnalysis)
{
    nlohmann::json triplets = nlohmann::json::array();
    for (const auto& triplet : bondAngleAnalysis.bondAngleTriplets) {
        triplets.push_back({{"atomIdA", triplet.atomIdA},
                            {"atomIdBCenter", triplet.atomIdBCenter},
                            {"atomIdC", triplet.atomIdC}});
    }

    nlohmann::json bondAngles = nlohmann::json::array();
    for (const auto& bondAngle : bondAngleAnalysis.bondAngles) {
        bondAngles.push_back({{"atomIdA", bondAngle.atomIdA},
                              {"atomIdBCenter", bondAngle.atomIdBCenter},
                              {"atomIdC", bondAngle.atomIdC},
                              {"angleDegrees", bondAngle.angleDegrees}});
    }

    return {
        {"atomIds", bondAngleAnalysis.atomIds},
        {"bondAngleTriplets", triplets},
        {"bondAngles", bondAngles},
        {"statistics",
         {{"count", bondAngleAnalysis.statistics.count},
          {"minAngleDegrees", bondAngleAnalysis.statistics.minAngleDegrees},
          {"meanAngleDegrees", bondAngleAnalysis.statistics.meanAngleDegrees},
          {"stdAngleDegrees", bondAngleAnalysis.statistics.stdAngleDegrees},
          {"q25AngleDegrees", bondAngleAnalysis.statistics.q25AngleDegrees},
          {"medianAngleDegrees", bondAngleAnalysis.statistics.medianAngleDegrees},
          {"q75AngleDegrees", bondAngleAnalysis.statistics.q75AngleDegrees},
          {"maxAngleDegrees", bondAngleAnalysis.statistics.maxAngleDegrees}}},
        {"metadata",
         {{"atomCount", bondAngleAnalysis.metadata.atomCount},
          {"bondedAngleTripletCount", bondAngleAnalysis.metadata.bondedAngleTripletCount},
          {"sourceDistanceMethod", bondAngleAnalysis.metadata.sourceDistanceMethod},
          {"units", bondAngleAnalysis.metadata.units},
          {"selectionRule", bondAngleAnalysis.metadata.selectionRule}}},
    };
}

nlohmann::json toJson(const pubchem::BioactivityAnalysisResult& bioactivity)
{
    return {
        {"sourceFile", bioactivity.sourceFile},
        {"rowCounts",
         {{"totalRows", bioactivity.rowCounts.totalRows},
          {"rowsWithNumericActivityValue", bioactivity.rowCounts.rowsWithNumericActivityValue},
          {"rowsWithIc50ActivityType", bioactivity.rowCounts.rowsWithIc50ActivityType},
          {"retainedIc50Rows", bioactivity.rowCounts.retainedIc50Rows},
          {"droppedRows", bioactivity.rowCounts.droppedRows}}},
        {"statistics",
         {{"ic50Um",
           {{"min", bioactivity.statistics.ic50Um.min},
            {"median", bioactivity.statistics.ic50Um.median},
            {"max", bioactivity.statistics.ic50Um.max}}},
          {"pIC50",
           {{"min", bioactivity.statistics.pIC50.min},
            {"median", bioactivity.statistics.pIC50.median},
            {"max", bioactivity.statistics.pIC50.max}}}}},
        {"analysis",
         {{"transform", bioactivity.analysis.transform},
          {"interpretation", bioactivity.analysis.interpretation},
          {"observedIc50DomainUm", bioactivity.analysis.observedIc50DomainUm},
          {"strongestRetainedMeasurement",
           {{"bioactivityId", bioactivity.analysis.strongestRetainedMeasurement.bioactivityId},
            {"bioAssayAid", bioactivity.analysis.strongestRetainedMeasurement.bioAssayAid},
            {"ic50Um", bioactivity.analysis.strongestRetainedMeasurement.ic50Um},
            {"pIC50", bioactivity.analysis.strongestRetainedMeasurement.pIC50}}},
          {"weakestRetainedMeasurement",
           {{"bioactivityId", bioactivity.analysis.weakestRetainedMeasurement.bioactivityId},
            {"bioAssayAid", bioactivity.analysis.weakestRetainedMeasurement.bioAssayAid},
            {"ic50Um", bioactivity.analysis.weakestRetainedMeasurement.ic50Um},
            {"pIC50", bioactivity.analysis.weakestRetainedMeasurement.pIC50}}}}},
    };
}

nlohmann::json toJson(const pubchem::GradientDescentAnalysisResult& gradientDescent)
{
    nlohmann::json atomRows = nlohmann::json::array();
    for (const auto& atomRow : gradientDescent.summary.dataset.atomRows) {
        atomRows.push_back({{"index", atomRow.index},
                            {"symbol", atomRow.symbol},
                            {"mass", atomRow.mass},
                            {"atomicNumber", atomRow.atomicNumber}});
    }

    const auto& optimization = gradientDescent.summary.optimization;
    return {
        {"sourceFile", gradientDescent.sourceFile},
        {"dataset",
         {{"rowCount", gradientDescent.summary.dataset.rowCount},
          {"feature", gradientDescent.summary.dataset.feature},
          {"target", gradientDescent.summary.dataset.target},
          {"featureMatrixShape", gradientDescent.summary.dataset.featureMatrixShape},
          {"massRange", gradientDescent.summary.dataset.massRange},
          {"atomicNumberRange", gradientDescent.summary.dataset.atomicNumberRange},
          {"atomRows", atomRows}}},
        {"model",
         {{"predictionEquation", gradientDescent.summary.model.predictionEquation},
          {"objectiveName", gradientDescent.summary.model.objectiveName},
          {"objectiveEquation", gradientDescent.summary.model.objectiveEquation},
          {"mseEquation", gradientDescent.summary.model.meanSquaredErrorEquation},
          {"gradientEquation", gradientDescent.summary.model.gradientEquation},
          {"featureName", gradientDescent.summary.model.featureName},
          {"targetName", gradientDescent.summary.model.targetName}}},
        {"optimization",
         {{"initialWeight", optimization.initialWeight},
          {"finalWeight", optimization.finalWeight},
          {"learningRate", optimization.learningRate},
          {"epochs", optimization.epochs},
          {"closedFormWeight", optimization.closedFormWeight},
          {"initialSumSquaredError", optimization.initialSumSquaredError},
          {"finalSumSquaredError", optimization.finalSumSquaredError},
          {"initialMse", optimization.initialMeanSquaredError},
          {"finalMse", optimization.finalMeanSquaredError},
          {"weightErrorVsClosedForm", optimization.weightErrorVsClosedForm},
          {"gradientChecks",
           {{"initialWeight",
             {{"analytic", optimization.gradientChecks.initialWeight.analytic},
              {"finiteDifference", optimization.gradientChecks.initialWeight.finiteDifference}}},
            {"finalWeight",
             {{"analytic", optimization.gradientChecks.finalWeight.analytic},
              {"finiteDifference", optimization.gradientChecks.finalWeight.finiteDifference}}}}},
          {"lossTrace",
           {{"monotonicNonincreasingMse",
             optimization.lossTrace.monotonicNonincreasingMeanSquaredError},
            {"bestEpoch", optimization.lossTrace.bestEpoch}}}}},
    };
}
} // namespace

nlohmann::json toJson(const pubchem::HillDoseResponseAnalysisResult& hillAnalysis)
{
    nlohmann::json activityTypeCounts = nlohmann::json::object();
    for (const auto& entry : hillAnalysis.activityTypeCounts) {
        activityTypeCounts[entry.activityType] = entry.count;
    }

    nlohmann::json representativeRows = nlohmann::json::array();
    for (const auto& row : hillAnalysis.analysis.representativeRows) {
        representativeRows.push_back({
            {"bioactivityId", row.bioactivityId},
            {"bioAssayAid", row.bioAssayAid},
            {"activityType", row.activityType},
            {"targetName", row.targetName},
            {"activityValue", row.activityValue},
            {"inferredKActivityValue", row.inferredKActivityValue},
            {"aucTrapezoidReferenceCurve", row.aucTrapezoidReferenceCurve},
            {"log10MidpointConcentration", row.log10MidpointConcentration},
        });
    }

    nlohmann::json linearInflection = nullptr;
    if (hillAnalysis.analysis.linearConcentrationInflection.has_value()) {
        const auto& inflection = *hillAnalysis.analysis.linearConcentrationInflection;
        linearInflection = {
            {"formula", inflection.formula},
            {"responseFormula", inflection.responseFormula},
            {"relativeToK", inflection.relativeToK},
            {"normalizedResponse", inflection.normalizedResponse},
        };
    }

    return {
        {"sourceFile", hillAnalysis.sourceFile},
        {"rowCounts",
         {{"totalRows", hillAnalysis.rowCounts.totalRows},
          {"rowsWithNumericActivityValue", hillAnalysis.rowCounts.rowsWithNumericActivityValue},
          {"rowsWithPositiveActivityValue", hillAnalysis.rowCounts.rowsWithPositiveActivityValue},
          {"rowsFlaggedHasDoseResponseCurve",
           hillAnalysis.rowCounts.rowsFlaggedHasDoseResponseCurve},
          {"retainedRows", hillAnalysis.rowCounts.retainedRows},
          {"retainedRowsFlaggedHasDoseResponseCurve",
           hillAnalysis.rowCounts.retainedRowsFlaggedHasDoseResponseCurve},
          {"retainedUniqueBioassays", hillAnalysis.rowCounts.retainedUniqueBioassays}}},
        {"statistics",
         {{"activityValueAsInferredK",
           {{"min", hillAnalysis.statistics.activityValueAsInferredK.min},
            {"median", hillAnalysis.statistics.activityValueAsInferredK.median},
            {"max", hillAnalysis.statistics.activityValueAsInferredK.max}}},
          {"midpointFirstDerivative",
           {{"min", hillAnalysis.statistics.midpointFirstDerivative.min},
            {"median", hillAnalysis.statistics.midpointFirstDerivative.median},
                        {"max", hillAnalysis.statistics.midpointFirstDerivative.max}}},
                    {"aucTrapezoidReferenceCurve",
                     {{"min", hillAnalysis.statistics.aucTrapezoidReferenceCurve.min},
                        {"median", hillAnalysis.statistics.aucTrapezoidReferenceCurve.median},
                        {"max", hillAnalysis.statistics.aucTrapezoidReferenceCurve.max}}}}},
        {"activityTypeCounts", activityTypeCounts},
        {"analysis",
         {{"model", hillAnalysis.analysis.model},
          {"equation", hillAnalysis.analysis.equation},
          {"firstDerivative", hillAnalysis.analysis.firstDerivative},
          {"secondDerivative", hillAnalysis.analysis.secondDerivative},
          {"referenceHillCoefficientN", hillAnalysis.analysis.referenceHillCoefficientN},
          {"parameterInterpretation", hillAnalysis.analysis.parameterInterpretation},
          {"midpointInLogConcentrationSpace",
           {{"condition", hillAnalysis.analysis.midpointInLogConcentrationSpace.condition},
            {"response", hillAnalysis.analysis.midpointInLogConcentrationSpace.response},
            {"interpretation",
             hillAnalysis.analysis.midpointInLogConcentrationSpace.interpretation}}},
             {"aucTrapezoidReferenceCurve",
              {{"integrationMethod", hillAnalysis.analysis.aucTrapezoidReferenceCurve.integrationMethod},
                {"curveBasis", hillAnalysis.analysis.aucTrapezoidReferenceCurve.curveBasis},
                {"concentrationBoundsDefinition",
                 hillAnalysis.analysis.aucTrapezoidReferenceCurve.concentrationBoundsDefinition},
                {"gridSize", hillAnalysis.analysis.aucTrapezoidReferenceCurve.gridSize},
                {"concentrationUnits",
                 hillAnalysis.analysis.aucTrapezoidReferenceCurve.concentrationUnits},
                {"interpretation",
                 hillAnalysis.analysis.aucTrapezoidReferenceCurve.interpretation}}},
          {"linearConcentrationInflection", linearInflection},
          {"fitStatus", hillAnalysis.analysis.fitStatus},
          {"representativeRows", representativeRows},
          {"notes", hillAnalysis.analysis.notes}}},
    };
}

int main(int argc, char* argv[])
{
    try {
        const CommandLineOptions options = parseArguments(argc, argv);
        const std::filesystem::path dataDir = resolveDataDir();
        const std::filesystem::path sdfPath = dataDir / options.sdfFile;

        const pubchem::AnalysisResult result = analyzeSdf(sdfPath);
        const std::filesystem::path outputDir = pubchem::outputDirectoryFor(dataDir);
        const std::filesystem::path outputPath =
            pubchem::outputJsonPath(outputDir, options.sdfFile);

        const std::filesystem::path adjacencyJsonPath = dataDir / options.adjacencyJsonFile;
        const std::filesystem::path bioactivityCsvPath = dataDir / options.bioactivityFile;
        const pubchem::NormalizedAdjacencyInput adjacencyInput =
            pubchem::loadAdjacencyInput(adjacencyJsonPath);
        const pubchem::DistanceMatrixInput distanceInput{
            .atomIds = adjacencyInput.atomIds,
            .jsonPath = adjacencyJsonPath,
            .sdfPath = sdfPath,
        };
        const pubchem::DistanceMatrixResult distanceMatrix =
            pubchem::buildDistanceMatrix(distanceInput, options.distanceMethod);
        const std::filesystem::path distanceOutputPath = pubchem::distanceOutputJsonPath(
            outputDir, options.adjacencyJsonFile, distanceMatrix.method);
        const pubchem::AdjacencyMatrix adjacencyMatrix = pubchem::buildAdjacencyMatrix(
            adjacencyInput, options.adjacencyJsonFile.filename().string(), options.adjacencyMethod);
        const pubchem::BondedDistanceAnalysisResult bondedDistanceAnalysis =
            pubchem::buildBondedDistanceAnalysis(distanceMatrix, adjacencyMatrix);
        const std::filesystem::path bondedDistanceOutputPath =
            pubchem::bondedDistanceOutputJsonPath(
                outputDir,
                options.adjacencyJsonFile,
                bondedDistanceAnalysis.metadata.sourceDistanceMethod);
        const pubchem::BondAngleAnalysisResult bondAngleAnalysis =
            pubchem::buildBondAngleAnalysis(distanceMatrix, adjacencyMatrix);
        const std::filesystem::path bondAngleOutputPath = pubchem::bondAngleOutputJsonPath(
            outputDir, options.adjacencyJsonFile, bondAngleAnalysis.metadata.sourceDistanceMethod);
        const std::filesystem::path adjacencyOutputPath = pubchem::adjacencyOutputJsonPath(
            outputDir, options.adjacencyJsonFile, adjacencyMatrix.method);
        const pubchem::EigendecompositionResult eigendecomposition =
            pubchem::buildEigendecomposition(adjacencyMatrix, options.eigenMethod);
        const std::filesystem::path eigendecompositionOutputPath =
            pubchem::eigendecompositionOutputJsonPath(
                outputDir, options.adjacencyJsonFile, eigendecomposition.method);
        const pubchem::LaplacianAnalysisResult laplacianAnalysis =
            pubchem::buildLaplacianAnalysis(adjacencyMatrix, options.laplacianMethod);
        const std::filesystem::path laplacianOutputPath = pubchem::laplacianOutputJsonPath(
            outputDir, options.adjacencyJsonFile, laplacianAnalysis.method);
        const pubchem::BioactivityAnalysisResult bioactivityAnalysis =
            pubchem::buildBioactivityAnalysis(bioactivityCsvPath);
        const std::filesystem::path bioactivityCsvOutputPath =
            pubchem::bioactivityFilteredCsvPath(outputDir, options.bioactivityFile);
        const std::filesystem::path bioactivitySummaryOutputPath =
            pubchem::bioactivitySummaryJsonPath(outputDir, options.bioactivityFile);
        const std::filesystem::path bioactivityPlotOutputPath =
            pubchem::bioactivityPlotSvgPath(outputDir, options.bioactivityFile);
        const pubchem::HillDoseResponseAnalysisResult hillDoseResponseAnalysis =
            pubchem::buildHillDoseResponseAnalysis(bioactivityCsvPath);
        const std::filesystem::path hillDoseResponseCsvOutputPath =
            pubchem::hillDoseResponseCsvPath(outputDir, options.bioactivityFile);
        const std::filesystem::path hillDoseResponseSummaryOutputPath =
            pubchem::hillDoseResponseSummaryJsonPath(outputDir, options.bioactivityFile);
        const std::filesystem::path hillDoseResponsePlotOutputPath =
            pubchem::hillDoseResponsePlotSvgPath(outputDir, options.bioactivityFile);
        const pubchem::GradientDescentAnalysisResult gradientDescentAnalysis =
            pubchem::buildGradientDescentAnalysis(result.atoms,
                                                  options.sdfFile.filename().string());
        const std::filesystem::path gradientDescentCsvOutputPath =
            pubchem::gradientDescentCsvPath(outputDir, options.sdfFile);
        const std::filesystem::path gradientDescentSummaryOutputPath =
            pubchem::gradientDescentSummaryJsonPath(outputDir, options.sdfFile);
        const std::filesystem::path gradientDescentLossPlotOutputPath =
            pubchem::gradientDescentLossPlotSvgPath(outputDir, options.sdfFile);
        const std::filesystem::path gradientDescentFitPlotOutputPath =
            pubchem::gradientDescentFitPlotSvgPath(outputDir, options.sdfFile);

        std::filesystem::create_directories(outputDir);

        std::ofstream output(outputPath);
        output << std::setw(2) << toJson(result) << '\n';

        std::ofstream adjacencyOutput(adjacencyOutputPath);
        adjacencyOutput << std::setw(2) << toJson(adjacencyMatrix) << '\n';

        std::ofstream distanceOutput(distanceOutputPath);
        distanceOutput << std::setw(2) << toJson(distanceMatrix) << '\n';

        std::ofstream bondedDistanceOutput(bondedDistanceOutputPath);
        bondedDistanceOutput << std::setw(2) << toJson(bondedDistanceAnalysis) << '\n';

        std::ofstream bondAngleOutput(bondAngleOutputPath);
        bondAngleOutput << std::setw(2) << toJson(bondAngleAnalysis) << '\n';

        std::ofstream eigendecompositionOutput(eigendecompositionOutputPath);
        eigendecompositionOutput << std::setw(2) << toJson(eigendecomposition) << '\n';

        std::ofstream laplacianOutput(laplacianOutputPath);
        laplacianOutput << std::setw(2) << toJson(laplacianAnalysis) << '\n';

        pubchem::writeBioactivityFilteredCsv(bioactivityAnalysis, bioactivityCsvOutputPath);

        std::ofstream bioactivitySummaryOutput(bioactivitySummaryOutputPath);
        bioactivitySummaryOutput << std::setw(2) << toJson(bioactivityAnalysis) << '\n';

        pubchem::writeBioactivityPlotSvg(bioactivityAnalysis, bioactivityPlotOutputPath);

        pubchem::writeHillDoseResponseCsv(hillDoseResponseAnalysis, hillDoseResponseCsvOutputPath);

        std::ofstream hillDoseResponseSummaryOutput(hillDoseResponseSummaryOutputPath);
        hillDoseResponseSummaryOutput << std::setw(2) << toJson(hillDoseResponseAnalysis) << '\n';

        pubchem::writeHillDoseResponsePlotSvg(hillDoseResponseAnalysis,
                                              hillDoseResponsePlotOutputPath);

        pubchem::writeGradientDescentCsv(gradientDescentAnalysis, gradientDescentCsvOutputPath);

        std::ofstream gradientDescentSummaryOutput(gradientDescentSummaryOutputPath);
        gradientDescentSummaryOutput << std::setw(2) << toJson(gradientDescentAnalysis) << '\n';

        pubchem::writeGradientDescentLossPlotSvg(gradientDescentAnalysis,
                                                 gradientDescentLossPlotOutputPath);
        pubchem::writeGradientDescentFitPlotSvg(gradientDescentAnalysis,
                                                gradientDescentFitPlotOutputPath);

        std::cout << "Average molecular weight: " << result.averageMolecularWeight << '\n';
        std::cout << "Exact molecular mass: " << result.exactMolecularMass << '\n';
        std::cout << "Atom records written to: " << outputPath << '\n';
        std::cout << "Distance method: " << distanceMatrix.method << '\n';
        std::cout << "Distance matrix written to: " << distanceOutputPath << '\n';
        std::cout << "Bonded distance analysis written to: " << bondedDistanceOutputPath << '\n';
        std::cout << "Bond angle analysis written to: " << bondAngleOutputPath << '\n';
        std::cout << "Adjacency matrix method: " << adjacencyMatrix.method << '\n';
        std::cout << "Adjacency matrix written to: " << adjacencyOutputPath << '\n';
        std::cout << "Eigendecomposition method: " << eigendecomposition.method << '\n';
        std::cout << "Eigendecomposition written to: " << eigendecompositionOutputPath << '\n';
        std::cout << "Laplacian method: " << laplacianAnalysis.method << '\n';
        std::cout << "Laplacian analysis written to: " << laplacianOutputPath << '\n';
        std::cout << "Bioactivity rows written to: " << bioactivityCsvOutputPath << '\n';
        std::cout << "Bioactivity summary written to: " << bioactivitySummaryOutputPath << '\n';
        std::cout << "Bioactivity plot written to: " << bioactivityPlotOutputPath << '\n';
        std::cout << "Hill dose-response rows written to: " << hillDoseResponseCsvOutputPath
                  << '\n';
        std::cout << "Hill dose-response summary written to: " << hillDoseResponseSummaryOutputPath
                  << '\n';
        std::cout << "Hill dose-response plot written to: " << hillDoseResponsePlotOutputPath
                  << '\n';
        std::cout << "Gradient descent trace written to: " << gradientDescentCsvOutputPath << '\n';
        std::cout << "Gradient descent summary written to: " << gradientDescentSummaryOutputPath
                  << '\n';
        std::cout << "Gradient descent loss plot written to: " << gradientDescentLossPlotOutputPath
                  << '\n';
        std::cout << "Gradient descent fit plot written to: " << gradientDescentFitPlotOutputPath
                  << '\n';
    }
    catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        printUsage(std::cerr);
        return 1;
    }

    return 0;
}
