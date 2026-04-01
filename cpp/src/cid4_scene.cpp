#include "cid4_scene.hpp"

#include <algorithm>
#include <fstream>
#include <limits>
#include <map>
#include <stdexcept>
#include <string_view>

#include <nlohmann/json.hpp>

namespace pubchem {
namespace {
using Json = nlohmann::json;

class SceneParseError : public std::runtime_error {
  public:
    using std::runtime_error::runtime_error;
};

std::vector<int> jsonToIntVector(const Json& value, std::string_view fieldName)
{
    if (!value.is_array()) {
        throw SceneParseError(std::string(fieldName) + " must be an array");
    }

    std::vector<int> parsed;
    parsed.reserve(value.size());
    for (const auto& item : value) {
        parsed.push_back(item.get<int>());
    }
    return parsed;
}

std::vector<float> jsonToFloatVector(const Json& value, std::string_view fieldName)
{
    if (!value.is_array()) {
        throw SceneParseError(std::string(fieldName) + " must be an array");
    }

    std::vector<float> parsed;
    parsed.reserve(value.size());
    for (const auto& item : value) {
        parsed.push_back(item.get<float>());
    }
    return parsed;
}

std::string symbolForAtomicNumber(const int atomicNumber)
{
    switch (atomicNumber) {
    case 1:
        return "H";
    case 6:
        return "C";
    case 7:
        return "N";
    case 8:
        return "O";
    default:
        return "Z" + std::to_string(atomicNumber);
    }
}

SceneBounds computeBounds(const std::vector<SceneAtom>& atoms)
{
    SceneBounds bounds{
        .minimum = {std::numeric_limits<float>::max(),
                    std::numeric_limits<float>::max(),
                    std::numeric_limits<float>::max()},
        .maximum = {std::numeric_limits<float>::lowest(),
                    std::numeric_limits<float>::lowest(),
                    std::numeric_limits<float>::lowest()},
        .center = {0.0F, 0.0F, 0.0F},
    };

    for (const SceneAtom& atom : atoms) {
        for (std::size_t axis = 0; axis < 3; ++axis) {
            bounds.minimum[axis] = std::min(bounds.minimum[axis], atom.position[axis]);
            bounds.maximum[axis] = std::max(bounds.maximum[axis], atom.position[axis]);
        }
    }

    for (std::size_t axis = 0; axis < 3; ++axis) {
        bounds.center[axis] = (bounds.minimum[axis] + bounds.maximum[axis]) * 0.5F;
    }

    return bounds;
}
} // namespace

SceneData loadSceneData(const std::filesystem::path& jsonPath)
{
    std::ifstream input(jsonPath);
    if (!input) {
        throw SceneParseError("Unable to open scene file: " + jsonPath.string());
    }

    Json root;
    input >> root;

    const Json& compounds = root.at("PC_Compounds");
    if (!compounds.is_array() || compounds.empty()) {
        throw SceneParseError("PC_Compounds must contain at least one entry");
    }

    const Json& compound = compounds.at(0);
    const int compoundId = compound.at("id").at("id").at("cid").get<int>();
    const std::vector<int> atomIds = jsonToIntVector(compound.at("atoms").at("aid"), "atoms.aid");
    const std::vector<int> atomElements =
        jsonToIntVector(compound.at("atoms").at("element"), "atoms.element");

    if (atomIds.size() != atomElements.size()) {
        throw SceneParseError("atoms.aid and atoms.element must have the same length");
    }

    const Json& coords = compound.at("coords");
    if (!coords.is_array() || coords.empty()) {
        throw SceneParseError("coords must contain at least one coordinate block");
    }

    const Json& coordinateBlock = coords.at(0);
    const std::vector<int> coordinateAtomIds =
        jsonToIntVector(coordinateBlock.at("aid"), "coords[0].aid");

    const Json& conformers = coordinateBlock.at("conformers");
    if (!conformers.is_array() || conformers.empty()) {
        throw SceneParseError("coords[0].conformers must contain at least one entry");
    }

    const Json& conformer = conformers.at(0);
    const std::vector<float> xCoordinates = jsonToFloatVector(conformer.at("x"), "conformer.x");
    const std::vector<float> yCoordinates = jsonToFloatVector(conformer.at("y"), "conformer.y");
    std::vector<float> zCoordinates;
    bool hasZCoordinates = false;
    if (conformer.contains("z")) {
        zCoordinates = jsonToFloatVector(conformer.at("z"), "conformer.z");
        hasZCoordinates = true;
    }
    else {
        zCoordinates.assign(xCoordinates.size(), 0.0F);
    }

    if (coordinateAtomIds.size() != xCoordinates.size() ||
        coordinateAtomIds.size() != yCoordinates.size() ||
        coordinateAtomIds.size() != zCoordinates.size()) {
        throw SceneParseError("Coordinate arrays must align with coords[0].aid");
    }

    std::map<int, std::size_t> coordinateIndexByAtomId;
    for (std::size_t index = 0; index < coordinateAtomIds.size(); ++index) {
        coordinateIndexByAtomId.emplace(coordinateAtomIds[index], index);
    }

    std::vector<SceneAtom> atoms;
    atoms.reserve(atomIds.size());
    std::map<int, std::size_t> atomIndexById;
    for (std::size_t index = 0; index < atomIds.size(); ++index) {
        const int atomId = atomIds[index];
        const auto coordinateIterator = coordinateIndexByAtomId.find(atomId);
        if (coordinateIterator == coordinateIndexByAtomId.end()) {
            throw SceneParseError("Missing coordinates for atom id " + std::to_string(atomId));
        }

        const std::size_t coordinateIndex = coordinateIterator->second;
        atoms.push_back(SceneAtom{
            .atomId = atomId,
            .atomicNumber = atomElements[index],
            .elementSymbol = symbolForAtomicNumber(atomElements[index]),
            .position = {xCoordinates[coordinateIndex],
                         yCoordinates[coordinateIndex],
                         zCoordinates[coordinateIndex]},
        });
        atomIndexById.emplace(atomId, index);
    }

    const std::vector<int> bondAid1 =
        jsonToIntVector(compound.at("bonds").at("aid1"), "bonds.aid1");
    const std::vector<int> bondAid2 =
        jsonToIntVector(compound.at("bonds").at("aid2"), "bonds.aid2");
    const std::vector<int> bondOrder =
        jsonToIntVector(compound.at("bonds").at("order"), "bonds.order");
    if (bondAid1.size() != bondAid2.size() || bondAid1.size() != bondOrder.size()) {
        throw SceneParseError("Bond arrays must have matching lengths");
    }

    std::vector<SceneBond> bonds;
    bonds.reserve(bondAid1.size());
    for (std::size_t index = 0; index < bondAid1.size(); ++index) {
        const auto sourceIterator = atomIndexById.find(bondAid1[index]);
        const auto targetIterator = atomIndexById.find(bondAid2[index]);
        if (sourceIterator == atomIndexById.end() || targetIterator == atomIndexById.end()) {
            throw SceneParseError("Bond references an unknown atom id");
        }

        bonds.push_back(SceneBond{
            .sourceAtomId = bondAid1[index],
            .targetAtomId = bondAid2[index],
            .order = bondOrder[index],
            .sourceIndex = sourceIterator->second,
            .targetIndex = targetIterator->second,
        });
    }

    return SceneData{
        .sourceFile = jsonPath.filename().string(),
        .compoundId = compoundId,
        .hasZCoordinates = hasZCoordinates,
        .bounds = computeBounds(atoms),
        .atoms = std::move(atoms),
        .bonds = std::move(bonds),
    };
}
} // namespace pubchem
