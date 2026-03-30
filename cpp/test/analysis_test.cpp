#include <gtest/gtest.h>

#include "analysis.hpp"

#include <cmath>
#include <filesystem>
#include <fstream>
#include <numeric>
#include <stdexcept>
#include <string>

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

std::vector<double> rowSums(const std::vector<std::vector<double>>& matrix)
{
    std::vector<double> sums;
    sums.reserve(matrix.size());
    for (const auto& row : matrix) {
        sums.push_back(std::accumulate(row.begin(), row.end(), 0.0));
    }

    return sums;
}

void expectSymmetric(const std::vector<std::vector<double>>& matrix)
{
    for (std::size_t rowIndex = 0; rowIndex < matrix.size(); ++rowIndex) {
        for (std::size_t columnIndex = 0; columnIndex < matrix[rowIndex].size(); ++columnIndex) {
            EXPECT_NEAR(matrix[rowIndex][columnIndex], matrix[columnIndex][rowIndex], 1.0e-8);
        }
    }
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

std::filesystem::path writeTempFile(const std::string& fileName, const std::string& contents)
{
    const auto directory = std::filesystem::temp_directory_path() / "pubchem-cid4-analysis-tests";
    std::filesystem::create_directories(directory);
    const auto filePath = directory / fileName;
    std::ofstream output(filePath);
    output << contents;
    return filePath;
}

pubchem::DistanceMatrixInput sampleDistanceInput(const std::filesystem::path& jsonPath,
                                                 const std::filesystem::path& sdfPath)
{
    return pubchem::DistanceMatrixInput{
        .atomIds = {1, 2, 3},
        .jsonPath = jsonPath,
        .sdfPath = sdfPath,
    };
}

std::filesystem::path repositoryRoot()
{
    return std::filesystem::path(__FILE__).parent_path().parent_path().parent_path();
}

std::string sampleDistanceJson()
{
    return R"json({
    "PC_Compounds": [
        {
            "atoms": {
                "aid": [1, 2, 3],
                "element": [6, 1, 1]
            },
            "bonds": {
                "aid1": [1, 1],
                "aid2": [2, 3],
                "order": [1, 1]
            },
            "coords": [
                {
                    "aid": [2, 1, 3],
                    "conformers": [
                        {
                            "x": [3.0, 0.0, 0.0],
                            "y": [0.0, 0.0, 4.0],
                            "z": [0.0, 0.0, 0.0]
                        }
                    ]
                }
            ]
        }
    ]
})json";
}

std::string sampleBioactivityCsv()
{
    return "Bioactivity_ID,BioAssay_AID,Activity_Type,Activity_Value,Has_Dose_Response_Curve,"
           "Target_Name,citations\n"
           "100909607,158688,IC50,800.0,0,Plasmodium falciparum (malaria parasite P. "
           "falciparum),\"Paper with, comma\"\n"
           "334754348,743069,Potency,21.872400,1,ESR1 - estrogen receptor 1 (human),\"Potency "
           "row\"\n"
           "383459365,1920063,IC50,,1,GNRHR - gonadotropin releasing hormone receptor "
           "(human),\"Missing numeric value\"\n"
           "383457597,1919969,IC50,not-a-number,1,NFE2L2 - NFE2 like bZIP transcription factor 2 "
           "(human),\"Invalid numeric value\"\n";
}

std::vector<pubchem::AtomRecord> sampleGradientAtoms()
{
    return {
        pubchem::AtomRecord{.index = 0,
                            .bondCount = 1,
                            .charge = 0,
                            .implicitHydrogenCount = 0,
                            .totalHydrogenCount = 0,
                            .atomicNumber = 2,
                            .symbol = "He",
                            .valency = 0,
                            .isAromatic = false,
                            .mass = 1.0,
                            .hybridization = "S"},
        pubchem::AtomRecord{.index = 1,
                            .bondCount = 1,
                            .charge = 0,
                            .implicitHydrogenCount = 0,
                            .totalHydrogenCount = 0,
                            .atomicNumber = 4,
                            .symbol = "Be",
                            .valency = 0,
                            .isAromatic = false,
                            .mass = 2.0,
                            .hybridization = "S"},
        pubchem::AtomRecord{.index = 2,
                            .bondCount = 1,
                            .charge = 0,
                            .implicitHydrogenCount = 0,
                            .totalHydrogenCount = 0,
                            .atomicNumber = 6,
                            .symbol = "C",
                            .valency = 0,
                            .isAromatic = false,
                            .mass = 3.0,
                            .hybridization = "SP"},
    };
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

TEST(LaplacianHelpersTest, SupportedMethodsIncludeArmadilloAndBoost)
{
    EXPECT_EQ(pubchem::supportedLaplacianMethods(),
              (std::vector<std::string>{"armadillo", "boost"}));
}

TEST(LaplacianHelpersTest, ParseMethodRejectsUnsupportedValues)
{
    EXPECT_THROW(static_cast<void>(pubchem::parseLaplacianMethod("lapack")), std::invalid_argument);
}

TEST(LaplacianHelpersTest, OutputPathIncludesMethodSuffix)
{
    const auto path =
        pubchem::laplacianOutputJsonPath("/tmp/out", "Conformer3D_COMPOUND_CID_4(1).json", "boost");
    EXPECT_EQ(path.filename().string(),
              "Conformer3D_COMPOUND_CID_4(1).boost.laplacian_analysis.json");
}

TEST(LaplacianStrategiesTest, ArmadilloProducesValidLaplacianAnalysis)
{
    const auto result = pubchem::buildLaplacianAnalysis(sampleSpectrumMatrix(), "armadillo");

    EXPECT_EQ(result.method, "armadillo");
    EXPECT_EQ(result.degreeVector, (std::vector<double>{1.0, 3.0, 2.0}));
    ASSERT_EQ(result.laplacianMatrix.size(), 3U);
    EXPECT_EQ(result.laplacianMatrix.front().size(), 3U);
    expectSymmetric(result.laplacianMatrix);
    for (const auto sum : rowSums(result.laplacianMatrix)) {
        EXPECT_NEAR(sum, 0.0, 1.0e-8);
    }
    ASSERT_EQ(result.laplacianEigenvalues.size(), 3U);
    EXPECT_NEAR(result.laplacianEigenvalues.front(), 0.0, 1.0e-8);
    EXPECT_EQ(result.nullSpace.numZeroEigenvalues, 1U);
    EXPECT_EQ(result.connectedComponents.numComponents, 1U);
    EXPECT_EQ(result.connectedComponents.labels, (std::vector<int>{0, 0, 0}));
    EXPECT_TRUE(result.metadata.graphIsConnected);
}

TEST(LaplacianStrategiesTest, BoostMatchesArmadilloLaplacianEigenvalues)
{
    const auto adjacencyMatrix = sampleSpectrumMatrix();
    const auto armadilloResult = pubchem::buildLaplacianAnalysis(adjacencyMatrix, "armadillo");
    const auto boostResult = pubchem::buildLaplacianAnalysis(adjacencyMatrix, "boost");

    EXPECT_EQ(boostResult.method, "boost");
    EXPECT_EQ(boostResult.degreeVector, armadilloResult.degreeVector);
    EXPECT_EQ(boostResult.connectedComponents.labels, armadilloResult.connectedComponents.labels);
    ASSERT_EQ(boostResult.laplacianEigenvalues.size(), armadilloResult.laplacianEigenvalues.size());
    for (std::size_t index = 0; index < armadilloResult.laplacianEigenvalues.size(); ++index) {
        EXPECT_NEAR(boostResult.laplacianEigenvalues[index],
                    armadilloResult.laplacianEigenvalues[index],
                    1.0e-8);
    }
    expectSymmetric(boostResult.laplacianMatrix);
    for (const auto sum : rowSums(boostResult.laplacianMatrix)) {
        EXPECT_NEAR(sum, 0.0, 1.0e-8);
    }
    EXPECT_EQ(boostResult.nullSpace.numZeroEigenvalues, 1U);
}

TEST(DistanceHelpersTest, SupportedMethodsIncludeJsonAndSdf)
{
    EXPECT_EQ(pubchem::supportedDistanceMethods(), (std::vector<std::string>{"json", "sdf"}));
}

TEST(DistanceHelpersTest, ParseMethodRejectsUnsupportedValues)
{
    EXPECT_THROW(static_cast<void>(pubchem::parseDistanceMethod("rdkit")), std::invalid_argument);
}

TEST(DistanceHelpersTest, OutputPathIncludesMethodSuffix)
{
    const auto path =
        pubchem::distanceOutputJsonPath("/tmp/out", "Conformer3D_COMPOUND_CID_4(1).json", "json");
    EXPECT_EQ(path.filename().string(), "Conformer3D_COMPOUND_CID_4(1).json.distance_matrix.json");
}

TEST(DistanceHelpersTest, BondedDistanceOutputPathIncludesMethodSuffix)
{
    const auto path = pubchem::bondedDistanceOutputJsonPath(
        "/tmp/out", "Conformer3D_COMPOUND_CID_4(1).json", "json");
    EXPECT_EQ(path.filename().string(),
              "Conformer3D_COMPOUND_CID_4(1).json.bonded_distance_analysis.json");
}

TEST(DistanceHelpersTest, BondAngleOutputPathIncludesMethodSuffix)
{
    const auto path =
        pubchem::bondAngleOutputJsonPath("/tmp/out", "Conformer3D_COMPOUND_CID_4(1).json", "json");
    EXPECT_EQ(path.filename().string(),
              "Conformer3D_COMPOUND_CID_4(1).json.bond_angle_analysis.json");
}

TEST(DistanceStrategiesTest, JsonBuildsExpectedDistanceMatrix)
{
    const auto jsonPath = writeTempFile("distance-sample.json", sampleDistanceJson());
    const auto sdfPath = jsonPath;

    const auto result =
        pubchem::buildDistanceMatrix(sampleDistanceInput(jsonPath, sdfPath), "json");

    EXPECT_EQ(result.method, "json");
    EXPECT_EQ(result.atomIds, (std::vector<int>{1, 2, 3}));
    EXPECT_EQ(
        result.xyzCoordinates,
        (std::vector<std::vector<double>>{{0.0, 0.0, 0.0}, {3.0, 0.0, 0.0}, {0.0, 4.0, 0.0}}));
    EXPECT_EQ(
        result.distanceMatrix,
        (std::vector<std::vector<double>>{{0.0, 3.0, 4.0}, {3.0, 0.0, 5.0}, {4.0, 5.0, 0.0}}));
    EXPECT_EQ(result.metadata.atomCount, 3U);
    EXPECT_EQ(result.metadata.coordinateDimension, 3U);
}

TEST(DistanceStrategiesTest, SdfMatchesJsonDistanceMatrix)
{
    const auto dataDirectory = repositoryRoot() / "data";
    const auto jsonPath = dataDirectory / "Conformer3D_COMPOUND_CID_4(1).json";
    const auto sdfPath = dataDirectory / "Conformer3D_COMPOUND_CID_4(1).sdf";
    const auto adjacencyInput = pubchem::loadAdjacencyInput(jsonPath);
    const auto input = pubchem::DistanceMatrixInput{
        .atomIds = adjacencyInput.atomIds,
        .jsonPath = jsonPath,
        .sdfPath = sdfPath,
    };

    const auto jsonResult = pubchem::buildDistanceMatrix(input, "json");
    const auto sdfResult = pubchem::buildDistanceMatrix(input, "sdf");

    EXPECT_EQ(sdfResult.method, "sdf");
    EXPECT_EQ(sdfResult.atomIds, jsonResult.atomIds);
    EXPECT_EQ(sdfResult.xyzCoordinates, jsonResult.xyzCoordinates);
    EXPECT_EQ(sdfResult.distanceMatrix, jsonResult.distanceMatrix);
    expectSymmetric(sdfResult.distanceMatrix);
    for (const auto sum : rowSums(sdfResult.distanceMatrix)) {
        EXPECT_GT(sum, 0.0);
    }
    for (std::size_t index = 0; index < sdfResult.distanceMatrix.size(); ++index) {
        EXPECT_DOUBLE_EQ(sdfResult.distanceMatrix[index][index], 0.0);
    }
}

TEST(DistanceStrategiesTest, BondedDistanceAnalysisPartitionsDistancesAndSummaries)
{
    const pubchem::DistanceMatrixResult distanceMatrix{
        .sourceFile = "distance-sample.json",
        .method = "json",
        .atomIds = {1, 2, 3},
        .xyzCoordinates = {{0.0, 0.0, 0.0}, {3.0, 0.0, 0.0}, {0.0, 4.0, 0.0}},
        .distanceMatrix = {{0.0, 3.0, 4.0}, {3.0, 0.0, 5.0}, {4.0, 5.0, 0.0}},
        .metadata =
            pubchem::DistanceMatrixMetadata{
                .atomCount = 3U,
                .coordinateDimension = 3U,
                .units = "angstrom",
            },
    };
    const pubchem::AdjacencyMatrix adjacencyMatrix{
        .sourceFile = "distance-sample.json",
        .method = "arrays",
        .atomIds = {1, 2, 3},
        .values = {{0, 1, 1}, {1, 0, 0}, {1, 0, 0}},
    };

    const auto result = pubchem::buildBondedDistanceAnalysis(distanceMatrix, adjacencyMatrix);

    EXPECT_EQ(result.atomIds, (std::vector<int>{1, 2, 3}));
    ASSERT_EQ(result.bondedAtomPairs.size(), 2U);
    EXPECT_EQ(result.metadata.atomCount, 3U);
    EXPECT_EQ(result.metadata.bondedPairCount, 2U);
    EXPECT_EQ(result.metadata.nonbondedPairCount, 1U);
    EXPECT_EQ(result.metadata.totalUniquePairCount, 3U);
    EXPECT_EQ(result.metadata.sourceDistanceMethod, "json");
    EXPECT_EQ(result.metadata.units, "angstrom");
    ASSERT_EQ(result.bondedPairDistances.size(), 2U);
    ASSERT_EQ(result.nonbondedPairDistances.size(), 1U);
    EXPECT_EQ(result.nonbondedPairDistances.front().atomId1, 2);
    EXPECT_EQ(result.nonbondedPairDistances.front().atomId2, 3);
    EXPECT_DOUBLE_EQ(result.nonbondedPairDistances.front().distanceAngstrom, 5.0);
    EXPECT_DOUBLE_EQ(result.bondedDistances.meanDistanceAngstrom, 3.5);
    EXPECT_DOUBLE_EQ(result.bondedDistances.stdDistanceAngstrom, 0.5);
    EXPECT_DOUBLE_EQ(result.bondedDistances.q25DistanceAngstrom, 3.25);
    EXPECT_DOUBLE_EQ(result.bondedDistances.medianDistanceAngstrom, 3.5);
    EXPECT_DOUBLE_EQ(result.bondedDistances.q75DistanceAngstrom, 3.75);
    EXPECT_DOUBLE_EQ(result.nonbondedDistances.meanDistanceAngstrom, 5.0);
    EXPECT_DOUBLE_EQ(result.comparison.meanDistanceDifferenceAngstrom, 1.5);
    EXPECT_DOUBLE_EQ(result.comparison.nonbondedToBondedMeanRatio, 5.0 / 3.5);
}

TEST(DistanceStrategiesTest, BondedDistanceAnalysisMatchesCid4RealData)
{
    const auto dataDirectory = repositoryRoot() / "data";
    const auto jsonPath = dataDirectory / "Conformer3D_COMPOUND_CID_4(1).json";
    const auto sdfPath = dataDirectory / "Conformer3D_COMPOUND_CID_4(1).sdf";
    const auto adjacencyInput = pubchem::loadAdjacencyInput(jsonPath);
    const auto distanceInput = pubchem::DistanceMatrixInput{
        .atomIds = adjacencyInput.atomIds,
        .jsonPath = jsonPath,
        .sdfPath = sdfPath,
    };
    const auto distanceMatrix = pubchem::buildDistanceMatrix(distanceInput, "json");
    const auto adjacencyMatrix =
        pubchem::buildAdjacencyMatrix(adjacencyInput, jsonPath.filename().string(), "arrays");

    const auto result = pubchem::buildBondedDistanceAnalysis(distanceMatrix, adjacencyMatrix);

    EXPECT_EQ(result.metadata.atomCount, 14U);
    EXPECT_EQ(result.metadata.bondedPairCount, 13U);
    EXPECT_EQ(result.metadata.nonbondedPairCount, 78U);
    EXPECT_EQ(result.metadata.totalUniquePairCount, 91U);
    EXPECT_NEAR(result.bondedDistances.meanDistanceAngstrom, 1.1940559475938086, 1.0e-12);
    EXPECT_NEAR(result.nonbondedDistances.meanDistanceAngstrom, 2.9383026626251145, 1.0e-12);
    EXPECT_NEAR(result.comparison.nonbondedToBondedMeanRatio, 2.460774696986527, 1.0e-12);
}

TEST(DistanceStrategiesTest, BondAngleAnalysisComputesTripletsAndStatistics)
{
    const pubchem::DistanceMatrixResult distanceMatrix{
        .sourceFile = "distance-sample.json",
        .method = "json",
        .atomIds = {1, 2, 3},
        .xyzCoordinates = {{1.0, 0.0, 0.0}, {0.0, 0.0, 0.0}, {0.0, 1.0, 0.0}},
        .distanceMatrix = {{0.0, 1.0, std::sqrt(2.0)}, {1.0, 0.0, 1.0}, {std::sqrt(2.0), 1.0, 0.0}},
        .metadata =
            pubchem::DistanceMatrixMetadata{
                .atomCount = 3U,
                .coordinateDimension = 3U,
                .units = "angstrom",
            },
    };
    const pubchem::AdjacencyMatrix adjacencyMatrix{
        .sourceFile = "distance-sample.json",
        .method = "arrays",
        .atomIds = {1, 2, 3},
        .values = {{0, 1, 0}, {1, 0, 1}, {0, 1, 0}},
    };

    const auto result = pubchem::buildBondAngleAnalysis(distanceMatrix, adjacencyMatrix);

    EXPECT_EQ(result.atomIds, (std::vector<int>{1, 2, 3}));
    ASSERT_EQ(result.bondAngleTriplets.size(), 1U);
    EXPECT_EQ(result.bondAngleTriplets.front().atomIdA, 1);
    EXPECT_EQ(result.bondAngleTriplets.front().atomIdBCenter, 2);
    EXPECT_EQ(result.bondAngleTriplets.front().atomIdC, 3);
    ASSERT_EQ(result.bondAngles.size(), 1U);
    EXPECT_DOUBLE_EQ(result.bondAngles.front().angleDegrees, 90.0);
    EXPECT_EQ(result.metadata.atomCount, 3U);
    EXPECT_EQ(result.metadata.bondedAngleTripletCount, 1U);
    EXPECT_EQ(result.metadata.sourceDistanceMethod, "json");
    EXPECT_EQ(result.metadata.units, "degrees");
    EXPECT_DOUBLE_EQ(result.statistics.meanAngleDegrees, 90.0);
    EXPECT_DOUBLE_EQ(result.statistics.medianAngleDegrees, 90.0);
}

TEST(DistanceStrategiesTest, BondAngleAnalysisMatchesCid4RealData)
{
    const auto dataDirectory = repositoryRoot() / "data";
    const auto jsonPath = dataDirectory / "Conformer3D_COMPOUND_CID_4(1).json";
    const auto sdfPath = dataDirectory / "Conformer3D_COMPOUND_CID_4(1).sdf";
    const auto adjacencyInput = pubchem::loadAdjacencyInput(jsonPath);
    const auto distanceInput = pubchem::DistanceMatrixInput{
        .atomIds = adjacencyInput.atomIds,
        .jsonPath = jsonPath,
        .sdfPath = sdfPath,
    };
    const auto distanceMatrix = pubchem::buildDistanceMatrix(distanceInput, "json");
    const auto adjacencyMatrix =
        pubchem::buildAdjacencyMatrix(adjacencyInput, jsonPath.filename().string(), "arrays");

    const auto result = pubchem::buildBondAngleAnalysis(distanceMatrix, adjacencyMatrix);

    EXPECT_EQ(result.metadata.atomCount, 14U);
    EXPECT_EQ(result.metadata.bondedAngleTripletCount, 22U);
    EXPECT_EQ(result.metadata.sourceDistanceMethod, "json");
    EXPECT_NEAR(result.statistics.meanAngleDegrees, 109.22375164065625, 1.0e-12);
    EXPECT_NEAR(result.statistics.minAngleDegrees, 106.04151155509001, 1.0e-12);
    EXPECT_NEAR(result.statistics.maxAngleDegrees, 113.11659612947966, 1.0e-12);
}

TEST(BioactivityHelpersTest, OutputPathsUseStableSuffixes)
{
    EXPECT_EQ(pubchem::bioactivityFilteredCsvPath("/tmp/out", "pubchem_cid_4_bioactivity.csv")
                  .filename()
                  .string(),
              "pubchem_cid_4_bioactivity.ic50_pic50.csv");
    EXPECT_EQ(pubchem::bioactivitySummaryJsonPath("/tmp/out", "pubchem_cid_4_bioactivity.csv")
                  .filename()
                  .string(),
              "pubchem_cid_4_bioactivity.ic50_pic50.summary.json");
    EXPECT_EQ(pubchem::bioactivityPlotSvgPath("/tmp/out", "pubchem_cid_4_bioactivity.csv")
                  .filename()
                  .string(),
              "pubchem_cid_4_bioactivity.ic50_pic50.svg");
    EXPECT_EQ(pubchem::hillDoseResponseCsvPath("/tmp/out", "pubchem_cid_4_bioactivity.csv")
                  .filename()
                  .string(),
              "pubchem_cid_4_bioactivity.hill_dose_response.csv");
    EXPECT_EQ(pubchem::hillDoseResponseSummaryJsonPath("/tmp/out", "pubchem_cid_4_bioactivity.csv")
                  .filename()
                  .string(),
              "pubchem_cid_4_bioactivity.hill_dose_response.summary.json");
    EXPECT_EQ(pubchem::hillDoseResponsePlotSvgPath("/tmp/out", "pubchem_cid_4_bioactivity.csv")
                  .filename()
                  .string(),
              "pubchem_cid_4_bioactivity.hill_dose_response.svg");
    EXPECT_EQ(pubchem::gradientDescentCsvPath("/tmp/out", "Conformer3D_COMPOUND_CID_4(1).sdf")
                  .filename()
                  .string(),
              "Conformer3D_COMPOUND_CID_4(1).mass_to_atomic_number_gradient_descent.csv");
    EXPECT_EQ(
        pubchem::gradientDescentSummaryJsonPath("/tmp/out", "Conformer3D_COMPOUND_CID_4(1).sdf")
            .filename()
            .string(),
        "Conformer3D_COMPOUND_CID_4(1).mass_to_atomic_number_gradient_descent.summary.json");
    EXPECT_EQ(
        pubchem::gradientDescentLossPlotSvgPath("/tmp/out", "Conformer3D_COMPOUND_CID_4(1).sdf")
            .filename()
            .string(),
        "Conformer3D_COMPOUND_CID_4(1).mass_to_atomic_number_gradient_descent.loss.svg");
    EXPECT_EQ(
        pubchem::gradientDescentFitPlotSvgPath("/tmp/out", "Conformer3D_COMPOUND_CID_4(1).sdf")
            .filename()
            .string(),
        "Conformer3D_COMPOUND_CID_4(1).mass_to_atomic_number_gradient_descent.fit.svg");
}

TEST(GradientDescentStrategiesTest, AnalysisConvergesTowardClosedFormWeight)
{
    const auto result =
        pubchem::buildGradientDescentAnalysis(sampleGradientAtoms(), "sample.sdf", 0.05, 40U);

    EXPECT_EQ(result.sourceFile, "sample.sdf");
    EXPECT_EQ(result.headers,
              (std::vector<std::string>{"epoch", "weight", "gradient", "sum_squared_error", "mse"}));
    ASSERT_EQ(result.traceRows.size(), 41U);
    EXPECT_NEAR(result.summary.optimization.closedFormWeight, 2.0, 1.0e-12);
    EXPECT_NEAR(result.summary.optimization.finalWeight, 2.0, 1.0e-6);
    EXPECT_LT(result.summary.optimization.finalMeanSquaredError,
              result.summary.optimization.initialMeanSquaredError);
    EXPECT_TRUE(result.summary.optimization.lossTrace.monotonicNonincreasingMeanSquaredError);
    EXPECT_EQ(result.summary.optimization.lossTrace.bestEpoch, result.traceRows.back().epoch);
    EXPECT_NEAR(result.summary.optimization.gradientChecks.initialWeight.analytic,
                result.summary.optimization.gradientChecks.initialWeight.finiteDifference,
                1.0e-5);
    EXPECT_NEAR(result.summary.optimization.gradientChecks.finalWeight.analytic,
                result.summary.optimization.gradientChecks.finalWeight.finiteDifference,
                1.0e-5);
    EXPECT_EQ(result.summary.dataset.featureMatrixShape, (std::vector<int>{3, 1}));
}

TEST(GradientDescentStrategiesTest, WritersEmitCsvAndSvgArtifacts)
{
    const auto result =
        pubchem::buildGradientDescentAnalysis(sampleGradientAtoms(), "sample.sdf", 0.05, 20U);
    const auto outputDirectory =
        std::filesystem::temp_directory_path() / "pubchem-cid4-gradient-descent";
    std::filesystem::create_directories(outputDirectory);

    const auto csvPath = outputDirectory / "gradient.csv";
    const auto lossSvgPath = outputDirectory / "gradient.loss.svg";
    const auto fitSvgPath = outputDirectory / "gradient.fit.svg";

    pubchem::writeGradientDescentCsv(result, csvPath);
    pubchem::writeGradientDescentLossPlotSvg(result, lossSvgPath);
    pubchem::writeGradientDescentFitPlotSvg(result, fitSvgPath);

    std::ifstream csvInput(csvPath);
    std::ifstream lossSvgInput(lossSvgPath);
    std::ifstream fitSvgInput(fitSvgPath);
    ASSERT_TRUE(csvInput.good());
    ASSERT_TRUE(lossSvgInput.good());
    ASSERT_TRUE(fitSvgInput.good());

    const std::string csvContents((std::istreambuf_iterator<char>(csvInput)),
                                  std::istreambuf_iterator<char>());
    const std::string lossSvgContents((std::istreambuf_iterator<char>(lossSvgInput)),
                                      std::istreambuf_iterator<char>());
    const std::string fitSvgContents((std::istreambuf_iterator<char>(fitSvgInput)),
                                     std::istreambuf_iterator<char>());

    EXPECT_NE(csvContents.find("sum_squared_error"), std::string::npos);
    EXPECT_NE(csvContents.find("mse"), std::string::npos);
    EXPECT_NE(lossSvgContents.find("Manual Gradient Descent MSE Trace"), std::string::npos);
    EXPECT_NE(fitSvgContents.find("Mass to Atomic Number"), std::string::npos);
    EXPECT_NE(fitSvgContents.find("y_hat ="), std::string::npos);
}

TEST(BioactivityStrategiesTest, AnalysisFiltersIc50RowsAndComputesPic50)
{
    const auto csvPath = writeTempFile("bioactivity-sample.csv", sampleBioactivityCsv());

    const auto result = pubchem::buildBioactivityAnalysis(csvPath);

    EXPECT_EQ(result.sourceFile, "bioactivity-sample.csv");
    EXPECT_EQ(result.rowCounts.totalRows, 4U);
    EXPECT_EQ(result.rowCounts.rowsWithNumericActivityValue, 2U);
    EXPECT_EQ(result.rowCounts.rowsWithIc50ActivityType, 3U);
    EXPECT_EQ(result.rowCounts.retainedIc50Rows, 1U);
    EXPECT_EQ(result.rowCounts.droppedRows, 3U);
    ASSERT_EQ(result.filteredRows.size(), 1U);
    EXPECT_NEAR(result.statistics.ic50Um.min, 800.0, 1.0e-12);
    EXPECT_NEAR(result.statistics.pIC50.max, -2.9030899869919438, 1.0e-12);
    EXPECT_EQ(result.analysis.strongestRetainedMeasurement.bioactivityId, 100909607LL);
    EXPECT_EQ(result.analysis.strongestRetainedMeasurement.bioAssayAid, 158688LL);
    EXPECT_NEAR(result.analysis.strongestRetainedMeasurement.pIC50, -2.9030899869919438, 1.0e-12);
}

TEST(BioactivityStrategiesTest, CsvAndSvgWritersEmitArtifacts)
{
    const auto csvPath = writeTempFile("bioactivity-writer-sample.csv", sampleBioactivityCsv());
    const auto result = pubchem::buildBioactivityAnalysis(csvPath);
    const auto outputDirectory =
        std::filesystem::temp_directory_path() / "pubchem-cid4-bioactivity";
    std::filesystem::create_directories(outputDirectory);

    const auto filteredCsvPath = outputDirectory / "bioactivity.csv";
    const auto plotSvgPath = outputDirectory / "bioactivity.svg";

    pubchem::writeBioactivityFilteredCsv(result, filteredCsvPath);
    pubchem::writeBioactivityPlotSvg(result, plotSvgPath);

    std::ifstream filteredInput(filteredCsvPath);
    std::ifstream svgInput(plotSvgPath);
    ASSERT_TRUE(filteredInput.good());
    ASSERT_TRUE(svgInput.good());

    const std::string filteredContents((std::istreambuf_iterator<char>(filteredInput)),
                                       std::istreambuf_iterator<char>());
    const std::string svgContents((std::istreambuf_iterator<char>(svgInput)),
                                  std::istreambuf_iterator<char>());

    EXPECT_NE(filteredContents.find("IC50_uM"), std::string::npos);
    EXPECT_NE(filteredContents.find("-2.90308998699194"), std::string::npos);
    EXPECT_NE(svgContents.find("<svg"), std::string::npos);
    EXPECT_NE(svgContents.find("Observed IC50 rows"), std::string::npos);
}

TEST(BioactivityStrategiesTest, HillAnalysisBuildsReferenceRowsAndSummary)
{
    const auto csvPath = writeTempFile("bioactivity-hill-sample.csv", sampleBioactivityCsv());

    const auto result = pubchem::buildHillDoseResponseAnalysis(csvPath);

    EXPECT_EQ(result.sourceFile, "bioactivity-hill-sample.csv");
    EXPECT_EQ(result.rowCounts.totalRows, 4U);
    EXPECT_EQ(result.rowCounts.rowsWithNumericActivityValue, 2U);
    EXPECT_EQ(result.rowCounts.rowsWithPositiveActivityValue, 2U);
    EXPECT_EQ(result.rowCounts.rowsFlaggedHasDoseResponseCurve, 3U);
    EXPECT_EQ(result.rowCounts.retainedRows, 2U);
    EXPECT_EQ(result.rowCounts.retainedRowsFlaggedHasDoseResponseCurve, 1U);
    EXPECT_EQ(result.rowCounts.retainedUniqueBioassays, 2U);
    ASSERT_EQ(result.rows.size(), 2U);
    EXPECT_NEAR(result.statistics.activityValueAsInferredK.min, 21.8724, 1.0e-12);
    EXPECT_NEAR(result.statistics.activityValueAsInferredK.max, 800.0, 1.0e-12);
    EXPECT_NEAR(result.statistics.midpointFirstDerivative.max, 1.0 / (4.0 * 21.8724), 1.0e-12);
    EXPECT_NEAR(result.statistics.midpointFirstDerivative.min, 1.0 / (4.0 * 800.0), 1.0e-12);
    EXPECT_EQ(result.analysis.fitStatus, "reference_curve_inferred_from_activity_value");
    EXPECT_EQ(result.analysis.midpointInLogConcentrationSpace.condition, "c = K");
    EXPECT_DOUBLE_EQ(result.analysis.midpointInLogConcentrationSpace.response, 0.5);
    EXPECT_FALSE(result.analysis.linearConcentrationInflection.has_value());
    ASSERT_EQ(result.analysis.representativeRows.size(), 2U);
    EXPECT_EQ(result.analysis.representativeRows.front().bioAssayAid, 743069LL);
    EXPECT_EQ(result.analysis.representativeRows.back().bioAssayAid, 158688LL);
}

TEST(BioactivityStrategiesTest, HillAnalysisSupportsPositiveLinearInflectionForNGreaterThanOne)
{
    const auto csvPath = writeTempFile("bioactivity-hill-n2-sample.csv", sampleBioactivityCsv());

    const auto result = pubchem::buildHillDoseResponseAnalysis(csvPath, 2.0);

    ASSERT_TRUE(result.analysis.linearConcentrationInflection.has_value());
    const auto& inflection = *result.analysis.linearConcentrationInflection;
    EXPECT_NEAR(inflection.relativeToK, std::sqrt(1.0 / 3.0), 1.0e-12);
    EXPECT_NEAR(inflection.normalizedResponse, 0.25, 1.0e-12);
    const auto& firstRow = result.rows.front();
    const auto headers = result.headers;
    const auto linearInflectionColumn =
        std::find(headers.begin(), headers.end(), "linear_inflection_concentration");
    ASSERT_NE(linearInflectionColumn, headers.end());
    const auto columnIndex =
        static_cast<std::size_t>(std::distance(headers.begin(), linearInflectionColumn));
    EXPECT_FALSE(firstRow.at(columnIndex).empty());
}

TEST(BioactivityStrategiesTest, HillCsvAndSvgWritersEmitArtifacts)
{
    const auto csvPath =
        writeTempFile("bioactivity-hill-writer-sample.csv", sampleBioactivityCsv());
    const auto result = pubchem::buildHillDoseResponseAnalysis(csvPath);
    const auto outputDirectory =
        std::filesystem::temp_directory_path() / "pubchem-cid4-hill-bioactivity";
    std::filesystem::create_directories(outputDirectory);

    const auto filteredCsvPath = outputDirectory / "bioactivity.hill.csv";
    const auto plotSvgPath = outputDirectory / "bioactivity.hill.svg";

    pubchem::writeHillDoseResponseCsv(result, filteredCsvPath);
    pubchem::writeHillDoseResponsePlotSvg(result, plotSvgPath);

    std::ifstream filteredInput(filteredCsvPath);
    std::ifstream svgInput(plotSvgPath);
    ASSERT_TRUE(filteredInput.good());
    ASSERT_TRUE(svgInput.good());

    const std::string filteredContents((std::istreambuf_iterator<char>(filteredInput)),
                                       std::istreambuf_iterator<char>());
    const std::string svgContents((std::istreambuf_iterator<char>(svgInput)),
                                  std::istreambuf_iterator<char>());

    EXPECT_NE(filteredContents.find("inferred_K_activity_value"), std::string::npos);
    EXPECT_NE(filteredContents.find("reference_curve_inferred_from_activity_value"),
              std::string::npos);
    EXPECT_NE(svgContents.find("Reference Hill Curves Inferred from Activity_Value"),
              std::string::npos);
    EXPECT_NE(svgContents.find("AID 743069"), std::string::npos);
}

TEST(BioactivityStrategiesTest, HillAnalysisMatchesCid4RealData)
{
    const auto csvPath = repositoryRoot() / "data" / "pubchem_cid_4_bioactivity.csv";

    const auto result = pubchem::buildHillDoseResponseAnalysis(csvPath);

    EXPECT_EQ(result.rowCounts.totalRows, 406U);
    EXPECT_EQ(result.rowCounts.rowsWithNumericActivityValue, 2U);
    EXPECT_EQ(result.rowCounts.rowsWithPositiveActivityValue, 2U);
    EXPECT_EQ(result.rowCounts.rowsFlaggedHasDoseResponseCurve, 203U);
    EXPECT_EQ(result.rowCounts.retainedRows, 2U);
    EXPECT_EQ(result.rowCounts.retainedRowsFlaggedHasDoseResponseCurve, 1U);
    EXPECT_EQ(result.rowCounts.retainedUniqueBioassays, 2U);
    EXPECT_NEAR(result.statistics.activityValueAsInferredK.min, 21.8724, 1.0e-12);
    EXPECT_NEAR(result.statistics.activityValueAsInferredK.median, 410.9362, 1.0e-10);
    EXPECT_NEAR(result.statistics.activityValueAsInferredK.max, 800.0, 1.0e-12);
    EXPECT_NEAR(result.statistics.midpointFirstDerivative.min, 0.0003125, 1.0e-12);
    EXPECT_NEAR(result.statistics.midpointFirstDerivative.median, 0.005871214978694611, 1.0e-15);
    EXPECT_NEAR(result.statistics.midpointFirstDerivative.max, 0.011429929957389222, 1.0e-15);
    EXPECT_FALSE(result.analysis.linearConcentrationInflection.has_value());
    ASSERT_EQ(result.analysis.representativeRows.size(), 2U);
    EXPECT_EQ(result.analysis.representativeRows.front().bioAssayAid, 743069LL);
    EXPECT_EQ(result.analysis.representativeRows.back().bioAssayAid, 158688LL);
}
