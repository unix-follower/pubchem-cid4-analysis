#include "cid4_cuda_runtime.hpp"

#include <cuda_runtime.h>

#include <stdexcept>
#include <string>

namespace pubchem {
namespace {
__global__ void distanceMatrixKernel(const float* positions,
                                     float* distances,
                                     const int atomCount,
                                     const int conformerCount)
{
    const int flatIndex = static_cast<int>(blockIdx.x * blockDim.x + threadIdx.x);
    const int matrixSize = atomCount * atomCount;
    const int totalEntries = conformerCount * matrixSize;
    if (flatIndex >= totalEntries) {
        return;
    }

    const int conformerIndex = flatIndex / matrixSize;
    const int intraMatrixIndex = flatIndex % matrixSize;
    const int rowIndex = intraMatrixIndex / atomCount;
    const int columnIndex = intraMatrixIndex % atomCount;

    const int conformerOffset = conformerIndex * atomCount * 3;
    const int rowOffset = conformerOffset + rowIndex * 3;
    const int columnOffset = conformerOffset + columnIndex * 3;

    const float dx = positions[rowOffset] - positions[columnOffset];
    const float dy = positions[rowOffset + 1] - positions[columnOffset + 1];
    const float dz = positions[rowOffset + 2] - positions[columnOffset + 2];
    distances[flatIndex] = sqrtf(dx * dx + dy * dy + dz * dz);
}

void throwOnCudaError(const cudaError_t status, const char* operation)
{
    if (status != cudaSuccess) {
        throw std::runtime_error(std::string(operation) + " failed: " + cudaGetErrorString(status));
    }
}
}

DistanceMatrixBatch computeDistanceMatricesCuda(const CudaCoordinateBatch& batch)
{
    if (batch.atomCount == 0 || batch.conformerCount == 0) {
        throw std::invalid_argument("CUDA batch must contain at least one conformer and one atom");
    }

    const std::size_t positionBytes = batch.positions.size() * sizeof(float);
    const std::size_t distanceCount = batch.conformerCount * batch.atomCount * batch.atomCount;
    const std::size_t distanceBytes = distanceCount * sizeof(float);

    float* devicePositions = nullptr;
    float* deviceDistances = nullptr;

    throwOnCudaError(cudaMalloc(&devicePositions, positionBytes), "cudaMalloc(devicePositions)");

    try {
        throwOnCudaError(cudaMalloc(&deviceDistances, distanceBytes), "cudaMalloc(deviceDistances)");
        throwOnCudaError(cudaMemcpy(devicePositions,
                                    batch.positions.data(),
                                    positionBytes,
                                    cudaMemcpyHostToDevice),
                         "cudaMemcpy(host->device positions)");

        const int totalEntries = static_cast<int>(distanceCount);
        constexpr int threadsPerBlock = 256;
        const int blockCount = (totalEntries + threadsPerBlock - 1) / threadsPerBlock;
        distanceMatrixKernel<<<blockCount, threadsPerBlock>>>(devicePositions,
                                                              deviceDistances,
                                                              static_cast<int>(batch.atomCount),
                                                              static_cast<int>(batch.conformerCount));
        throwOnCudaError(cudaGetLastError(), "distanceMatrixKernel launch");
        throwOnCudaError(cudaDeviceSynchronize(), "cudaDeviceSynchronize");

        DistanceMatrixBatch result{
            .atomCount = batch.atomCount,
            .conformerCount = batch.conformerCount,
            .distances = std::vector<float>(distanceCount, 0.0F),
        };
        throwOnCudaError(cudaMemcpy(result.distances.data(),
                                    deviceDistances,
                                    distanceBytes,
                                    cudaMemcpyDeviceToHost),
                         "cudaMemcpy(device->host distances)");

        cudaFree(deviceDistances);
        cudaFree(devicePositions);
        return result;
    }
    catch (...) {
        if (deviceDistances != nullptr) {
            cudaFree(deviceDistances);
        }
        if (devicePositions != nullptr) {
            cudaFree(devicePositions);
        }
        throw;
    }
}
}
