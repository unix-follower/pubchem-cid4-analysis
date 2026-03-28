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
} // namespace

int main(int argc, char* argv[])
{
    try {
        const std::filesystem::path dataDir = resolveDataDir();
        const std::filesystem::path sourceFile =
            argc > 1 ? std::filesystem::path(argv[1])
                     : std::filesystem::path("Conformer3D_COMPOUND_CID_4(1).sdf");
        const std::filesystem::path sdfPath = dataDir / sourceFile;

        const pubchem::AnalysisResult result = analyzeSdf(sdfPath);
        const std::filesystem::path outputDir = pubchem::outputDirectoryFor(dataDir);
        const std::filesystem::path outputPath = pubchem::outputJsonPath(outputDir, sourceFile);

        std::filesystem::create_directories(outputDir);

        std::ofstream output(outputPath);
        output << std::setw(2) << toJson(result) << '\n';

        std::cout << "Average molecular weight: " << result.averageMolecularWeight << '\n';
        std::cout << "Exact molecular mass: " << result.exactMolecularMass << '\n';
        std::cout << "Atom records written to: " << outputPath << '\n';
    }
    catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }

    return 0;
}
