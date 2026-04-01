#include "cid4_opencv.hpp"

#include <algorithm>
#include <cmath>
#include <stdexcept>

namespace pubchem {
namespace {
float safeSpan(const float value)
{
    return value > 0.0F ? value : 1.0F;
}
} // namespace

OverlayLayout buildOverlayLayout(const SceneData& scene,
                                 const int canvasWidth,
                                 const int canvasHeight,
                                 const int padding)
{
    if (canvasWidth <= 0 || canvasHeight <= 0) {
        throw std::invalid_argument("Overlay canvas dimensions must be positive");
    }

    if (padding < 0 || padding * 2 >= canvasWidth || padding * 2 >= canvasHeight) {
        throw std::invalid_argument("Overlay padding must leave drawable content area");
    }

    const float minX = scene.bounds.minimum[0];
    const float maxX = scene.bounds.maximum[0];
    const float minY = scene.bounds.minimum[1];
    const float maxY = scene.bounds.maximum[1];
    const float spanX = safeSpan(maxX - minX);
    const float spanY = safeSpan(maxY - minY);
    const float drawableWidth = static_cast<float>(canvasWidth - padding * 2);
    const float drawableHeight = static_cast<float>(canvasHeight - padding * 2);
    const float scale = std::min(drawableWidth / spanX, drawableHeight / spanY);

    auto project = [&](const std::array<float, 3>& position) {
        const float x = static_cast<float>(padding) + ((position[0] - minX) * scale);
        const float y = static_cast<float>(canvasHeight - padding) - ((position[1] - minY) * scale);
        return std::array<float, 2>{x, y};
    };

    OverlayLayout layout{
        .canvasWidth = canvasWidth,
        .canvasHeight = canvasHeight,
        .padding = padding,
        .scale = scale,
        .contentMinimum = {minX, minY},
        .contentMaximum = {maxX, maxY},
    };

    layout.atoms.reserve(scene.atoms.size());
    for (const SceneAtom& atom : scene.atoms) {
        layout.atoms.push_back(OverlayAtomPoint{
            .atomId = atom.atomId,
            .elementSymbol = atom.elementSymbol,
            .position = project(atom.position),
        });
    }

    layout.bonds.reserve(scene.bonds.size());
    for (const SceneBond& bond : scene.bonds) {
        layout.bonds.push_back(OverlayBondSegment{
            .sourceAtomId = bond.sourceAtomId,
            .targetAtomId = bond.targetAtomId,
            .order = bond.order,
            .start = layout.atoms.at(bond.sourceIndex).position,
            .end = layout.atoms.at(bond.targetIndex).position,
        });
    }

    return layout;
}

std::vector<std::filesystem::path> defaultConformerImagePaths(const std::filesystem::path& dataDir)
{
    std::vector<std::filesystem::path> paths;
    for (int index = 1; index <= 6; ++index) {
        paths.push_back(
            dataDir / ("1-Amino-2-propanol_Conformer3D_large(" + std::to_string(index) + ").png"));
    }

    return paths;
}

nlohmann::json toJson(const OverlayLayout& layout)
{
    nlohmann::json atoms = nlohmann::json::array();
    for (const OverlayAtomPoint& atom : layout.atoms) {
        atoms.push_back({
            {"atomId", atom.atomId},
            {"elementSymbol", atom.elementSymbol},
            {"position", {atom.position[0], atom.position[1]}},
        });
    }

    nlohmann::json bonds = nlohmann::json::array();
    for (const OverlayBondSegment& bond : layout.bonds) {
        bonds.push_back({
            {"sourceAtomId", bond.sourceAtomId},
            {"targetAtomId", bond.targetAtomId},
            {"order", bond.order},
            {"start", {bond.start[0], bond.start[1]}},
            {"end", {bond.end[0], bond.end[1]}},
        });
    }

    return {
        {"canvasWidth", layout.canvasWidth},
        {"canvasHeight", layout.canvasHeight},
        {"padding", layout.padding},
        {"scale", layout.scale},
        {"contentMinimum", {layout.contentMinimum[0], layout.contentMinimum[1]}},
        {"contentMaximum", {layout.contentMaximum[0], layout.contentMaximum[1]}},
        {"atoms", atoms},
        {"bonds", bonds},
    };
}

nlohmann::json toJson(const std::vector<ConformerImagePairScore>& scores)
{
    nlohmann::json pairs = nlohmann::json::array();
    for (const ConformerImagePairScore& score : scores) {
        pairs.push_back({
            {"leftImage", score.leftImage},
            {"rightImage", score.rightImage},
            {"meanAbsoluteDifference", score.meanAbsoluteDifference},
        });
    }

    return {{"pairScores", pairs}};
}
} // namespace pubchem
