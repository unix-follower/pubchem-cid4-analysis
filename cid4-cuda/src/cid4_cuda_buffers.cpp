#include "cid4_cuda_buffers.hpp"

#include "cid4_scene.hpp"

#include <cmath>
#include <sstream>
#include <stdexcept>
#include <string>

namespace pubchem {
namespace {
std::string joinPaths(const std::vector<std::filesystem::path>& paths)
{
    std::ostringstream stream;
    for (std::size_t index = 0; index < paths.size(); ++index) {
        if (index > 0) {
            stream << ", ";
        }
        stream << paths[index].filename().string();
    }

    return stream.str();
}
} // namespace

std::vector<std::filesystem::path> defaultCudaJsonPaths(const std::filesystem::path& dataDir,
                                                        const std::size_t conformerCount)
{
    std::vector<std::filesystem::path> paths;
    paths.reserve(conformerCount);
    for (std::size_t index = 1; index <= conformerCount; ++index) {
        paths.push_back(dataDir /
                        ("Conformer3D_COMPOUND_CID_4(" + std::to_string(index) + ").json"));
    }

    return paths;
}

CudaCoordinateBatch loadCudaCoordinateBatch(const std::vector<std::filesystem::path>& jsonPaths)
{
    if (jsonPaths.empty()) {
        throw std::invalid_argument("At least one JSON file is required for CUDA batch loading");
    }

    CudaCoordinateBatch batch{};
    batch.atomCount = 0;
    batch.conformerCount = 0;
    batch.hasZCoordinates = false;

    for (const std::filesystem::path& jsonPath : jsonPaths) {
        const SceneData scene = loadSceneData(jsonPath);
        if (batch.conformerCount == 0) {
            batch.atomCount = scene.atoms.size();
            batch.hasZCoordinates = scene.hasZCoordinates;
            batch.atomIds.reserve(scene.atoms.size());
            for (const SceneAtom& atom : scene.atoms) {
                batch.atomIds.push_back(atom.atomId);
            }
        }
        else {
            if (scene.atoms.size() != batch.atomCount) {
                throw std::runtime_error("CUDA batch atom-count mismatch across: " +
                                         joinPaths(jsonPaths));
            }

            for (std::size_t atomIndex = 0; atomIndex < scene.atoms.size(); ++atomIndex) {
                if (scene.atoms[atomIndex].atomId != batch.atomIds[atomIndex]) {
                    throw std::runtime_error("CUDA batch atom ordering mismatch across: " +
                                             joinPaths(jsonPaths));
                }
            }

            batch.hasZCoordinates = batch.hasZCoordinates || scene.hasZCoordinates;
        }

        batch.sourceFiles.push_back(jsonPath);
        batch.positions.reserve(batch.positions.size() + scene.atoms.size() * 3);
        for (const SceneAtom& atom : scene.atoms) {
            batch.positions.push_back(atom.position[0]);
            batch.positions.push_back(atom.position[1]);
            batch.positions.push_back(atom.position[2]);
        }

        ++batch.conformerCount;
    }

    return batch;
}

DistanceMatrixBatch computeDistanceMatricesReference(const CudaCoordinateBatch& batch)
{
    DistanceMatrixBatch result{
        .atomCount = batch.atomCount,
        .conformerCount = batch.conformerCount,
        .distances =
            std::vector<float>(batch.conformerCount * batch.atomCount * batch.atomCount, 0.0F),
    };

    for (std::size_t conformerIndex = 0; conformerIndex < batch.conformerCount; ++conformerIndex) {
        const std::size_t conformerOffset = conformerIndex * batch.atomCount * 3;
        const std::size_t distanceOffset = conformerIndex * batch.atomCount * batch.atomCount;

        for (std::size_t rowIndex = 0; rowIndex < batch.atomCount; ++rowIndex) {
            const std::size_t rowCoordinateOffset = conformerOffset + rowIndex * 3;
            for (std::size_t columnIndex = 0; columnIndex < batch.atomCount; ++columnIndex) {
                const std::size_t columnCoordinateOffset = conformerOffset + columnIndex * 3;
                const float dx =
                    batch.positions[rowCoordinateOffset] - batch.positions[columnCoordinateOffset];
                const float dy = batch.positions[rowCoordinateOffset + 1] -
                                 batch.positions[columnCoordinateOffset + 1];
                const float dz = batch.positions[rowCoordinateOffset + 2] -
                                 batch.positions[columnCoordinateOffset + 2];
                result.distances[distanceOffset + rowIndex * batch.atomCount + columnIndex] =
                    std::sqrt(dx * dx + dy * dy + dz * dz);
            }
        }
    }

    return result;
}

float distanceMatrixValue(const DistanceMatrixBatch& batch,
                          const std::size_t conformerIndex,
                          const std::size_t rowIndex,
                          const std::size_t columnIndex)
{
    const std::size_t matrixSize = batch.atomCount * batch.atomCount;
    const std::size_t offset =
        conformerIndex * matrixSize + rowIndex * batch.atomCount + columnIndex;
    if (offset >= batch.distances.size()) {
        throw std::out_of_range("Distance matrix index out of range");
    }

    return batch.distances[offset];
}
} // namespace pubchem
