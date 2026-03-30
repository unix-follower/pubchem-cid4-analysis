#include "analysis.hpp"

#include <algorithm>
#include <armadillo>
#include <boost/graph/adjacency_list.hpp>
#include <boost/graph/connected_components.hpp>
#include <boost/graph/graph_traits.hpp>
#include <boost/numeric/ublas/matrix.hpp>
#include <boost/numeric/ublas/matrix_proxy.hpp>
#include <cmath>
#include <fstream>
#include <limits>
#include <map>
#include <numeric>
#include <sstream>
#include <stdexcept>

#include <nlohmann/json.hpp>

namespace pubchem {
namespace {
using Json = nlohmann::json;

class AdjacencyInputError : public std::invalid_argument {
  public:
    using std::invalid_argument::invalid_argument;
};

class LaplacianAnalysisError : public std::runtime_error {
  public:
    using std::runtime_error::runtime_error;
};

class DistanceAnalysisError : public std::runtime_error {
  public:
    using std::runtime_error::runtime_error;
};

struct EigenComponents {
    std::vector<double> eigenvalues;
    std::vector<std::vector<double>> eigenvectors;
};

using UblasMatrix = boost::numeric::ublas::matrix<double>;

std::vector<int> jsonToIntVector(const Json& value, std::string_view fieldName);

std::vector<std::vector<double>> identityMatrix(const std::size_t size)
{
    std::vector<std::vector<double>> identity(size, std::vector<double>(size, 0.0));
    for (std::size_t index = 0; index < size; ++index) {
        identity[index][index] = 1.0;
    }

    return identity;
}

EigenComponents sortEigenComponents(std::vector<double> eigenvalues,
                                    std::vector<std::vector<double>> eigenvectors)
{
    std::vector<std::size_t> order(eigenvalues.size());
    std::iota(order.begin(), order.end(), 0);
    std::stable_sort(
        order.begin(), order.end(), [&](const std::size_t left, const std::size_t right) {
            return eigenvalues[left] < eigenvalues[right];
        });

    std::vector<double> sortedEigenvalues;
    sortedEigenvalues.reserve(eigenvalues.size());

    std::vector<std::vector<double>> sortedEigenvectors(
        eigenvectors.size(), std::vector<double>(eigenvectors.size(), 0.0));

    for (std::size_t columnIndex = 0; columnIndex < order.size(); ++columnIndex) {
        const std::size_t sourceColumn = order[columnIndex];
        sortedEigenvalues.push_back(eigenvalues[sourceColumn]);
        for (std::size_t rowIndex = 0; rowIndex < eigenvectors.size(); ++rowIndex) {
            sortedEigenvectors[rowIndex][columnIndex] = eigenvectors[rowIndex][sourceColumn];
        }
    }

    return EigenComponents{
        .eigenvalues = std::move(sortedEigenvalues),
        .eigenvectors = std::move(sortedEigenvectors),
    };
}

EigendecompositionResult makeEigendecompositionResult(const AdjacencyMatrix& matrix,
                                                      const std::string_view method,
                                                      EigenComponents components)
{
    return EigendecompositionResult{
        .sourceFile = matrix.sourceFile,
        .method = std::string(method),
        .atomIds = matrix.atomIds,
        .eigenvalues = std::move(components.eigenvalues),
        .eigenvectors = std::move(components.eigenvectors),
    };
}

UblasMatrix toUblasMatrix(const AdjacencyMatrix& matrix)
{
    UblasMatrix values(matrix.values.size(), matrix.values.size());
    for (std::size_t rowIndex = 0; rowIndex < matrix.values.size(); ++rowIndex) {
        for (std::size_t columnIndex = 0; columnIndex < matrix.values[rowIndex].size();
             ++columnIndex) {
            values(rowIndex, columnIndex) =
                static_cast<double>(matrix.values[rowIndex][columnIndex]);
        }
    }

    return values;
}

arma::mat toArmadilloMatrix(const std::vector<std::vector<double>>& matrixValues)
{
    arma::mat values(matrixValues.size(), matrixValues.size(), arma::fill::zeros);
    for (std::size_t rowIndex = 0; rowIndex < matrixValues.size(); ++rowIndex) {
        for (std::size_t columnIndex = 0; columnIndex < matrixValues[rowIndex].size();
             ++columnIndex) {
            values(rowIndex, columnIndex) = matrixValues[rowIndex][columnIndex];
        }
    }

    return values;
}

std::vector<std::vector<double>> toVectorMatrix(const arma::mat& matrix)
{
    std::vector<std::vector<double>> values(matrix.n_rows, std::vector<double>(matrix.n_cols, 0.0));
    for (std::size_t rowIndex = 0; rowIndex < matrix.n_rows; ++rowIndex) {
        for (std::size_t columnIndex = 0; columnIndex < matrix.n_cols; ++columnIndex) {
            values[rowIndex][columnIndex] = matrix(rowIndex, columnIndex);
        }
    }

    return values;
}

std::vector<std::vector<double>> toDoubleMatrix(const AdjacencyMatrix& matrix)
{
    std::vector<std::vector<double>> values(matrix.values.size(),
                                            std::vector<double>(matrix.values.size(), 0.0));
    for (std::size_t rowIndex = 0; rowIndex < matrix.values.size(); ++rowIndex) {
        for (std::size_t columnIndex = 0; columnIndex < matrix.values[rowIndex].size();
             ++columnIndex) {
            values[rowIndex][columnIndex] =
                static_cast<double>(matrix.values[rowIndex][columnIndex]);
        }
    }

    return values;
}

std::vector<double> computeDegreeVector(const std::vector<std::vector<double>>& adjacencyValues)
{
    std::vector<double> degreeVector;
    degreeVector.reserve(adjacencyValues.size());
    for (const auto& row : adjacencyValues) {
        degreeVector.push_back(std::accumulate(row.begin(), row.end(), 0.0));
    }

    return degreeVector;
}

std::vector<std::vector<double>> buildLaplacianMatrixValues(const AdjacencyMatrix& matrix)
{
    const auto adjacencyValues = toDoubleMatrix(matrix);
    const auto degreeVector = computeDegreeVector(adjacencyValues);
    std::vector<std::vector<double>> laplacianValues(
        adjacencyValues.size(), std::vector<double>(adjacencyValues.size(), 0.0));

    for (std::size_t rowIndex = 0; rowIndex < adjacencyValues.size(); ++rowIndex) {
        for (std::size_t columnIndex = 0; columnIndex < adjacencyValues[rowIndex].size();
             ++columnIndex) {
            const double degreeContribution =
                rowIndex == columnIndex ? degreeVector[rowIndex] : 0.0;
            laplacianValues[rowIndex][columnIndex] =
                degreeContribution - adjacencyValues[rowIndex][columnIndex];
        }
    }

    return laplacianValues;
}

std::vector<double> jsonToDoubleVector(const Json& value, const std::string_view fieldName)
{
    if (!value.is_array()) {
        throw DistanceAnalysisError(std::string(fieldName) + " must be an array");
    }

    return value.get<std::vector<double>>();
}

std::vector<std::vector<double>>
buildDistanceMatrixValues(const std::vector<std::vector<double>>& coordinates)
{
    std::vector<std::vector<double>> matrix(coordinates.size(),
                                            std::vector<double>(coordinates.size(), 0.0));

    for (std::size_t rowIndex = 0; rowIndex < coordinates.size(); ++rowIndex) {
        for (std::size_t columnIndex = rowIndex + 1; columnIndex < coordinates.size();
             ++columnIndex) {
            const double xDelta = coordinates[rowIndex][0] - coordinates[columnIndex][0];
            const double yDelta = coordinates[rowIndex][1] - coordinates[columnIndex][1];
            const double zDelta = coordinates[rowIndex][2] - coordinates[columnIndex][2];
            const double distance = std::sqrt(xDelta * xDelta + yDelta * yDelta + zDelta * zDelta);
            matrix[rowIndex][columnIndex] = distance;
            matrix[columnIndex][rowIndex] = distance;
        }
    }

    return matrix;
}

void validateCoordinates(const DistanceMatrixInput& input,
                         const std::vector<std::vector<double>>& coordinates,
                         const std::string_view sourceName)
{
    if (input.atomIds.empty()) {
        throw DistanceAnalysisError("Distance analysis requires at least one atom id");
    }

    if (coordinates.size() != input.atomIds.size()) {
        throw DistanceAnalysisError("Atom ids count does not match coordinate count for " +
                                    std::string(sourceName));
    }

    for (const auto& coordinate : coordinates) {
        if (coordinate.size() != 3U) {
            throw DistanceAnalysisError("Distance analysis expects 3D coordinates for " +
                                        std::string(sourceName));
        }
    }
}

DistanceMatrixResult makeDistanceMatrixResult(const DistanceMatrixInput& input,
                                              const std::string_view method,
                                              const std::string_view sourceFile,
                                              std::vector<std::vector<double>> coordinates)
{
    validateCoordinates(input, coordinates, sourceFile);

    return DistanceMatrixResult{
        .sourceFile = std::string(sourceFile),
        .method = std::string(method),
        .atomIds = input.atomIds,
        .xyzCoordinates = coordinates,
        .distanceMatrix = buildDistanceMatrixValues(coordinates),
        .metadata =
            DistanceMatrixMetadata{
                .atomCount = input.atomIds.size(),
                .coordinateDimension = 3,
                .units = "angstrom",
            },
    };
}

std::vector<std::vector<double>> loadSdfCoordinates(const std::filesystem::path& sdfPath)
{
    std::ifstream input(sdfPath);
    if (!input) {
        throw DistanceAnalysisError("Could not open distance SDF input file: " + sdfPath.string());
    }

    std::string line;
    for (int index = 0; index < 3; ++index) {
        if (!std::getline(input, line)) {
            throw DistanceAnalysisError("SDF file ended before the counts line: " +
                                        sdfPath.string());
        }
    }

    if (!std::getline(input, line)) {
        throw DistanceAnalysisError("SDF file ended before the counts line: " + sdfPath.string());
    }

    std::istringstream countsStream(line);
    int atomCount = 0;
    int bondCount = 0;
    if (!(countsStream >> atomCount >> bondCount) || atomCount <= 0) {
        throw DistanceAnalysisError("Could not parse SDF counts line: " + sdfPath.string());
    }

    std::vector<std::vector<double>> coordinates;
    coordinates.reserve(static_cast<std::size_t>(atomCount));
    for (int atomIndex = 0; atomIndex < atomCount; ++atomIndex) {
        if (!std::getline(input, line)) {
            throw DistanceAnalysisError("SDF file ended inside the atom block: " +
                                        sdfPath.string());
        }

        std::istringstream atomStream(line);
        double x = 0.0;
        double y = 0.0;
        double z = 0.0;
        std::string symbol;
        if (!(atomStream >> x >> y >> z >> symbol)) {
            throw DistanceAnalysisError("Could not parse SDF atom coordinates: " +
                                        sdfPath.string());
        }

        coordinates.push_back({x, y, z});
    }

    return coordinates;
}

NullSpaceBasis buildNullSpaceBasis(const EigenComponents& components, const double zeroTolerance)
{
    std::vector<std::size_t> zeroIndices;
    for (std::size_t index = 0; index < components.eigenvalues.size(); ++index) {
        if (std::abs(components.eigenvalues[index]) < zeroTolerance) {
            zeroIndices.push_back(index);
        }
    }

    std::vector<std::vector<double>> nullSpaceEigenvectors(
        components.eigenvectors.size(), std::vector<double>(zeroIndices.size(), 0.0));
    for (std::size_t columnIndex = 0; columnIndex < zeroIndices.size(); ++columnIndex) {
        const std::size_t sourceColumn = zeroIndices[columnIndex];
        for (std::size_t rowIndex = 0; rowIndex < components.eigenvectors.size(); ++rowIndex) {
            nullSpaceEigenvectors[rowIndex][columnIndex] =
                components.eigenvectors[rowIndex][sourceColumn];
        }
    }

    const auto smallestNonZero =
        std::find_if(components.eigenvalues.begin(),
                     components.eigenvalues.end(),
                     [&](const double value) { return value > zeroTolerance; });

    return NullSpaceBasis{
        .eigenvalues =
            [&] {
                std::vector<double> values;
                values.reserve(zeroIndices.size());
                for (const auto index : zeroIndices) {
                    values.push_back(components.eigenvalues[index]);
                }
                return values;
            }(),
        .eigenvectors = std::move(nullSpaceEigenvectors),
        .tolerance = zeroTolerance,
        .numZeroEigenvalues = zeroIndices.size(),
        .smallestNonZeroEigenvalue =
            smallestNonZero == components.eigenvalues.end() ? 0.0 : *smallestNonZero,
    };
}

ConnectedComponentsResult buildConnectedComponentsResult(const AdjacencyMatrix& matrix)
{
    using Graph = boost::adjacency_list<boost::vecS,
                                        boost::vecS,
                                        boost::undirectedS,
                                        boost::no_property,
                                        boost::property<boost::edge_weight_t, int>>;

    Graph graph(matrix.values.size());
    for (std::size_t rowIndex = 0; rowIndex < matrix.values.size(); ++rowIndex) {
        for (std::size_t columnIndex = rowIndex + 1; columnIndex < matrix.values[rowIndex].size();
             ++columnIndex) {
            const int weight = matrix.values[rowIndex][columnIndex];
            if (weight > 0) {
                boost::add_edge(static_cast<Graph::vertices_size_type>(rowIndex),
                                static_cast<Graph::vertices_size_type>(columnIndex),
                                weight,
                                graph);
            }
        }
    }

    std::vector<int> labels(matrix.values.size(), 0);
    const auto numComponents =
        static_cast<std::size_t>(boost::connected_components(graph, labels.data()));
    std::vector<std::vector<int>> componentAtomIds(numComponents);
    for (std::size_t index = 0; index < labels.size(); ++index) {
        componentAtomIds[static_cast<std::size_t>(labels[index])].push_back(matrix.atomIds[index]);
    }

    for (auto& component : componentAtomIds) {
        std::sort(component.begin(), component.end());
    }

    return ConnectedComponentsResult{
        .labels = std::move(labels),
        .numComponents = numComponents,
        .componentAtomIds = std::move(componentAtomIds),
        .verificationBoostGraphCount = numComponents,
    };
}

std::size_t countBonds(const AdjacencyMatrix& matrix)
{
    std::size_t bondCount = 0;
    for (std::size_t rowIndex = 0; rowIndex < matrix.values.size(); ++rowIndex) {
        for (std::size_t columnIndex = rowIndex + 1; columnIndex < matrix.values[rowIndex].size();
             ++columnIndex) {
            if (matrix.values[rowIndex][columnIndex] > 0) {
                ++bondCount;
            }
        }
    }

    return bondCount;
}

LaplacianAnalysisResult
makeLaplacianAnalysisResult(const AdjacencyMatrix& matrix,
                            const std::string_view method,
                            const std::vector<double>& degreeVector,
                            std::vector<std::vector<double>> laplacianMatrix,
                            EigenComponents components,
                            const double zeroTolerance)
{
    const NullSpaceBasis nullSpace = buildNullSpaceBasis(components, zeroTolerance);
    const ConnectedComponentsResult connectedComponents = buildConnectedComponentsResult(matrix);
    if (nullSpace.numZeroEigenvalues != connectedComponents.numComponents) {
        throw LaplacianAnalysisError(
            "Null-space dimension does not match Boost.Graph connected-components count");
    }

    const std::size_t laplacianRank =
        std::count_if(components.eigenvalues.begin(),
                      components.eigenvalues.end(),
                      [&](const double value) { return std::abs(value) >= zeroTolerance; });

    return LaplacianAnalysisResult{
        .sourceFile = matrix.sourceFile,
        .method = std::string(method),
        .atomIds = matrix.atomIds,
        .degreeVector = degreeVector,
        .laplacianMatrix = std::move(laplacianMatrix),
        .laplacianEigenvalues = std::move(components.eigenvalues),
        .laplacianEigenvectors = std::move(components.eigenvectors),
        .nullSpace = nullSpace,
        .connectedComponents = connectedComponents,
        .metadata =
            LaplacianMetadata{
                .atomCount = matrix.atomIds.size(),
                .bondCount = countBonds(matrix),
                .laplacianRank = laplacianRank,
                .graphIsConnected = connectedComponents.numComponents == 1,
            },
    };
}

EigenComponents jacobiEigenDecomposition(UblasMatrix matrix)
{
    const std::size_t size = matrix.size1();
    auto eigenvectors = identityMatrix(size);
    const double tolerance = 1.0e-12;
    const std::size_t maxIterations = size == 0 ? 0 : size * size * 100;

    for (std::size_t iteration = 0; iteration < maxIterations; ++iteration) {
        std::size_t pivotRow = 0;
        std::size_t pivotColumn = 0;
        double maxOffDiagonal = 0.0;

        for (std::size_t rowIndex = 0; rowIndex < size; ++rowIndex) {
            for (std::size_t columnIndex = rowIndex + 1; columnIndex < size; ++columnIndex) {
                const double value = std::abs(matrix(rowIndex, columnIndex));
                if (value > maxOffDiagonal) {
                    maxOffDiagonal = value;
                    pivotRow = rowIndex;
                    pivotColumn = columnIndex;
                }
            }
        }

        if (maxOffDiagonal <= tolerance) {
            break;
        }

        const double app = matrix(pivotRow, pivotRow);
        const double aqq = matrix(pivotColumn, pivotColumn);
        const double apq = matrix(pivotRow, pivotColumn);
        const double phi = 0.5 * std::atan2(2.0 * apq, aqq - app);
        const double cosine = std::cos(phi);
        const double sine = std::sin(phi);

        for (std::size_t index = 0; index < size; ++index) {
            if (index == pivotRow || index == pivotColumn) {
                continue;
            }

            const double aip = matrix(index, pivotRow);
            const double aiq = matrix(index, pivotColumn);
            const double rotatedRowValue = cosine * aip - sine * aiq;
            const double rotatedColumnValue = sine * aip + cosine * aiq;

            matrix(index, pivotRow) = rotatedRowValue;
            matrix(pivotRow, index) = rotatedRowValue;
            matrix(index, pivotColumn) = rotatedColumnValue;
            matrix(pivotColumn, index) = rotatedColumnValue;
        }

        matrix(pivotRow, pivotRow) =
            cosine * cosine * app - 2.0 * sine * cosine * apq + sine * sine * aqq;
        matrix(pivotColumn, pivotColumn) =
            sine * sine * app + 2.0 * sine * cosine * apq + cosine * cosine * aqq;
        matrix(pivotRow, pivotColumn) = 0.0;
        matrix(pivotColumn, pivotRow) = 0.0;

        for (std::size_t rowIndex = 0; rowIndex < size; ++rowIndex) {
            const double vip = eigenvectors[rowIndex][pivotRow];
            const double viq = eigenvectors[rowIndex][pivotColumn];
            eigenvectors[rowIndex][pivotRow] = cosine * vip - sine * viq;
            eigenvectors[rowIndex][pivotColumn] = sine * vip + cosine * viq;
        }
    }

    std::vector<double> eigenvalues(size, 0.0);
    for (std::size_t index = 0; index < size; ++index) {
        eigenvalues[index] = matrix(index, index);
    }

    return sortEigenComponents(std::move(eigenvalues), std::move(eigenvectors));
}

class ArraysAdjacencyMatrixStrategy final : public AdjacencyMatrixStrategy {
  public:
    [[nodiscard]] std::string_view method() const noexcept override
    {
        return "arrays";
    }

    [[nodiscard]] AdjacencyMatrix build(const NormalizedAdjacencyInput& input,
                                        const std::string_view sourceFile) const override
    {
        std::vector<std::vector<int>> matrix(input.size(), std::vector<int>(input.size(), 0));

        for (const auto& bond : input.bonds) {
            matrix[bond.sourceIndex][bond.targetIndex] = bond.weight;
            matrix[bond.targetIndex][bond.sourceIndex] = bond.weight;
        }

        return AdjacencyMatrix{
            .sourceFile = std::string(sourceFile),
            .method = std::string(method()),
            .atomIds = input.atomIds,
            .values = std::move(matrix),
        };
    }
};

class ArmadilloAdjacencyMatrixStrategy final : public AdjacencyMatrixStrategy {
  public:
    [[nodiscard]] std::string_view method() const noexcept override
    {
        return "armadillo";
    }

    [[nodiscard]] AdjacencyMatrix build(const NormalizedAdjacencyInput& input,
                                        const std::string_view sourceFile) const override
    {
        arma::Mat<int> matrix(input.size(), input.size(), arma::fill::zeros);

        for (const auto& bond : input.bonds) {
            matrix(bond.sourceIndex, bond.targetIndex) = bond.weight;
            matrix(bond.targetIndex, bond.sourceIndex) = bond.weight;
        }

        std::vector<std::vector<int>> values(input.size(), std::vector<int>(input.size(), 0));
        for (std::size_t rowIndex = 0; rowIndex < input.size(); ++rowIndex) {
            for (std::size_t columnIndex = 0; columnIndex < input.size(); ++columnIndex) {
                values[rowIndex][columnIndex] = matrix(rowIndex, columnIndex);
            }
        }

        return AdjacencyMatrix{
            .sourceFile = std::string(sourceFile),
            .method = std::string(method()),
            .atomIds = input.atomIds,
            .values = std::move(values),
        };
    }
};

class BoostGraphAdjacencyMatrixStrategy final : public AdjacencyMatrixStrategy {
  public:
    [[nodiscard]] std::string_view method() const noexcept override
    {
        return "boost-graph";
    }

    [[nodiscard]] AdjacencyMatrix build(const NormalizedAdjacencyInput& input,
                                        const std::string_view sourceFile) const override
    {
        using Graph = boost::adjacency_list<boost::vecS,
                                            boost::vecS,
                                            boost::undirectedS,
                                            boost::no_property,
                                            boost::property<boost::edge_weight_t, int>>;

        Graph graph(input.size());
        for (const auto& bond : input.bonds) {
            boost::add_edge(static_cast<Graph::vertices_size_type>(bond.sourceIndex),
                            static_cast<Graph::vertices_size_type>(bond.targetIndex),
                            bond.weight,
                            graph);
        }

        const auto edgeWeights = boost::get(boost::edge_weight, graph);
        std::vector<std::vector<int>> matrix(input.size(), std::vector<int>(input.size(), 0));

        for (auto [edgeIterator, edgeEnd] = boost::edges(graph); edgeIterator != edgeEnd;
             ++edgeIterator) {
            const auto edge = *edgeIterator;
            const auto sourceIndex = static_cast<std::size_t>(boost::source(edge, graph));
            const auto targetIndex = static_cast<std::size_t>(boost::target(edge, graph));
            const int weight = edgeWeights[edge];
            matrix[sourceIndex][targetIndex] = weight;
            matrix[targetIndex][sourceIndex] = weight;
        }

        return AdjacencyMatrix{
            .sourceFile = std::string(sourceFile),
            .method = std::string(method()),
            .atomIds = input.atomIds,
            .values = std::move(matrix),
        };
    }
};

class ArmadilloEigendecompositionStrategy final : public EigendecompositionStrategy {
  public:
    [[nodiscard]] std::string_view method() const noexcept override
    {
        return "armadillo";
    }

    [[nodiscard]] EigendecompositionResult compute(const AdjacencyMatrix& matrix) const override
    {
        arma::mat values(matrix.values.size(), matrix.values.size(), arma::fill::zeros);
        for (std::size_t rowIndex = 0; rowIndex < matrix.values.size(); ++rowIndex) {
            for (std::size_t columnIndex = 0; columnIndex < matrix.values[rowIndex].size();
                 ++columnIndex) {
                values(rowIndex, columnIndex) =
                    static_cast<double>(matrix.values[rowIndex][columnIndex]);
            }
        }

        arma::vec eigenvalues;
        arma::mat eigenvectors;
        if (!arma::eig_sym(eigenvalues, eigenvectors, values)) {
            throw std::runtime_error("Armadillo failed to compute eigendecomposition");
        }

        EigenComponents components{
            .eigenvalues = std::vector<double>(eigenvalues.begin(), eigenvalues.end()),
            .eigenvectors = std::vector<std::vector<double>>(
                eigenvectors.n_rows, std::vector<double>(eigenvectors.n_cols, 0.0)),
        };

        for (std::size_t rowIndex = 0; rowIndex < eigenvectors.n_rows; ++rowIndex) {
            for (std::size_t columnIndex = 0; columnIndex < eigenvectors.n_cols; ++columnIndex) {
                components.eigenvectors[rowIndex][columnIndex] =
                    eigenvectors(rowIndex, columnIndex);
            }
        }

        return makeEigendecompositionResult(matrix, method(), std::move(components));
    }
};

class BoostEigendecompositionStrategy final : public EigendecompositionStrategy {
  public:
    [[nodiscard]] std::string_view method() const noexcept override
    {
        return "boost";
    }

    [[nodiscard]] EigendecompositionResult compute(const AdjacencyMatrix& matrix) const override
    {
        return makeEigendecompositionResult(
            matrix, method(), jacobiEigenDecomposition(toUblasMatrix(matrix)));
    }
};

class ArmadilloLaplacianAnalysisStrategy final : public LaplacianAnalysisStrategy {
  public:
    [[nodiscard]] std::string_view method() const noexcept override
    {
        return "armadillo";
    }

    [[nodiscard]] LaplacianAnalysisResult analyze(const AdjacencyMatrix& matrix,
                                                  const double zeroTolerance) const override
    {
        const auto laplacianMatrix = buildLaplacianMatrixValues(matrix);
        const auto degreeVector = computeDegreeVector(toDoubleMatrix(matrix));
        const arma::mat values = toArmadilloMatrix(laplacianMatrix);

        arma::vec eigenvalues;
        arma::mat eigenvectors;
        if (!arma::eig_sym(eigenvalues, eigenvectors, values)) {
            throw LaplacianAnalysisError(
                "Armadillo failed to compute Laplacian eigendecomposition");
        }

        EigenComponents components{
            .eigenvalues = std::vector<double>(eigenvalues.begin(), eigenvalues.end()),
            .eigenvectors = toVectorMatrix(eigenvectors),
        };

        return makeLaplacianAnalysisResult(
            matrix, method(), degreeVector, laplacianMatrix, std::move(components), zeroTolerance);
    }
};

class BoostLaplacianAnalysisStrategy final : public LaplacianAnalysisStrategy {
  public:
    [[nodiscard]] std::string_view method() const noexcept override
    {
        return "boost";
    }

    [[nodiscard]] LaplacianAnalysisResult analyze(const AdjacencyMatrix& matrix,
                                                  const double zeroTolerance) const override
    {
        const auto laplacianMatrix = buildLaplacianMatrixValues(matrix);
        const auto degreeVector = computeDegreeVector(toDoubleMatrix(matrix));

        UblasMatrix values(laplacianMatrix.size(), laplacianMatrix.size());
        for (std::size_t rowIndex = 0; rowIndex < laplacianMatrix.size(); ++rowIndex) {
            for (std::size_t columnIndex = 0; columnIndex < laplacianMatrix[rowIndex].size();
                 ++columnIndex) {
                values(rowIndex, columnIndex) = laplacianMatrix[rowIndex][columnIndex];
            }
        }

        return makeLaplacianAnalysisResult(matrix,
                                           method(),
                                           degreeVector,
                                           laplacianMatrix,
                                           jacobiEigenDecomposition(std::move(values)),
                                           zeroTolerance);
    }
};

class JsonDistanceMatrixStrategy final : public DistanceMatrixStrategy {
  public:
    [[nodiscard]] std::string_view method() const noexcept override
    {
        return "json";
    }

    [[nodiscard]] DistanceMatrixResult build(const DistanceMatrixInput& input) const override
    {
        std::ifstream jsonInput(input.jsonPath);
        if (!jsonInput) {
            throw DistanceAnalysisError("Could not open distance JSON input file: " +
                                        input.jsonPath.string());
        }

        Json root;
        jsonInput >> root;

        const auto& compounds = root.at("PC_Compounds");
        if (!compounds.is_array() || compounds.empty()) {
            throw DistanceAnalysisError("PC_Compounds must contain at least one compound");
        }

        const auto& compound = compounds.at(0);
        const auto& coords = compound.at("coords");
        if (!coords.is_array() || coords.empty()) {
            throw DistanceAnalysisError("coords must contain at least one coordinate entry");
        }

        const auto& coordinateSet = coords.at(0);
        const auto coordinateAtomIds = jsonToIntVector(coordinateSet.at("aid"), "coords[0].aid");
        const auto& conformers = coordinateSet.at("conformers");
        if (!conformers.is_array() || conformers.empty()) {
            throw DistanceAnalysisError("coords[0].conformers must contain at least one conformer");
        }

        const auto& conformer = conformers.at(0);
        const auto x = jsonToDoubleVector(conformer.at("x"), "coords[0].conformers[0].x");
        const auto y = jsonToDoubleVector(conformer.at("y"), "coords[0].conformers[0].y");
        const auto z = jsonToDoubleVector(conformer.at("z"), "coords[0].conformers[0].z");

        if (coordinateAtomIds.size() != x.size() || x.size() != y.size() || x.size() != z.size()) {
            throw DistanceAnalysisError(
                "JSON coordinate atom ids and x/y/z arrays must have the same length");
        }

        std::map<int, std::vector<double>> coordinatesByAtomId;
        for (std::size_t index = 0; index < coordinateAtomIds.size(); ++index) {
            coordinatesByAtomId.emplace(coordinateAtomIds[index],
                                        std::vector<double>{x[index], y[index], z[index]});
        }

        std::vector<std::vector<double>> orderedCoordinates;
        orderedCoordinates.reserve(input.atomIds.size());
        for (const auto atomId : input.atomIds) {
            const auto iterator = coordinatesByAtomId.find(atomId);
            if (iterator == coordinatesByAtomId.end()) {
                throw DistanceAnalysisError("Missing JSON coordinates for atom id " +
                                            std::to_string(atomId));
            }
            orderedCoordinates.push_back(iterator->second);
        }

        return makeDistanceMatrixResult(
            input, method(), input.jsonPath.filename().string(), std::move(orderedCoordinates));
    }
};

class SdfDistanceMatrixStrategy final : public DistanceMatrixStrategy {
  public:
    [[nodiscard]] std::string_view method() const noexcept override
    {
        return "sdf";
    }

    [[nodiscard]] DistanceMatrixResult build(const DistanceMatrixInput& input) const override
    {
        return makeDistanceMatrixResult(
            input, method(), input.sdfPath.filename().string(), loadSdfCoordinates(input.sdfPath));
    }
};

const AdjacencyMatrixStrategy& resolveAdjacencyStrategy(const std::string_view method)
{
    static const ArraysAdjacencyMatrixStrategy arraysStrategy;
    static const ArmadilloAdjacencyMatrixStrategy armadilloStrategy;
    static const BoostGraphAdjacencyMatrixStrategy boostGraphStrategy;

    const std::string normalizedMethod = parseAdjacencyMethod(method);
    if (normalizedMethod == arraysStrategy.method()) {
        return arraysStrategy;
    }

    if (normalizedMethod == boostGraphStrategy.method()) {
        return boostGraphStrategy;
    }

    return armadilloStrategy;
}

const EigendecompositionStrategy& resolveEigendecompositionStrategy(const std::string_view method)
{
    static const ArmadilloEigendecompositionStrategy armadilloStrategy;
    static const BoostEigendecompositionStrategy boostStrategy;

    const std::string normalizedMethod = parseEigendecompositionMethod(method);
    if (normalizedMethod == boostStrategy.method()) {
        return boostStrategy;
    }

    return armadilloStrategy;
}

const LaplacianAnalysisStrategy& resolveLaplacianAnalysisStrategy(const std::string_view method)
{
    static const ArmadilloLaplacianAnalysisStrategy armadilloStrategy;
    static const BoostLaplacianAnalysisStrategy boostStrategy;

    const std::string normalizedMethod = parseLaplacianMethod(method);
    if (normalizedMethod == boostStrategy.method()) {
        return boostStrategy;
    }

    return armadilloStrategy;
}

const DistanceMatrixStrategy& resolveDistanceMatrixStrategy(const std::string_view method)
{
    static const JsonDistanceMatrixStrategy jsonStrategy;
    static const SdfDistanceMatrixStrategy sdfStrategy;

    const std::string normalizedMethod = parseDistanceMethod(method);
    if (normalizedMethod == sdfStrategy.method()) {
        return sdfStrategy;
    }

    return jsonStrategy;
}

std::vector<int> jsonToIntVector(const Json& value, const std::string_view fieldName)
{
    if (!value.is_array()) {
        throw AdjacencyInputError(std::string(fieldName) + " must be an array");
    }

    return value.get<std::vector<int>>();
}
} // namespace

double averageOrZero(const std::vector<double>& values)
{
    if (values.empty()) {
        return 0.0;
    }

    const double total = std::accumulate(values.begin(), values.end(), 0.0);
    return total / static_cast<double>(values.size());
}

std::size_t NormalizedAdjacencyInput::size() const noexcept
{
    return atomIds.size();
}

std::vector<std::string> supportedAdjacencyMethods()
{
    return {"arrays", "armadillo", "boost-graph"};
}

std::string parseAdjacencyMethod(const std::string_view method)
{
    const std::string normalizedMethod(method);
    for (const auto& supportedMethod : supportedAdjacencyMethods()) {
        if (normalizedMethod == supportedMethod) {
            return supportedMethod;
        }
    }

    throw std::invalid_argument("Unsupported adjacency method '" + normalizedMethod +
                                "'. Supported values: arrays, armadillo, boost-graph");
}

std::vector<std::string> supportedEigendecompositionMethods()
{
    return {"armadillo", "boost"};
}

std::string parseEigendecompositionMethod(const std::string_view method)
{
    const std::string normalizedMethod(method);
    for (const auto& supportedMethod : supportedEigendecompositionMethods()) {
        if (normalizedMethod == supportedMethod) {
            return supportedMethod;
        }
    }

    throw std::invalid_argument("Unsupported eigendecomposition method '" + normalizedMethod +
                                "'. Supported values: armadillo, boost");
}

std::vector<std::string> supportedLaplacianMethods()
{
    return {"armadillo", "boost"};
}

std::vector<std::string> supportedDistanceMethods()
{
    return {"json", "sdf"};
}

std::string parseLaplacianMethod(const std::string_view method)
{
    const std::string normalizedMethod(method);
    for (const auto& supportedMethod : supportedLaplacianMethods()) {
        if (normalizedMethod == supportedMethod) {
            return supportedMethod;
        }
    }

    throw std::invalid_argument("Unsupported Laplacian method '" + normalizedMethod +
                                "'. Supported values: armadillo, boost");
}

std::string parseDistanceMethod(const std::string_view method)
{
    const std::string normalizedMethod(method);
    for (const auto& supportedMethod : supportedDistanceMethods()) {
        if (normalizedMethod == supportedMethod) {
            return supportedMethod;
        }
    }

    throw std::invalid_argument("Unsupported distance method '" + normalizedMethod +
                                "'. Supported values: json, sdf");
}

NormalizedAdjacencyInput loadAdjacencyInput(const std::filesystem::path& jsonPath)
{
    std::ifstream input(jsonPath);
    if (!input) {
        throw std::runtime_error("Could not open adjacency input file: " + jsonPath.string());
    }

    Json root;
    input >> root;

    const auto& compounds = root.at("PC_Compounds");
    if (!compounds.is_array() || compounds.empty()) {
        throw AdjacencyInputError("PC_Compounds must contain at least one compound");
    }

    const auto& compound = compounds.at(0);
    auto atomIds = jsonToIntVector(compound.at("atoms").at("aid"), "atoms.aid");
    std::sort(atomIds.begin(), atomIds.end());

    const auto uniqueEnd = std::unique(atomIds.begin(), atomIds.end());
    if (uniqueEnd != atomIds.end()) {
        throw AdjacencyInputError("atoms.aid contains duplicate atom ids");
    }

    const auto aid1 = jsonToIntVector(compound.at("bonds").at("aid1"), "bonds.aid1");
    const auto aid2 = jsonToIntVector(compound.at("bonds").at("aid2"), "bonds.aid2");
    const auto order = jsonToIntVector(compound.at("bonds").at("order"), "bonds.order");

    if (aid1.size() != aid2.size() || aid1.size() != order.size()) {
        throw AdjacencyInputError("Bond arrays aid1, aid2, and order must have the same length");
    }

    std::map<int, std::size_t> atomIndexById;
    for (std::size_t index = 0; index < atomIds.size(); ++index) {
        atomIndexById.emplace(atomIds[index], index);
    }

    std::vector<WeightedBond> bonds;
    bonds.reserve(aid1.size());
    for (std::size_t index = 0; index < aid1.size(); ++index) {
        const auto sourceIterator = atomIndexById.find(aid1[index]);
        const auto targetIterator = atomIndexById.find(aid2[index]);
        if (sourceIterator == atomIndexById.end() || targetIterator == atomIndexById.end()) {
            throw AdjacencyInputError("Bond references an atom id not present in atoms.aid");
        }

        bonds.push_back(WeightedBond{
            .sourceAtomId = aid1[index],
            .targetAtomId = aid2[index],
            .weight = order[index],
            .sourceIndex = sourceIterator->second,
            .targetIndex = targetIterator->second,
        });
    }

    return NormalizedAdjacencyInput{
        .atomIds = std::move(atomIds),
        .bonds = std::move(bonds),
    };
}

AdjacencyMatrix buildAdjacencyMatrix(const NormalizedAdjacencyInput& input,
                                     const std::string_view sourceFile,
                                     const std::string_view method)
{
    return resolveAdjacencyStrategy(method).build(input, sourceFile);
}

EigendecompositionResult buildEigendecomposition(const AdjacencyMatrix& matrix,
                                                 const std::string_view method)
{
    return resolveEigendecompositionStrategy(method).compute(matrix);
}

LaplacianAnalysisResult buildLaplacianAnalysis(const AdjacencyMatrix& matrix,
                                               const std::string_view method,
                                               const double zeroTolerance)
{
    return resolveLaplacianAnalysisStrategy(method).analyze(matrix, zeroTolerance);
}

DistanceMatrixResult buildDistanceMatrix(const DistanceMatrixInput& input,
                                         const std::string_view method)
{
    return resolveDistanceMatrixStrategy(method).build(input);
}

std::filesystem::path outputDirectoryFor(const std::filesystem::path& dataDirectory)
{
    return dataDirectory / "out";
}

std::filesystem::path outputJsonPath(const std::filesystem::path& outputDirectory,
                                     const std::filesystem::path& sourceFile)
{
    return outputDirectory / (sourceFile.filename().string() + ".json");
}

std::filesystem::path adjacencyOutputJsonPath(const std::filesystem::path& outputDirectory,
                                              const std::filesystem::path& sourceFile,
                                              const std::string_view method)
{
    return outputDirectory /
           (sourceFile.stem().string() + "." + std::string(method) + ".adjacency_matrix.json");
}

std::filesystem::path eigendecompositionOutputJsonPath(const std::filesystem::path& outputDirectory,
                                                       const std::filesystem::path& sourceFile,
                                                       const std::string_view method)
{
    return outputDirectory /
           (sourceFile.stem().string() + "." + std::string(method) + ".eigendecomposition.json");
}

std::filesystem::path laplacianOutputJsonPath(const std::filesystem::path& outputDirectory,
                                              const std::filesystem::path& sourceFile,
                                              const std::string_view method)
{
    return outputDirectory /
           (sourceFile.stem().string() + "." + std::string(method) + ".laplacian_analysis.json");
}

std::filesystem::path distanceOutputJsonPath(const std::filesystem::path& outputDirectory,
                                             const std::filesystem::path& sourceFile,
                                             const std::string_view method)
{
    return outputDirectory /
           (sourceFile.stem().string() + "." + std::string(method) + ".distance_matrix.json");
}
} // namespace pubchem
