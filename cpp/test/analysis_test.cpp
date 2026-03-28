#include <gtest/gtest.h>

#include "analysis.hpp"

TEST(AnalysisHelpersTest, AverageReturnsZeroForEmptyInput)
{
    EXPECT_DOUBLE_EQ(pubchem::averageOrZero({}), 0.0);
}

TEST(AnalysisHelpersTest, AverageComputesArithmeticMean)
{
    EXPECT_DOUBLE_EQ(pubchem::averageOrZero({10.0, 20.0, 30.0}), 20.0);
}

TEST(AnalysisHelpersTest, OutputJsonPathPreservesSourceFilename)
{
    const auto path = pubchem::outputJsonPath("/tmp/out", "Conformer3D_COMPOUND_CID_4(1).sdf");
    EXPECT_EQ(path.filename().string(), "Conformer3D_COMPOUND_CID_4(1).sdf.json");
}
