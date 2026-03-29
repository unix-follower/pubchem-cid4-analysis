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
    std::string adjacencyMethod = "armadillo";
    std::string eigenMethod = "armadillo";
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
    output << "Usage: app [--sdf <file>] [--json <file>] [--method <arrays|armadillo|boost-graph>]"
           << " [--eigenmethod <armadillo|boost>]\n";
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

        if (argument == "--method") {
            options.adjacencyMethod = pubchem::parseAdjacencyMethod(readValue("--method"));
            continue;
        }

        if (argument == "--eigenmethod") {
            options.eigenMethod =
                pubchem::parseEigendecompositionMethod(readValue("--eigenmethod"));
            continue;
        }

        throw std::invalid_argument("Unknown argument: " + argument);
    }

    return options;
}

pubchem::AnalysisResult analyzeSdf(const std::filesystem::path& sdfPath)
{
    RDKit::v1::SDMolSupplier supplier(sdfPath.string(), true, true, true);

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
} // namespace

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
        const pubchem::NormalizedAdjacencyInput adjacencyInput =
            pubchem::loadAdjacencyInput(adjacencyJsonPath);
        const pubchem::AdjacencyMatrix adjacencyMatrix = pubchem::buildAdjacencyMatrix(
            adjacencyInput, options.adjacencyJsonFile.filename().string(), options.adjacencyMethod);
        const std::filesystem::path adjacencyOutputPath = pubchem::adjacencyOutputJsonPath(
            outputDir, options.adjacencyJsonFile, adjacencyMatrix.method);
        const pubchem::EigendecompositionResult eigendecomposition =
            pubchem::buildEigendecomposition(adjacencyMatrix, options.eigenMethod);
        const std::filesystem::path eigendecompositionOutputPath =
            pubchem::eigendecompositionOutputJsonPath(
                outputDir, options.adjacencyJsonFile, eigendecomposition.method);

        std::filesystem::create_directories(outputDir);

        std::ofstream output(outputPath);
        output << std::setw(2) << toJson(result) << '\n';

        std::ofstream adjacencyOutput(adjacencyOutputPath);
        adjacencyOutput << std::setw(2) << toJson(adjacencyMatrix) << '\n';

        std::ofstream eigendecompositionOutput(eigendecompositionOutputPath);
        eigendecompositionOutput << std::setw(2) << toJson(eigendecomposition) << '\n';

        std::cout << "Average molecular weight: " << result.averageMolecularWeight << '\n';
        std::cout << "Exact molecular mass: " << result.exactMolecularMass << '\n';
        std::cout << "Atom records written to: " << outputPath << '\n';
        std::cout << "Adjacency matrix method: " << adjacencyMatrix.method << '\n';
        std::cout << "Adjacency matrix written to: " << adjacencyOutputPath << '\n';
        std::cout << "Eigendecomposition method: " << eigendecomposition.method << '\n';
        std::cout << "Eigendecomposition written to: " << eigendecompositionOutputPath << '\n';
    }
    catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        printUsage(std::cerr);
        return 1;
    }

    return 0;
}
