#pragma once

#include "cid4_cuda_buffers.hpp"

namespace pubchem {
DistanceMatrixBatch computeDistanceMatricesCuda(const CudaCoordinateBatch& batch);
}
