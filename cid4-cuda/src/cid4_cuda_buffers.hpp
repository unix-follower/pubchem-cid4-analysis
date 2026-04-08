#pragma once

#include <cstddef>
#include <filesystem>
#include <vector>

namespace pubchem {
struct CudaCoordinateBatch {
    std::vector<std::filesystem::path> sourceFiles;
    std::vector<int> atomIds;
    std::size_t atomCount;
    std::size_t conformerCount;
    bool hasZCoordinates;
    std::vector<float> positions;
};

struct DistanceMatrixBatch {
    std::size_t atomCount;
    std::size_t conformerCount;
    std::vector<float> distances;
};

std::vector<std::filesystem::path> defaultCudaJsonPaths(const std::filesystem::path& dataDir,
                                                        std::size_t conformerCount = 6);

CudaCoordinateBatch loadCudaCoordinateBatch(const std::vector<std::filesystem::path>& jsonPaths);

DistanceMatrixBatch computeDistanceMatricesReference(const CudaCoordinateBatch& batch);

float distanceMatrixValue(const DistanceMatrixBatch& batch,
                          std::size_t conformerIndex,
                          std::size_t rowIndex,
                          std::size_t columnIndex);
} // namespace pubchem
