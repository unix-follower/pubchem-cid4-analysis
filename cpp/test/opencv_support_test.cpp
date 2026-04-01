#include <gtest/gtest.h>

#include "cid4_opencv.hpp"

namespace {
pubchem::SceneData sampleScene()
{
    return pubchem::SceneData{
        .sourceFile = "sample-structure.json",
        .compoundId = 4,
        .hasZCoordinates = false,
        .bounds =
            pubchem::SceneBounds{
                .minimum = {0.0F, -1.0F, 0.0F},
                .maximum = {4.0F, 3.0F, 0.0F},
                .center = {2.0F, 1.0F, 0.0F},
            },
        .atoms =
            {
                pubchem::SceneAtom{.atomId = 1,
                                   .atomicNumber = 8,
                                   .elementSymbol = "O",
                                   .position = {0.0F, 0.0F, 0.0F}},
                pubchem::SceneAtom{.atomId = 2,
                                   .atomicNumber = 6,
                                   .elementSymbol = "C",
                                   .position = {4.0F, 3.0F, 0.0F}},
                pubchem::SceneAtom{.atomId = 3,
                                   .atomicNumber = 1,
                                   .elementSymbol = "H",
                                   .position = {2.0F, -1.0F, 0.0F}},
            },
        .bonds =
            {
                pubchem::SceneBond{.sourceAtomId = 1,
                                   .targetAtomId = 2,
                                   .order = 1,
                                   .sourceIndex = 0,
                                   .targetIndex = 1},
                pubchem::SceneBond{.sourceAtomId = 1,
                                   .targetAtomId = 3,
                                   .order = 1,
                                   .sourceIndex = 0,
                                   .targetIndex = 2},
            },
    };
}
} // namespace

TEST(OpenCvSupportTest, BuildsProjectedOverlayLayoutInsideCanvas)
{
    const pubchem::OverlayLayout layout = pubchem::buildOverlayLayout(sampleScene(), 320, 200, 20);

    ASSERT_EQ(layout.atoms.size(), 3U);
    ASSERT_EQ(layout.bonds.size(), 2U);
    EXPECT_GT(layout.scale, 0.0F);

    for (const auto& atom : layout.atoms) {
        EXPECT_GE(atom.position[0], 20.0F);
        EXPECT_LE(atom.position[0], 300.0F);
        EXPECT_GE(atom.position[1], 20.0F);
        EXPECT_LE(atom.position[1], 180.0F);
    }
}

TEST(OpenCvSupportTest, ReturnsExpectedDefaultConformerImagePaths)
{
    const auto paths = pubchem::defaultConformerImagePaths("/tmp/cid4-data");

    ASSERT_EQ(paths.size(), 6U);
    EXPECT_EQ(paths.front().filename().string(), "1-Amino-2-propanol_Conformer3D_large(1).png");
    EXPECT_EQ(paths.back().filename().string(), "1-Amino-2-propanol_Conformer3D_large(6).png");
}
