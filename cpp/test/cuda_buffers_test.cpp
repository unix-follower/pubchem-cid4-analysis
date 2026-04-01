#include <gtest/gtest.h>

#include "cid4_cuda_buffers.hpp"

#include <filesystem>
#include <fstream>
#include <string>

namespace {
std::filesystem::path writeTempFile(const std::string& fileName, const std::string& contents)
{
    const auto directory = std::filesystem::temp_directory_path() / "pubchem-cid4-cuda-tests";
    std::filesystem::create_directories(directory);
    const auto filePath = directory / fileName;
    std::ofstream output(filePath);
    output << contents;
    return filePath;
}

std::string sampleConformerJson(float x0, float y0, float z0)
{
    return "{\n"
           "  \"PC_Compounds\": [\n"
           "    {\n"
           "      \"id\": { \"id\": { \"cid\": 4 } },\n"
           "      \"atoms\": {\n"
           "        \"aid\": [1, 2],\n"
           "        \"element\": [6, 8]\n"
           "      },\n"
           "      \"bonds\": {\n"
           "        \"aid1\": [1],\n"
           "        \"aid2\": [2],\n"
           "        \"order\": [1]\n"
           "      },\n"
           "      \"coords\": [\n"
           "        {\n"
           "          \"aid\": [1, 2],\n"
           "          \"conformers\": [\n"
           "            {\n"
           "              \"x\": [" +
           std::to_string(x0) +
           ", 1.0],\n"
           "              \"y\": [" +
           std::to_string(y0) +
           ", 0.0],\n"
           "              \"z\": [" +
           std::to_string(z0) +
           ", 0.0]\n"
           "            }\n"
           "          ]\n"
           "        }\n"
           "      ]\n"
           "    }\n"
           "  ]\n"
           "}\n";
}
} // namespace

TEST(CudaBuffersTest, LoadsBatchedCoordinatesAcrossConformers)
{
    const auto first = writeTempFile("conformer-a.json", sampleConformerJson(0.0F, 0.0F, 0.0F));
    const auto second = writeTempFile("conformer-b.json", sampleConformerJson(2.0F, 0.0F, 0.0F));

    const auto batch = pubchem::loadCudaCoordinateBatch({first, second});

    EXPECT_EQ(batch.conformerCount, 2U);
    EXPECT_EQ(batch.atomCount, 2U);
    ASSERT_EQ(batch.positions.size(), 12U);
    EXPECT_FLOAT_EQ(batch.positions[0], 0.0F);
    EXPECT_FLOAT_EQ(batch.positions[6], 2.0F);
}

TEST(CudaBuffersTest, ComputesReferenceDistanceMatrices)
{
    const auto first =
        writeTempFile("conformer-dist-a.json", sampleConformerJson(0.0F, 0.0F, 0.0F));
    const auto second =
        writeTempFile("conformer-dist-b.json", sampleConformerJson(3.0F, 0.0F, 0.0F));

    const auto batch = pubchem::loadCudaCoordinateBatch({first, second});
    const auto distances = pubchem::computeDistanceMatricesReference(batch);

    EXPECT_EQ(distances.conformerCount, 2U);
    EXPECT_EQ(distances.atomCount, 2U);
    EXPECT_FLOAT_EQ(pubchem::distanceMatrixValue(distances, 0, 0, 1), 1.0F);
    EXPECT_FLOAT_EQ(pubchem::distanceMatrixValue(distances, 1, 0, 1), 2.0F);
    EXPECT_FLOAT_EQ(pubchem::distanceMatrixValue(distances, 1, 1, 0), 2.0F);
}
