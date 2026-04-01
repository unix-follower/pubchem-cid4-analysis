#include "cid4_cuda_buffers.hpp"

#if PUBCHEM_CUDA_RUNTIME_AVAILABLE
#include "cid4_cuda_runtime.hpp"
#endif

#include <algorithm>
#include <cmath>
#include <cstdlib>
#include <filesystem>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>
#include <string_view>
#include <vector>

namespace {
struct CudaAppOptions {
    std::vector<std::filesystem::path> jsonFiles;
    bool skipRuntimeProbe = false;
};

struct DistanceSummary {
    float minimum = 0.0F;
    float maximum = 0.0F;
    float mean = 0.0F;
};

std::filesystem::path defaultDataDir()
{
    return std::filesystem::path(PUBCHEM_DEFAULT_DATA_DIR);
}

std::filesystem::path resolveDataDir()
{
    if (const char* value = std::getenv("DATA_DIR"); value != nullptr && *value != '\0') {
        return std::filesystem::path(value);
    }

    return defaultDataDir();
}

void printUsage(std::ostream& output)
{
    output << "Usage: cuda_app [--json <file>]... [--skip-runtime-probe]\n";
}

CudaAppOptions parseArguments(int argc, char* argv[])
{
    CudaAppOptions options;

    for (int index = 1; index < argc; ++index) {
        const std::string argument = argv[index];
        if (argument == "--help") {
            printUsage(std::cout);
            std::exit(0);
        }

        auto readValue = [&](const std::string_view flagName) -> std::string {
            if (index + 1 >= argc) {
                throw std::invalid_argument("Missing value for " + std::string(flagName));
            }

            ++index;
            return argv[index];
        };

        if (argument == "--json") {
            options.jsonFiles.push_back(readValue("--json"));
            continue;
        }

        if (argument == "--skip-runtime-probe") {
            options.skipRuntimeProbe = true;
            continue;
        }

        throw std::invalid_argument("Unknown argument: " + argument);
    }

    return options;
}

DistanceSummary summarizeDistances(const pubchem::DistanceMatrixBatch& matrix)
{
    DistanceSummary summary{
        .minimum = std::numeric_limits<float>::max(),
        .maximum = 0.0F,
        .mean = 0.0F,
    };

    double sum = 0.0;
    std::size_t count = 0;
    for (std::size_t conformerIndex = 0; conformerIndex < matrix.conformerCount; ++conformerIndex) {
        for (std::size_t rowIndex = 0; rowIndex < matrix.atomCount; ++rowIndex) {
            for (std::size_t columnIndex = rowIndex + 1; columnIndex < matrix.atomCount;
                 ++columnIndex) {
                const float value =
                    pubchem::distanceMatrixValue(matrix, conformerIndex, rowIndex, columnIndex);
                summary.minimum = std::min(summary.minimum, value);
                summary.maximum = std::max(summary.maximum, value);
                sum += value;
                ++count;
            }
        }
    }

    if (count == 0) {
        summary.minimum = 0.0F;
        return summary;
    }

    summary.mean = static_cast<float>(sum / static_cast<double>(count));
    return summary;
}

float maxAbsDifference(const pubchem::DistanceMatrixBatch& left,
                       const pubchem::DistanceMatrixBatch& right)
{
    if (left.distances.size() != right.distances.size()) {
        throw std::runtime_error("CUDA validation requires matching distance-matrix sizes");
    }

    float maxDifference = 0.0F;
    for (std::size_t index = 0; index < left.distances.size(); ++index) {
        maxDifference =
            std::max(maxDifference, std::fabs(left.distances[index] - right.distances[index]));
    }

    return maxDifference;
}

void printBatchSummary(const pubchem::CudaCoordinateBatch& batch)
{
    std::cout << "CUDA coordinate batch loaded. Conformers: " << batch.conformerCount
              << ", Atoms per conformer: " << batch.atomCount << "\n";
    std::cout << "Coordinate mode: " << (batch.hasZCoordinates ? "3D" : "2D") << "\n";
    for (const auto& path : batch.sourceFiles) {
        std::cout << "  - " << path.filename().string() << "\n";
    }
}

void printDistanceSummary(const std::string_view label, const DistanceSummary& summary)
{
    std::cout << label << " min distance: " << summary.minimum << "\n";
    std::cout << label << " max distance: " << summary.maximum << "\n";
    std::cout << label << " mean distance: " << summary.mean << "\n";
}
} // namespace

int main(int argc, char* argv[])
{
    try {
        CudaAppOptions options = parseArguments(argc, argv);
        const std::filesystem::path dataDir = resolveDataDir();
        if (options.jsonFiles.empty()) {
            options.jsonFiles = pubchem::defaultCudaJsonPaths(dataDir);
        }
        else {
            for (std::filesystem::path& jsonFile : options.jsonFiles) {
                jsonFile = dataDir / jsonFile;
            }
        }

        const pubchem::CudaCoordinateBatch batch =
            pubchem::loadCudaCoordinateBatch(options.jsonFiles);
        printBatchSummary(batch);

        const pubchem::DistanceMatrixBatch reference =
            pubchem::computeDistanceMatricesReference(batch);
        printDistanceSummary("CPU reference", summarizeDistances(reference));

#if PUBCHEM_CUDA_RUNTIME_AVAILABLE
        if (options.skipRuntimeProbe) {
            std::cout << "Skipping CUDA runtime execution by request. CPU reference path compiled "
                         "successfully.\n";
            return 0;
        }

        const pubchem::DistanceMatrixBatch gpuResult = pubchem::computeDistanceMatricesCuda(batch);
        printDistanceSummary("CUDA", summarizeDistances(gpuResult));
        std::cout << "CUDA validation max abs diff: " << maxAbsDifference(reference, gpuResult)
                  << "\n";
        return 0;
#else
        std::cout << "CUDA toolkit was not detected at configure time. "
                     "This build provides the batch-loading and CPU reference path only.\n";
        std::cout << "Install the NVIDIA CUDA toolkit on a supported machine and reconfigure CMake "
                     "to enable runtime execution.\n";
        return 0;
#endif
    }
    catch (const std::exception& error) {
        std::cerr << "cuda_app error: " << error.what() << "\n";
        return 1;
    }
}
