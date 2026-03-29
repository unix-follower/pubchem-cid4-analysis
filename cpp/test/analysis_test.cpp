#include <gtest/gtest.h>

#include "analysis.hpp"

#include <cmath>
#include <stdexcept>

namespace {
pubchem::AdjacencyMatrix sampleSpectrumMatrix()
{
    return pubchem::AdjacencyMatrix{
        .sourceFile = "sample.json",
        .method = "arrays",
        .atomIds = {1, 2, 3},
        .values = {{0, 1, 0}, {1, 0, 2}, {0, 2, 0}},
    };
}

std::vector<std::vector<double>> multiplyMatrices(const std::vector<std::vector<double>>& left,
                                                  const std::vector<std::vector<double>>& right)
{
    std::vector<std::vector<double>> product(left.size(),
                                             std::vector<double>(right.front().size(), 0.0));

    for (std::size_t rowIndex = 0; rowIndex < left.size(); ++rowIndex) {
        for (std::size_t columnIndex = 0; columnIndex < right.front().size(); ++columnIndex) {
            for (std::size_t innerIndex = 0; innerIndex < right.size(); ++innerIndex) {
                product[rowIndex][columnIndex] +=
                    left[rowIndex][innerIndex] * right[innerIndex][columnIndex];
            }
        }
    }

    return product;
}

std::vector<std::vector<double>> toDoubleMatrix(const std::vector<std::vector<int>>& values)
{
    std::vector<std::vector<double>> matrix(values.size(), std::vector<double>(values.size(), 0.0));
    for (std::size_t rowIndex = 0; rowIndex < values.size(); ++rowIndex) {
        for (std::size_t columnIndex = 0; columnIndex < values[rowIndex].size(); ++columnIndex) {
            matrix[rowIndex][columnIndex] = static_cast<double>(values[rowIndex][columnIndex]);
        }
    }

    return matrix;
}

std::vector<std::vector<double>> diagonalMatrix(const std::vector<double>& diagonal)
{
    std::vector<std::vector<double>> matrix(diagonal.size(),
                                            std::vector<double>(diagonal.size(), 0.0));
    for (std::size_t index = 0; index < diagonal.size(); ++index) {
        matrix[index][index] = diagonal[index];
    }

    return matrix;
}

void expectReconstructionMatches(const pubchem::AdjacencyMatrix& adjacencyMatrix,
                                 const pubchem::EigendecompositionResult& eigendecomposition)
{
    const auto left =
        multiplyMatrices(toDoubleMatrix(adjacencyMatrix.values), eigendecomposition.eigenvectors);
    const auto right = multiplyMatrices(eigendecomposition.eigenvectors,
                                        diagonalMatrix(eigendecomposition.eigenvalues));

    for (std::size_t rowIndex = 0; rowIndex < left.size(); ++rowIndex) {
        for (std::size_t columnIndex = 0; columnIndex < left[rowIndex].size(); ++columnIndex) {
            EXPECT_NEAR(left[rowIndex][columnIndex], right[rowIndex][columnIndex], 1.0e-8);
        }
    }
}
} // namespace

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

TEST(AdjacencyHelpersTest, SupportedMethodsIncludeArraysAndArmadillo)
{
    EXPECT_EQ(pubchem::supportedAdjacencyMethods(),
              (std::vector<std::string>{"arrays", "armadillo", "boost-graph"}));
}

TEST(AdjacencyHelpersTest, ParseAdjacencyMethodRejectsUnsupportedValues)
{
    EXPECT_THROW(static_cast<void>(pubchem::parseAdjacencyMethod("lemon")), std::invalid_argument);
}

TEST(AdjacencyStrategiesTest, ArraysStrategyBuildsWeightedSymmetricMatrix)
{
    const pubchem::NormalizedAdjacencyInput input{
        .atomIds = {1, 2, 3},
        .bonds =
            {
                {.sourceAtomId = 1,
                 .targetAtomId = 2,
                 .weight = 1,
                 .sourceIndex = 0,
                 .targetIndex = 1},
                {.sourceAtomId = 2,
                 .targetAtomId = 3,
                 .weight = 2,
                 .sourceIndex = 1,
                 .targetIndex = 2},
            },
    };

    const auto matrix = pubchem::buildAdjacencyMatrix(input, "sample.json", "arrays");

    EXPECT_EQ(matrix.method, "arrays");
    EXPECT_EQ(matrix.values, (std::vector<std::vector<int>>{{0, 1, 0}, {1, 0, 2}, {0, 2, 0}}));
}

TEST(AdjacencyStrategiesTest, ArmadilloStrategyMatchesArraysStrategy)
{
    const pubchem::NormalizedAdjacencyInput input{
        .atomIds = {1, 2, 3, 4},
        .bonds =
            {
                {.sourceAtomId = 1,
                 .targetAtomId = 3,
                 .weight = 1,
                 .sourceIndex = 0,
                 .targetIndex = 2},
                {.sourceAtomId = 2,
                 .targetAtomId = 4,
                 .weight = 3,
                 .sourceIndex = 1,
                 .targetIndex = 3},
            },
    };

    const auto arraysMatrix = pubchem::buildAdjacencyMatrix(input, "sample.json", "arrays");
    const auto armadilloMatrix = pubchem::buildAdjacencyMatrix(input, "sample.json", "armadillo");
    const auto boostGraphMatrix =
        pubchem::buildAdjacencyMatrix(input, "sample.json", "boost-graph");

    EXPECT_EQ(armadilloMatrix.method, "armadillo");
    EXPECT_EQ(armadilloMatrix.atomIds, arraysMatrix.atomIds);
    EXPECT_EQ(armadilloMatrix.values, arraysMatrix.values);
    EXPECT_EQ(boostGraphMatrix.method, "boost-graph");
    EXPECT_EQ(boostGraphMatrix.atomIds, arraysMatrix.atomIds);
    EXPECT_EQ(boostGraphMatrix.values, arraysMatrix.values);
}

TEST(AdjacencyStrategiesTest, BoostGraphStrategyBuildsWeightedSymmetricMatrix)
{
    const pubchem::NormalizedAdjacencyInput input{
        .atomIds = {1, 2, 3},
        .bonds =
            {
                {.sourceAtomId = 1,
                 .targetAtomId = 2,
                 .weight = 1,
                 .sourceIndex = 0,
                 .targetIndex = 1},
                {.sourceAtomId = 1,
                 .targetAtomId = 3,
                 .weight = 4,
                 .sourceIndex = 0,
                 .targetIndex = 2},
            },
    };

    const auto matrix = pubchem::buildAdjacencyMatrix(input, "sample.json", "boost-graph");

    EXPECT_EQ(matrix.method, "boost-graph");
    EXPECT_EQ(matrix.values, (std::vector<std::vector<int>>{{0, 1, 4}, {1, 0, 0}, {4, 0, 0}}));
}

TEST(AdjacencyHelpersTest, AdjacencyOutputPathIncludesMethodSuffix)
{
    const auto path = pubchem::adjacencyOutputJsonPath(
        "/tmp/out", "Conformer3D_COMPOUND_CID_4(1).json", "armadillo");
    EXPECT_EQ(path.filename().string(),
              "Conformer3D_COMPOUND_CID_4(1).armadillo.adjacency_matrix.json");
}

TEST(EigendecompositionHelpersTest, SupportedMethodsIncludeArmadilloAndBoost)
{
    EXPECT_EQ(pubchem::supportedEigendecompositionMethods(),
              (std::vector<std::string>{"armadillo", "boost"}));
}

TEST(EigendecompositionHelpersTest, ParseMethodRejectsUnsupportedValues)
{
    EXPECT_THROW(static_cast<void>(pubchem::parseEigendecompositionMethod("lapack")),
                 std::invalid_argument);
}

TEST(EigendecompositionHelpersTest, OutputPathIncludesMethodSuffix)
{
    const auto path = pubchem::eigendecompositionOutputJsonPath(
        "/tmp/out", "Conformer3D_COMPOUND_CID_4(1).json", "boost");
    EXPECT_EQ(path.filename().string(),
              "Conformer3D_COMPOUND_CID_4(1).boost.eigendecomposition.json");
}

TEST(EigendecompositionStrategiesTest, ArmadilloComputesSortedSpectrum)
{
    const auto result = pubchem::buildEigendecomposition(sampleSpectrumMatrix(), "armadillo");

    EXPECT_EQ(result.method, "armadillo");
    ASSERT_EQ(result.eigenvalues.size(), 3U);
    EXPECT_LE(result.eigenvalues[0], result.eigenvalues[1]);
    EXPECT_LE(result.eigenvalues[1], result.eigenvalues[2]);
    EXPECT_EQ(result.atomIds, (std::vector<int>{1, 2, 3}));
    ASSERT_EQ(result.eigenvectors.size(), 3U);
    EXPECT_EQ(result.eigenvectors.front().size(), 3U);
    expectReconstructionMatches(sampleSpectrumMatrix(), result);
}

TEST(EigendecompositionStrategiesTest, BoostMatchesArmadilloEigenvalues)
{
    const auto adjacencyMatrix = sampleSpectrumMatrix();
    const auto armadilloResult = pubchem::buildEigendecomposition(adjacencyMatrix, "armadillo");
    const auto boostResult = pubchem::buildEigendecomposition(adjacencyMatrix, "boost");

    EXPECT_EQ(boostResult.method, "boost");
    ASSERT_EQ(boostResult.eigenvalues.size(), armadilloResult.eigenvalues.size());
    ASSERT_EQ(boostResult.eigenvectors.size(), 3U);
    EXPECT_EQ(boostResult.eigenvectors.front().size(), 3U);

    for (std::size_t index = 0; index < armadilloResult.eigenvalues.size(); ++index) {
        EXPECT_NEAR(boostResult.eigenvalues[index], armadilloResult.eigenvalues[index], 1.0e-8);
    }

    expectReconstructionMatches(adjacencyMatrix, boostResult);
}
