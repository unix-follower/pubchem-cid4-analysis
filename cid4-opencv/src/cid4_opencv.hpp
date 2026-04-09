#pragma once

#include "cid4_scene.hpp"

#include <array>
#include <cstddef>
#include <filesystem>
#include <string>
#include <vector>

#include <nlohmann/json.hpp>

namespace pubchem {
struct OverlayAtomPoint {
    int atomId;
    std::string elementSymbol;
    std::array<float, 2> position;
};

struct OverlayBondSegment {
    int sourceAtomId;
    int targetAtomId;
    int order;
    std::array<float, 2> start;
    std::array<float, 2> end;
};

struct OverlayLayout {
    int canvasWidth;
    int canvasHeight;
    int padding;
    float scale;
    std::array<float, 2> contentMinimum;
    std::array<float, 2> contentMaximum;
    std::vector<OverlayAtomPoint> atoms;
    std::vector<OverlayBondSegment> bonds;
};

struct ConformerImagePairScore {
    std::string leftImage;
    std::string rightImage;
    double meanAbsoluteDifference;
};

OverlayLayout
buildOverlayLayout(const SceneData& scene, int canvasWidth, int canvasHeight, int padding);

std::vector<std::filesystem::path> defaultConformerImagePaths(const std::filesystem::path& dataDir);

nlohmann::json toJson(const OverlayLayout& layout);

nlohmann::json toJson(const std::vector<ConformerImagePairScore>& scores);
} // namespace pubchem
