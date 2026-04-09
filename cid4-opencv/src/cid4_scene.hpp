#pragma once

#include <array>
#include <cstddef>
#include <filesystem>
#include <string>
#include <vector>

namespace pubchem {
struct SceneBounds {
    std::array<float, 3> minimum;
    std::array<float, 3> maximum;
    std::array<float, 3> center;
};

struct SceneAtom {
    int atomId;
    int atomicNumber;
    std::string elementSymbol;
    std::array<float, 3> position;
};

struct SceneBond {
    int sourceAtomId;
    int targetAtomId;
    int order;
    std::size_t sourceIndex;
    std::size_t targetIndex;
};

struct SceneData {
    std::string sourceFile;
    int compoundId;
    bool hasZCoordinates;
    SceneBounds bounds;
    std::vector<SceneAtom> atoms;
    std::vector<SceneBond> bonds;
};

SceneData loadSceneData(const std::filesystem::path& jsonPath);
} // namespace pubchem
