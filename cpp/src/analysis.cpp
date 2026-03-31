#include "analysis.hpp"

#include <algorithm>
#include <armadillo>
#include <boost/graph/adjacency_list.hpp>
#include <boost/graph/connected_components.hpp>
#include <boost/graph/graph_traits.hpp>
#include <boost/math/distributions/beta.hpp>
#include <boost/math/distributions/binomial.hpp>
#include <boost/math/distributions/chi_squared.hpp>
#include <boost/numeric/ublas/matrix.hpp>
#include <boost/numeric/ublas/matrix_proxy.hpp>
#include <cctype>
#include <cmath>
#include <fstream>
#include <iomanip>
#include <limits>
#include <map>
#include <numbers>
#include <numeric>
#include <optional>
#include <set>
#include <sstream>
#include <stdexcept>

#include <nlohmann/json.hpp>

#include <GraphMol/PeriodicTable.h>

namespace pubchem {
namespace {
using Json = nlohmann::json;

constexpr double kAngleVectorTolerance = 1.0e-10;
constexpr double kSpringDistanceTolerance = 1.0e-12;
constexpr double kSpringZeroResidualTolerance = 1.0e-12;
constexpr double kMinimumPositiveConcentration = 1.0e-6;
constexpr double kHillAucLowerBoundScale = 1.0e-2;
constexpr double kHillAucUpperBoundScale = 1.0e2;
constexpr std::size_t kHillAucGridSize = 400U;
constexpr double kDefaultPosteriorPriorAlpha = 1.0;
constexpr double kDefaultPosteriorPriorBeta = 1.0;
constexpr double kDefaultPosteriorCredibleIntervalMass = 0.95;
constexpr double kDefaultChiSquareExpectedCountThreshold = 5.0;
constexpr double kDefaultShapiroAlpha = 0.05;

using BondReferenceKey = std::tuple<std::string, std::string, int>;

const std::vector<std::string> kRequiredAtomEntropyElements{"O", "N", "C", "H"};

const std::map<int, double> kDefaultBondOrderSpringConstants{{1, 300.0}, {2, 500.0}, {3, 700.0}};
const std::map<int, double> kDefaultBondOrderLengthScales{{1, 1.0}, {2, 0.9}, {3, 0.85}};
const std::map<BondReferenceKey, double> kDefaultReferenceBondLengthsAngstrom{
    {BondReferenceKey{"C", "C", 1}, 1.54},
    {BondReferenceKey{"C", "C", 2}, 1.34},
    {BondReferenceKey{"C", "C", 3}, 1.20},
    {BondReferenceKey{"C", "N", 1}, 1.47},
    {BondReferenceKey{"C", "N", 2}, 1.28},
    {BondReferenceKey{"C", "N", 3}, 1.16},
    {BondReferenceKey{"C", "O", 1}, 1.43},
    {BondReferenceKey{"C", "O", 2}, 1.23},
    {BondReferenceKey{"C", "H", 1}, 1.09},
    {BondReferenceKey{"N", "H", 1}, 1.01},
    {BondReferenceKey{"O", "H", 1}, 0.96},
};

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

class BioactivityAnalysisError : public std::runtime_error {
  public:
    using std::runtime_error::runtime_error;
};

class GradientDescentAnalysisError : public std::runtime_error {
  public:
    using std::runtime_error::runtime_error;
};

struct BondedPairWithOrder {
    int atomId1;
    int atomId2;
    int bondOrder;
};

struct AtomGradientAccumulator {
    int atomId;
    std::string atomSymbol;
    std::size_t incidentBondCount;
    std::vector<double> gradientVector;
};

struct EigenComponents {
    std::vector<double> eigenvalues;
    std::vector<std::vector<double>> eigenvectors;
};

struct BinaryBioactivityContext {
    std::string sourceFile;
    std::vector<std::string> headers;
    std::map<std::string, std::size_t> headerIndex;
    std::size_t totalRows;
    std::size_t activityIndex;
    std::optional<std::size_t> aidTypeIndex;
    std::optional<std::size_t> activityTypeIndex;
    std::optional<std::size_t> targetNameIndex;
    std::optional<std::size_t> bioAssayNameIndex;
    std::size_t activeRows;
    std::size_t inactiveRows;
    std::size_t unspecifiedRows;
    std::size_t otherActivityRows;
    std::set<long long> retainedBioassayIds;
    std::vector<std::vector<std::string>> retainedRows;
};

struct AssayActivityCollapseRow {
    long long bioAssayAid;
    std::string assayActivity;
    std::size_t retainedBinaryRows;
    std::size_t activeRows;
    std::size_t inactiveRows;
    bool mixedEvidence;
    std::string activityType;
    std::string targetName;
    std::string bioAssayName;
};

using UblasMatrix = boost::numeric::ublas::matrix<double>;

std::vector<int> jsonToIntVector(const Json& value, std::string_view fieldName);

std::string formatDouble(const double value)
{
    std::ostringstream stream;
    stream << std::setprecision(15) << value;
    return stream.str();
}

std::string formatCompactDouble(const double value)
{
    std::ostringstream stream;
    stream << std::setprecision(4) << value;
    return stream.str();
}

std::string trimWhitespace(std::string value)
{
    const auto first =
        std::find_if_not(value.begin(), value.end(), [](const unsigned char character) {
            return std::isspace(character) != 0;
        });
    const auto last =
        std::find_if_not(value.rbegin(), value.rend(), [](const unsigned char character) {
            return std::isspace(character) != 0;
        }).base();

    if (first >= last) {
        return {};
    }

    return std::string(first, last);
}

std::vector<std::vector<std::string>> parseCsvRecords(std::istream& input)
{
    std::vector<std::vector<std::string>> records;
    std::vector<std::string> row;
    std::string field;
    bool inQuotes = false;

    char character = '\0';
    while (input.get(character)) {
        if (inQuotes) {
            if (character == '"') {
                if (input.peek() == '"') {
                    field.push_back('"');
                    input.get();
                }
                else {
                    inQuotes = false;
                }
            }
            else {
                field.push_back(character);
            }
            continue;
        }

        if (character == '"') {
            inQuotes = true;
            continue;
        }

        if (character == ',') {
            row.push_back(field);
            field.clear();
            continue;
        }

        if (character == '\r' || character == '\n') {
            if (character == '\r' && input.peek() == '\n') {
                input.get();
            }
            row.push_back(field);
            field.clear();
            records.push_back(row);
            row.clear();
            continue;
        }

        field.push_back(character);
    }

    if (inQuotes) {
        throw BioactivityAnalysisError("CSV input ended inside a quoted field");
    }

    if (!field.empty() || !row.empty()) {
        row.push_back(field);
        records.push_back(row);
    }

    return records;
}

std::string stripUtf8Bom(std::string value)
{
    constexpr char utf8Bom[] = "\xEF\xBB\xBF";
    if (value.rfind(utf8Bom, 0) == 0) {
        value.erase(0, 3);
    }
    return value;
}

std::string normalizeActivityType(std::string value)
{
    value = trimWhitespace(std::move(value));
    std::transform(value.begin(), value.end(), value.begin(), [](const unsigned char character) {
        return static_cast<char>(std::toupper(character));
    });
    return value;
}

std::string normalizePosteriorActivity(std::string value)
{
    value = trimWhitespace(std::move(value));
    std::transform(value.begin(), value.end(), value.begin(), [](const unsigned char character) {
        return static_cast<char>(std::toupper(character));
    });
    if (value.empty()) {
        return "UNSPECIFIED";
    }
    return value;
}

std::string normalizeOptionalLabel(std::string value, const std::string_view fallback)
{
    value = trimWhitespace(std::move(value));
    if (value.empty()) {
        return std::string(fallback);
    }
    return value;
}

std::string toTitleCase(std::string value)
{
    std::transform(value.begin(), value.end(), value.begin(), [](const unsigned char character) {
        return static_cast<char>(std::tolower(character));
    });
    if (!value.empty()) {
        value.front() = static_cast<char>(std::toupper(static_cast<unsigned char>(value.front())));
    }
    return value;
}

std::optional<double> parseDouble(const std::string& value)
{
    const std::string trimmedValue = trimWhitespace(value);
    if (trimmedValue.empty()) {
        return std::nullopt;
    }

    try {
        std::size_t parsedCharacters = 0;
        const double parsedValue = std::stod(trimmedValue, &parsedCharacters);
        if (parsedCharacters != trimmedValue.size()) {
            return std::nullopt;
        }
        return parsedValue;
    }
    catch (const std::exception&) {
        return std::nullopt;
    }
}

std::optional<double> parsePositiveDouble(const std::string& value)
{
    const auto parsedValue = parseDouble(value);
    if (!parsedValue.has_value() || *parsedValue <= 0.0) {
        return std::nullopt;
    }

    return parsedValue;
}

double computeMedian(std::vector<double> values)
{
    if (values.empty()) {
        throw BioactivityAnalysisError("Cannot compute median of an empty data set");
    }

    std::sort(values.begin(), values.end());
    const std::size_t middle = values.size() / 2;
    if (values.size() % 2U == 0U) {
        return (values[middle - 1] + values[middle]) / 2.0;
    }
    return values[middle];
}

double computeLinearQuantileFromSorted(const std::vector<double>& sortedValues,
                                      const double probability)
{
    if (sortedValues.empty()) {
        throw BioactivityAnalysisError("Cannot compute a quantile of an empty data set");
    }

    if (probability <= 0.0) {
        return sortedValues.front();
    }
    if (probability >= 1.0) {
        return sortedValues.back();
    }

    const double position = probability * static_cast<double>(sortedValues.size() - 1U);
    const auto lowerIndex = static_cast<std::size_t>(std::floor(position));
    const auto upperIndex = static_cast<std::size_t>(std::ceil(position));
    if (lowerIndex == upperIndex) {
        return sortedValues[lowerIndex];
    }

    const double interpolationWeight = position - static_cast<double>(lowerIndex);
    return sortedValues[lowerIndex] +
           interpolationWeight * (sortedValues[upperIndex] - sortedValues[lowerIndex]);
}

double computeMean(const std::vector<double>& values)
{
    if (values.empty()) {
        throw BioactivityAnalysisError("Cannot compute the mean of an empty data set");
    }

    return std::accumulate(values.begin(), values.end(), 0.0) /
           static_cast<double>(values.size());
}

double computeSampleVariance(const std::vector<double>& values, const double mean)
{
    if (values.size() < 2U) {
        return 0.0;
    }

    double sumSquaredResiduals = 0.0;
    for (const double value : values) {
        const double residual = value - mean;
        sumSquaredResiduals += residual * residual;
    }
    return sumSquaredResiduals / static_cast<double>(values.size() - 1U);
}

std::optional<double> computeBiasCorrectedSampleSkewness(const std::vector<double>& values,
                                                         const double mean)
{
    if (values.size() < 3U) {
        return std::nullopt;
    }

    double secondCentralMoment = 0.0;
    double thirdCentralMoment = 0.0;
    for (const double value : values) {
        const double residual = value - mean;
        secondCentralMoment += residual * residual;
        thirdCentralMoment += residual * residual * residual;
    }

    secondCentralMoment /= static_cast<double>(values.size());
    thirdCentralMoment /= static_cast<double>(values.size());
    if (secondCentralMoment <= 0.0) {
        return std::nullopt;
    }

    const double momentSkewness = thirdCentralMoment / std::pow(secondCentralMoment, 1.5);
    const double n = static_cast<double>(values.size());
    return std::sqrt(n * (n - 1.0)) / (n - 2.0) * momentSkewness;
}

long long parseRequiredLong(const std::vector<std::string>& row,
                            const std::map<std::string, std::size_t>& headerIndex,
                            const std::string_view fieldName)
{
    const auto iterator = headerIndex.find(std::string(fieldName));
    if (iterator == headerIndex.end() || iterator->second >= row.size()) {
        throw BioactivityAnalysisError("Bioactivity row is missing required field " +
                                       std::string(fieldName));
    }

    try {
        return std::stoll(row[iterator->second]);
    }
    catch (const std::exception& error) {
        throw BioactivityAnalysisError("Could not parse " + std::string(fieldName) +
                                       " as an integer: " + error.what());
    }
}

BioactivityMeasurement buildMeasurement(const std::vector<std::string>& row,
                                        const std::map<std::string, std::size_t>& headerIndex)
{
    return BioactivityMeasurement{
        .bioactivityId = parseRequiredLong(row, headerIndex, "Bioactivity_ID"),
        .bioAssayAid = parseRequiredLong(row, headerIndex, "BioAssay_AID"),
        .ic50Um = std::stod(row.at(headerIndex.at("IC50_uM"))),
        .pIC50 = std::stod(row.at(headerIndex.at("pIC50"))),
    };
}

std::string valueAtOrEmpty(const std::vector<std::string>& row,
                           const std::optional<std::size_t> index)
{
    if (!index.has_value() || *index >= row.size()) {
        return {};
    }
    return row[*index];
}

std::optional<std::size_t>
optionalColumnIndex(const std::map<std::string, std::size_t>& headerIndex,
                    const std::string_view fieldName)
{
    const auto iterator = headerIndex.find(std::string(fieldName));
    if (iterator == headerIndex.end()) {
        return std::nullopt;
    }
    return iterator->second;
}

std::vector<std::size_t> representativeRowPositions(const std::size_t rowCount)
{
    if (rowCount == 0U) {
        return {};
    }

    std::vector<std::size_t> positions{0U, rowCount / 2U, rowCount - 1U};
    std::sort(positions.begin(), positions.end());
    positions.erase(std::unique(positions.begin(), positions.end()), positions.end());
    return positions;
}

BinaryBioactivityContext loadBinaryBioactivityContext(const std::filesystem::path& csvPath)
{
    std::ifstream input(csvPath);
    if (!input) {
        throw BioactivityAnalysisError("Could not open bioactivity input file: " +
                                       csvPath.string());
    }

    auto records = parseCsvRecords(input);
    if (records.empty()) {
        throw BioactivityAnalysisError("Bioactivity CSV is empty: " + csvPath.string());
    }

    auto headers = records.front();
    if (!headers.empty()) {
        headers.front() = stripUtf8Bom(headers.front());
    }
    records.erase(records.begin());

    std::map<std::string, std::size_t> headerIndex;
    for (std::size_t index = 0; index < headers.size(); ++index) {
        headerIndex.emplace(headers[index], index);
    }

    for (const std::string_view requiredHeader : {"Bioactivity_ID", "BioAssay_AID", "Activity"}) {
        if (headerIndex.find(std::string(requiredHeader)) == headerIndex.end()) {
            throw BioactivityAnalysisError("Bioactivity CSV is missing required column: " +
                                           std::string(requiredHeader));
        }
    }

    const std::size_t activityIndex = headerIndex.at("Activity");
    const std::optional<std::size_t> aidTypeIndex = optionalColumnIndex(headerIndex, "Aid_Type");
    const std::optional<std::size_t> activityTypeIndex =
        optionalColumnIndex(headerIndex, "Activity_Type");
    const std::optional<std::size_t> targetNameIndex =
        optionalColumnIndex(headerIndex, "Target_Name");
    const std::optional<std::size_t> bioAssayNameIndex =
        optionalColumnIndex(headerIndex, "BioAssay_Name");

    std::size_t activeRows = 0U;
    std::size_t inactiveRows = 0U;
    std::size_t unspecifiedRows = 0U;
    std::size_t otherActivityRows = 0U;
    std::set<long long> retainedBioassayIds;
    std::vector<std::vector<std::string>> retainedRows;

    for (auto& row : records) {
        if (row.size() < headers.size()) {
            row.resize(headers.size());
        }

        const std::string normalizedActivity = normalizePosteriorActivity(row[activityIndex]);
        if (normalizedActivity == "ACTIVE") {
            ++activeRows;
        }
        else if (normalizedActivity == "INACTIVE") {
            ++inactiveRows;
        }
        else if (normalizedActivity == "UNSPECIFIED") {
            ++unspecifiedRows;
        }
        else {
            ++otherActivityRows;
        }

        if (normalizedActivity != "ACTIVE" && normalizedActivity != "INACTIVE") {
            continue;
        }

        row[activityIndex] = toTitleCase(normalizedActivity);
        if (aidTypeIndex.has_value()) {
            row[*aidTypeIndex] =
                normalizeOptionalLabel(valueAtOrEmpty(row, aidTypeIndex), "Unknown");
        }
        if (activityTypeIndex.has_value()) {
            row[*activityTypeIndex] =
                normalizeOptionalLabel(valueAtOrEmpty(row, activityTypeIndex), "Unknown");
        }
        if (targetNameIndex.has_value()) {
            row[*targetNameIndex] =
                normalizeOptionalLabel(valueAtOrEmpty(row, targetNameIndex), "Unknown");
        }
        if (bioAssayNameIndex.has_value()) {
            row[*bioAssayNameIndex] =
                normalizeOptionalLabel(valueAtOrEmpty(row, bioAssayNameIndex), "Unknown");
        }

        retainedBioassayIds.insert(parseRequiredLong(row, headerIndex, "BioAssay_AID"));
        retainedRows.push_back(std::move(row));
    }

    if (retainedRows.empty()) {
        throw BioactivityAnalysisError("No Active/Inactive rows were found in " +
                                       csvPath.filename().string());
    }

    return BinaryBioactivityContext{
        .sourceFile = csvPath.filename().string(),
        .headers = std::move(headers),
        .headerIndex = std::move(headerIndex),
        .totalRows = records.size(),
        .activityIndex = activityIndex,
        .aidTypeIndex = aidTypeIndex,
        .activityTypeIndex = activityTypeIndex,
        .targetNameIndex = targetNameIndex,
        .bioAssayNameIndex = bioAssayNameIndex,
        .activeRows = activeRows,
        .inactiveRows = inactiveRows,
        .unspecifiedRows = unspecifiedRows,
        .otherActivityRows = otherActivityRows,
        .retainedBioassayIds = std::move(retainedBioassayIds),
        .retainedRows = std::move(retainedRows),
    };
}

void writeCsvTable(const std::vector<std::string>& headers,
                   const std::vector<std::vector<std::string>>& rows,
                   const std::filesystem::path& outputPath,
                   const std::string_view context)
{
    std::ofstream output(outputPath);
    if (!output) {
        throw BioactivityAnalysisError("Could not open " + std::string(context) + ": " +
                                       outputPath.string());
    }

    const auto writeCsvRow = [&](const std::vector<std::string>& row) {
        for (std::size_t index = 0; index < row.size(); ++index) {
            if (index > 0) {
                output << ',';
            }
            const bool requiresQuotes = row[index].find_first_of(",\"\n\r") != std::string::npos;
            if (requiresQuotes) {
                output << '"';
                for (const char character : row[index]) {
                    if (character == '"') {
                        output << '"';
                    }
                    output << character;
                }
                output << '"';
            }
            else {
                output << row[index];
            }
        }
        output << '\n';
    };

    writeCsvRow(headers);
    for (const auto& row : rows) {
        writeCsvRow(row);
    }
}

std::pair<double, double> expandedDomain(const double minValue, const double maxValue)
{
    if (std::abs(minValue - maxValue) < 1.0e-12) {
        return {std::max(minValue / 10.0, 1.0e-6), maxValue * 10.0};
    }

    return {minValue, maxValue};
}

std::vector<double> geometricSpace(const double start, const double end, const std::size_t count)
{
    if (count < 2U) {
        return {start};
    }

    const double logStart = std::log10(start);
    const double logEnd = std::log10(end);
    std::vector<double> values;
    values.reserve(count);
    for (std::size_t index = 0; index < count; ++index) {
        const double t = static_cast<double>(index) / static_cast<double>(count - 1U);
        values.push_back(std::pow(10.0, logStart + t * (logEnd - logStart)));
    }
    return values;
}

double hillResponse(const double concentration,
                    const double halfMaximalConcentration,
                    const double hillCoefficient)
{
    const double numerator = std::pow(concentration, hillCoefficient);
    const double denominator = std::pow(halfMaximalConcentration, hillCoefficient) + numerator;
    return numerator / denominator;
}

double hillResponseFirstDerivative(const double concentration,
                                   const double halfMaximalConcentration,
                                   const double hillCoefficient)
{
    const double numerator = hillCoefficient * std::pow(halfMaximalConcentration, hillCoefficient) *
                             std::pow(concentration, hillCoefficient - 1.0);
    const double denominator = std::pow(std::pow(halfMaximalConcentration, hillCoefficient) +
                                            std::pow(concentration, hillCoefficient),
                                        2.0);
    return numerator / denominator;
}

double hillResponseSecondDerivative(const double concentration,
                                    const double halfMaximalConcentration,
                                    const double hillCoefficient)
{
    const double halfMaximalPower = std::pow(halfMaximalConcentration, hillCoefficient);
    const double concentrationPower = std::pow(concentration, hillCoefficient);
    const double numerator = hillCoefficient * halfMaximalPower *
                             std::pow(concentration, hillCoefficient - 2.0) *
                             (((hillCoefficient - 1.0) * halfMaximalPower) -
                              ((hillCoefficient + 1.0) * concentrationPower));
    const double denominator = std::pow(halfMaximalPower + concentrationPower, 3.0);
    return numerator / denominator;
}

std::optional<double> hillLinearInflectionScale(const double hillCoefficient)
{
    if (hillCoefficient <= 1.0) {
        return std::nullopt;
    }

    return std::pow((hillCoefficient - 1.0) / (hillCoefficient + 1.0), 1.0 / hillCoefficient);
}

double computeHillReferenceAucTrapezoid(const double inferredK,
                                        const double hillCoefficient,
                                        const double lowerBoundScale = kHillAucLowerBoundScale,
                                        const double upperBoundScale = kHillAucUpperBoundScale,
                                        const std::size_t gridSize = kHillAucGridSize)
{
    if (inferredK <= 0.0) {
        throw BioactivityAnalysisError(
            "AUC trapezoidal integration requires a strictly positive inferred K value");
    }
    if (hillCoefficient <= 0.0) {
        throw BioactivityAnalysisError("Hill coefficient must be positive");
    }
    if (lowerBoundScale <= 0.0 || upperBoundScale <= 0.0) {
        throw BioactivityAnalysisError("AUC concentration-bound scales must be positive");
    }
    if (lowerBoundScale >= upperBoundScale) {
        throw BioactivityAnalysisError(
            "AUC lower-bound scale must be smaller than the upper-bound scale");
    }
    if (gridSize < 2U) {
        throw BioactivityAnalysisError(
            "AUC trapezoidal integration requires at least two grid points");
    }

    const auto relativeConcentrationGrid =
        geometricSpace(lowerBoundScale, upperBoundScale, gridSize);

    double auc = 0.0;
    double previousConcentration = relativeConcentrationGrid.front() * inferredK;
    double previousResponse = hillResponse(previousConcentration, inferredK, hillCoefficient);
    for (std::size_t index = 1; index < relativeConcentrationGrid.size(); ++index) {
        const double currentConcentration = relativeConcentrationGrid[index] * inferredK;
        const double currentResponse =
            hillResponse(currentConcentration, inferredK, hillCoefficient);
        auc += ((currentConcentration - previousConcentration) *
                (previousResponse + currentResponse)) /
               2.0;
        previousConcentration = currentConcentration;
        previousResponse = currentResponse;
    }

    return auc;
}

double computeSumSquaredError(const std::vector<double>& xValues,
                              const std::vector<double>& yValues,
                              const double weight)
{
    double loss = 0.0;
    for (std::size_t index = 0; index < xValues.size(); ++index) {
        const double residual = yValues[index] - (weight * xValues[index]);
        loss += residual * residual;
    }

    return loss;
}

double computeMeanSquaredError(const std::vector<double>& xValues,
                               const std::vector<double>& yValues,
                               const double weight)
{
    return computeSumSquaredError(xValues, yValues, weight) / static_cast<double>(xValues.size());
}

double computeSumSquaredErrorGradient(const std::vector<double>& xValues,
                                      const std::vector<double>& yValues,
                                      const double weight)
{
    double gradient = 0.0;
    for (std::size_t index = 0; index < xValues.size(); ++index) {
        gradient += xValues[index] * ((weight * xValues[index]) - yValues[index]);
    }

    return 2.0 * gradient;
}

double finiteDifferenceGradient(const std::vector<double>& xValues,
                                const std::vector<double>& yValues,
                                const double weight,
                                const double epsilon = 1.0e-6)
{
    const double forwardLoss = computeSumSquaredError(xValues, yValues, weight + epsilon);
    const double backwardLoss = computeSumSquaredError(xValues, yValues, weight - epsilon);
    return (forwardLoss - backwardLoss) / (2.0 * epsilon);
}

std::string escapeXml(std::string value)
{
    const std::pair<std::string_view, std::string_view> replacements[] = {
        {"&", "&amp;"}, {"<", "&lt;"}, {">", "&gt;"}, {"\"", "&quot;"}};
    for (const auto& [from, to] : replacements) {
        std::size_t position = 0;
        while ((position = value.find(from, position)) != std::string::npos) {
            value.replace(position, from.size(), to);
            position += to.size();
        }
    }
    return value;
}

std::string svgText(const double x,
                    const double y,
                    const std::string& text,
                    const std::string_view extraAttributes = {})
{
    std::ostringstream stream;
    stream << "<text x=\"" << x << "\" y=\"" << y << "\""
           << " font-family=\"Helvetica, Arial, sans-serif\" font-size=\"14\""
           << " fill=\"#111827\"";
    if (!extraAttributes.empty()) {
        stream << ' ' << extraAttributes;
    }
    stream << '>' << escapeXml(text) << "</text>";
    return stream.str();
}

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

double computePercentile(std::vector<double> values, const double percentile)
{
    if (values.empty()) {
        throw DistanceAnalysisError("Cannot compute a percentile for an empty data set");
    }

    if (percentile < 0.0 || percentile > 1.0) {
        throw DistanceAnalysisError("Percentile must be within [0, 1]");
    }

    std::sort(values.begin(), values.end());
    if (values.size() == 1U) {
        return values.front();
    }

    const double scaledIndex = percentile * static_cast<double>(values.size() - 1U);
    const auto lowerIndex = static_cast<std::size_t>(std::floor(scaledIndex));
    const auto upperIndex = static_cast<std::size_t>(std::ceil(scaledIndex));
    if (lowerIndex == upperIndex) {
        return values[lowerIndex];
    }

    const double fraction = scaledIndex - static_cast<double>(lowerIndex);
    return values[lowerIndex] + fraction * (values[upperIndex] - values[lowerIndex]);
}

void validateBondedDistanceAlignment(const DistanceMatrixResult& distanceMatrix,
                                     const AdjacencyMatrix& adjacencyMatrix)
{
    if (distanceMatrix.atomIds != adjacencyMatrix.atomIds) {
        throw DistanceAnalysisError(
            "Distance and adjacency atomIds must be aligned for bonded-distance analysis");
    }

    if (distanceMatrix.distanceMatrix.size() != adjacencyMatrix.values.size()) {
        throw DistanceAnalysisError("Distance matrix and adjacency matrix must have the same size");
    }
}

void validateBondAngleAlignment(const DistanceMatrixResult& distanceMatrix,
                                const AdjacencyMatrix& adjacencyMatrix)
{
    if (distanceMatrix.atomIds != adjacencyMatrix.atomIds) {
        throw DistanceAnalysisError(
            "Distance and adjacency atomIds must be aligned for bond-angle analysis");
    }

    if (distanceMatrix.xyzCoordinates.size() != adjacencyMatrix.values.size()) {
        throw DistanceAnalysisError(
            "Distance coordinates and adjacency matrix must have the same size");
    }
}

void validateSpringBondPotentialAlignment(const DistanceMatrixResult& distanceMatrix,
                                          const AdjacencyMatrix& adjacencyMatrix,
                                          const std::vector<AtomRecord>& atoms)
{
    if (distanceMatrix.atomIds != adjacencyMatrix.atomIds) {
        throw DistanceAnalysisError(
            "Distance and adjacency atomIds must be aligned for spring-bond analysis");
    }

    if (distanceMatrix.xyzCoordinates.size() != adjacencyMatrix.values.size()) {
        throw DistanceAnalysisError(
            "Distance coordinates and adjacency matrix must have the same size");
    }

    if (atoms.size() != distanceMatrix.atomIds.size()) {
        throw DistanceAnalysisError(
            "Spring-bond analysis requires atom records aligned with distance-matrix atom ids");
    }
}

std::vector<BondedAtomPair> bondedAtomPairsFromAdjacency(const AdjacencyMatrix& adjacencyMatrix)
{
    std::vector<BondedAtomPair> pairs;
    for (std::size_t rowIndex = 0; rowIndex < adjacencyMatrix.values.size(); ++rowIndex) {
        for (std::size_t columnIndex = rowIndex + 1;
             columnIndex < adjacencyMatrix.values[rowIndex].size();
             ++columnIndex) {
            if (adjacencyMatrix.values[rowIndex][columnIndex] > 0) {
                pairs.push_back(BondedAtomPair{
                    .atomId1 = adjacencyMatrix.atomIds[rowIndex],
                    .atomId2 = adjacencyMatrix.atomIds[columnIndex],
                });
            }
        }
    }

    if (pairs.empty()) {
        throw DistanceAnalysisError(
            "Expected at least one bonded atom pair in the adjacency matrix");
    }

    return pairs;
}

std::vector<BondedPairWithOrder>
bondedPairsWithOrderFromAdjacency(const AdjacencyMatrix& adjacencyMatrix)
{
    std::vector<BondedPairWithOrder> pairs;
    for (std::size_t rowIndex = 0; rowIndex < adjacencyMatrix.values.size(); ++rowIndex) {
        for (std::size_t columnIndex = rowIndex + 1;
             columnIndex < adjacencyMatrix.values[rowIndex].size();
             ++columnIndex) {
            const int bondOrder = adjacencyMatrix.values[rowIndex][columnIndex];
            if (bondOrder > 0) {
                pairs.push_back(BondedPairWithOrder{
                    .atomId1 = adjacencyMatrix.atomIds[rowIndex],
                    .atomId2 = adjacencyMatrix.atomIds[columnIndex],
                    .bondOrder = bondOrder,
                });
            }
        }
    }

    if (pairs.empty()) {
        throw DistanceAnalysisError(
            "Expected at least one bonded atom pair in the adjacency matrix");
    }

    return pairs;
}

BondedDistanceStatistics summarizePairDistances(const std::vector<AtomPairDistance>& pairDistances)
{
    if (pairDistances.empty()) {
        throw DistanceAnalysisError("Distance partition must contain at least one pair");
    }

    std::vector<double> distances;
    distances.reserve(pairDistances.size());
    for (const auto& pairDistance : pairDistances) {
        distances.push_back(pairDistance.distanceAngstrom);
    }

    const double meanDistance = averageOrZero(distances);
    double variance = 0.0;
    for (const double distance : distances) {
        const double delta = distance - meanDistance;
        variance += delta * delta;
    }
    variance /= static_cast<double>(distances.size());

    return BondedDistanceStatistics{
        .count = distances.size(),
        .minDistanceAngstrom = *std::min_element(distances.begin(), distances.end()),
        .meanDistanceAngstrom = meanDistance,
        .stdDistanceAngstrom = std::sqrt(variance),
        .q25DistanceAngstrom = computePercentile(distances, 0.25),
        .medianDistanceAngstrom = computePercentile(distances, 0.5),
        .q75DistanceAngstrom = computePercentile(distances, 0.75),
        .maxDistanceAngstrom = *std::max_element(distances.begin(), distances.end()),
    };
}

std::vector<BondAngleTriplet> bondAngleTripletsFromAdjacency(const AdjacencyMatrix& adjacencyMatrix)
{
    std::vector<BondAngleTriplet> triplets;

    for (std::size_t centerIndex = 0; centerIndex < adjacencyMatrix.values.size(); ++centerIndex) {
        std::vector<int> neighbors;
        for (std::size_t neighborIndex = 0;
             neighborIndex < adjacencyMatrix.values[centerIndex].size();
             ++neighborIndex) {
            if (adjacencyMatrix.values[centerIndex][neighborIndex] > 0) {
                neighbors.push_back(adjacencyMatrix.atomIds[neighborIndex]);
            }
        }

        for (std::size_t leftIndex = 0; leftIndex < neighbors.size(); ++leftIndex) {
            for (std::size_t rightIndex = leftIndex + 1; rightIndex < neighbors.size();
                 ++rightIndex) {
                triplets.push_back(BondAngleTriplet{
                    .atomIdA = neighbors[leftIndex],
                    .atomIdBCenter = adjacencyMatrix.atomIds[centerIndex],
                    .atomIdC = neighbors[rightIndex],
                });
            }
        }
    }

    if (triplets.empty()) {
        throw DistanceAnalysisError(
            "Expected at least one bonded angle triplet in the adjacency matrix");
    }

    return triplets;
}

std::vector<double> subtractCoordinates(const std::vector<double>& left,
                                        const std::vector<double>& right)
{
    return {left[0] - right[0], left[1] - right[1], left[2] - right[2]};
}

double vectorMagnitude(const std::vector<double>& values)
{
    return std::sqrt(values[0] * values[0] + values[1] * values[1] + values[2] * values[2]);
}

double dotProduct(const std::vector<double>& left, const std::vector<double>& right)
{
    return left[0] * right[0] + left[1] * right[1] + left[2] * right[2];
}

double computeBondAngleDegrees(const std::vector<double>& firstBondVector,
                               const std::vector<double>& secondBondVector)
{
    const double firstMagnitude = vectorMagnitude(firstBondVector);
    const double secondMagnitude = vectorMagnitude(secondBondVector);

    if (firstMagnitude <= kAngleVectorTolerance || secondMagnitude <= kAngleVectorTolerance) {
        throw DistanceAnalysisError("Bond angle computation requires non-zero bond vectors");
    }

    const double cosine =
        dotProduct(firstBondVector, secondBondVector) / (firstMagnitude * secondMagnitude);
    constexpr double radiansToDegrees = 180.0 / std::numbers::pi;
    return std::acos(std::clamp(cosine, -1.0, 1.0)) * radiansToDegrees;
}

std::vector<double> addCoordinates(const std::vector<double>& left,
                                   const std::vector<double>& right)
{
    return {left[0] + right[0], left[1] + right[1], left[2] + right[2]};
}

std::vector<double> scaleCoordinates(const std::vector<double>& values, const double factor)
{
    return {values[0] * factor, values[1] * factor, values[2] * factor};
}

std::string normalizedAtomSymbol(const AtomRecord& atom)
{
    if (!atom.symbol.empty()) {
        return atom.symbol;
    }

    if (atom.atomicNumber <= 0) {
        throw DistanceAnalysisError("Spring-bond analysis could not resolve an atom symbol");
    }

    return RDKit::PeriodicTable::getTable()->getElementSymbol(atom.atomicNumber);
}

double covalentRadiusForSymbol(const std::string& symbol)
{
    const double radius = RDKit::PeriodicTable::getTable()->getRcovalent(symbol);
    if (!(radius > 0.0)) {
        throw DistanceAnalysisError("Could not infer a positive covalent radius for symbol: " +
                                    symbol);
    }

    return radius;
}

std::pair<double, std::string> inferReferenceBondLengthAngstrom(const std::string& atomSymbol1,
                                                                const std::string& atomSymbol2,
                                                                const int bondOrder)
{
    if (bondOrder <= 0) {
        throw DistanceAnalysisError(
            "Bond order must be positive when inferring a spring reference distance");
    }

    const auto [leftSymbol, rightSymbol] =
        std::minmax(atomSymbol1, atomSymbol2, std::less<std::string>{});
    const BondReferenceKey key{leftSymbol, rightSymbol, bondOrder};
    const auto lookupIterator = kDefaultReferenceBondLengthsAngstrom.find(key);
    if (lookupIterator != kDefaultReferenceBondLengthsAngstrom.end()) {
        return {lookupIterator->second, "lookupTable"};
    }

    const double covalentRadiusSum =
        covalentRadiusForSymbol(atomSymbol1) + covalentRadiusForSymbol(atomSymbol2);
    const auto scaleIterator = kDefaultBondOrderLengthScales.find(bondOrder);
    const double lengthScale = scaleIterator != kDefaultBondOrderLengthScales.end()
                                   ? scaleIterator->second
                                   : 1.0 / std::sqrt(static_cast<double>(bondOrder));
    return {covalentRadiusSum * lengthScale, "covalentRadiusFallback"};
}

double resolveSpringConstantForBondOrder(const int bondOrder)
{
    if (bondOrder <= 0) {
        throw DistanceAnalysisError("Bond order must be positive when resolving a spring constant");
    }

    const auto iterator = kDefaultBondOrderSpringConstants.find(bondOrder);
    if (iterator != kDefaultBondOrderSpringConstants.end()) {
        return iterator->second;
    }

    return kDefaultBondOrderSpringConstants.at(1) * static_cast<double>(bondOrder);
}

CartesianPartialDerivatives toCartesianPartialDerivatives(const std::vector<double>& gradientVector)
{
    return CartesianPartialDerivatives{.dEDx = gradientVector[0],
                                       .dEDy = gradientVector[1],
                                       .dEDz = gradientVector[2],
                                       .gradientNorm = vectorMagnitude(gradientVector)};
}

DistanceResidualStatistics summarizeDistanceResiduals(const std::vector<double>& residuals)
{
    const double meanResidual = averageOrZero(residuals);
    double variance = 0.0;
    for (const double residual : residuals) {
        const double delta = residual - meanResidual;
        variance += delta * delta;
    }
    variance /= static_cast<double>(residuals.size());

    return DistanceResidualStatistics{
        .count = residuals.size(),
        .min = *std::min_element(residuals.begin(), residuals.end()),
        .mean = meanResidual,
        .std = std::sqrt(variance),
        .q25 = computePercentile(residuals, 0.25),
        .median = computePercentile(residuals, 0.5),
        .q75 = computePercentile(residuals, 0.75),
        .max = *std::max_element(residuals.begin(), residuals.end()),
        .zeroResidualBondCount = static_cast<std::size_t>(
            std::count_if(residuals.begin(), residuals.end(), [](const double value) {
                return std::abs(value) <= kSpringZeroResidualTolerance;
            }))};
}

SpringEnergyStatistics summarizeSpringEnergies(const std::vector<double>& springEnergies)
{
    const double meanEnergy = averageOrZero(springEnergies);
    double variance = 0.0;
    for (const double springEnergy : springEnergies) {
        const double delta = springEnergy - meanEnergy;
        variance += delta * delta;
    }
    variance /= static_cast<double>(springEnergies.size());

    return SpringEnergyStatistics{
        .count = springEnergies.size(),
        .total = std::accumulate(springEnergies.begin(), springEnergies.end(), 0.0),
        .min = *std::min_element(springEnergies.begin(), springEnergies.end()),
        .mean = meanEnergy,
        .std = std::sqrt(variance),
        .q25 = computePercentile(springEnergies, 0.25),
        .median = computePercentile(springEnergies, 0.5),
        .q75 = computePercentile(springEnergies, 0.75),
        .max = *std::max_element(springEnergies.begin(), springEnergies.end())};
}

AtomGradientNormStatistics summarizeAtomGradientNorms(const std::vector<double>& atomGradientNorms)
{
    const double meanNorm = averageOrZero(atomGradientNorms);
    double variance = 0.0;
    for (const double atomGradientNorm : atomGradientNorms) {
        const double delta = atomGradientNorm - meanNorm;
        variance += delta * delta;
    }
    variance /= static_cast<double>(atomGradientNorms.size());

    return AtomGradientNormStatistics{
        .count = atomGradientNorms.size(),
        .min = *std::min_element(atomGradientNorms.begin(), atomGradientNorms.end()),
        .mean = meanNorm,
        .std = std::sqrt(variance),
        .q25 = computePercentile(atomGradientNorms, 0.25),
        .median = computePercentile(atomGradientNorms, 0.5),
        .q75 = computePercentile(atomGradientNorms, 0.75),
        .max = *std::max_element(atomGradientNorms.begin(), atomGradientNorms.end())};
}

BondAngleStatistics summarizeBondAngles(const std::vector<BondAngleMeasurement>& bondAngles)
{
    if (bondAngles.empty()) {
        throw DistanceAnalysisError("Bond angle analysis must contain at least one angle");
    }

    std::vector<double> angleValues;
    angleValues.reserve(bondAngles.size());
    for (const auto& bondAngle : bondAngles) {
        angleValues.push_back(bondAngle.angleDegrees);
    }

    const double meanAngle = averageOrZero(angleValues);
    double variance = 0.0;
    for (const double angle : angleValues) {
        const double delta = angle - meanAngle;
        variance += delta * delta;
    }
    variance /= static_cast<double>(angleValues.size());

    return BondAngleStatistics{
        .count = angleValues.size(),
        .minAngleDegrees = *std::min_element(angleValues.begin(), angleValues.end()),
        .meanAngleDegrees = meanAngle,
        .stdAngleDegrees = std::sqrt(variance),
        .q25AngleDegrees = computePercentile(angleValues, 0.25),
        .medianAngleDegrees = computePercentile(angleValues, 0.5),
        .q75AngleDegrees = computePercentile(angleValues, 0.75),
        .maxAngleDegrees = *std::max_element(angleValues.begin(), angleValues.end()),
    };
}

BondAngleAnalysisResult makeBondAngleAnalysisResult(const DistanceMatrixResult& distanceMatrix,
                                                    std::vector<BondAngleTriplet> triplets,
                                                    std::vector<BondAngleMeasurement> bondAngles)
{
    const BondAngleStatistics statistics = summarizeBondAngles(bondAngles);

    return BondAngleAnalysisResult{
        .atomIds = distanceMatrix.atomIds,
        .bondAngleTriplets = std::move(triplets),
        .bondAngles = std::move(bondAngles),
        .statistics = statistics,
        .metadata =
            BondAngleMetadata{
                .atomCount = distanceMatrix.atomIds.size(),
                .bondedAngleTripletCount = statistics.count,
                .sourceDistanceMethod = distanceMatrix.method,
                .units = "degrees",
                .selectionRule =
                    "angles A-B-C where A-B and B-C are bonded and B is the central atom",
            },
    };
}

BondedDistanceAnalysisResult
makeBondedDistanceAnalysisResult(const DistanceMatrixResult& distanceMatrix,
                                 std::vector<BondedAtomPair> bondedAtomPairs,
                                 std::vector<AtomPairDistance> bondedPairDistances,
                                 std::vector<AtomPairDistance> nonbondedPairDistances)
{
    const BondedDistanceStatistics bondedDistances = summarizePairDistances(bondedPairDistances);
    const BondedDistanceStatistics nonbondedDistances =
        summarizePairDistances(nonbondedPairDistances);

    return BondedDistanceAnalysisResult{
        .atomIds = distanceMatrix.atomIds,
        .bondedAtomPairs = std::move(bondedAtomPairs),
        .bondedPairDistances = std::move(bondedPairDistances),
        .nonbondedPairDistances = std::move(nonbondedPairDistances),
        .bondedDistances = bondedDistances,
        .nonbondedDistances = nonbondedDistances,
        .comparison =
            BondedDistanceComparison{
                .meanDistanceDifferenceAngstrom =
                    nonbondedDistances.meanDistanceAngstrom - bondedDistances.meanDistanceAngstrom,
                .nonbondedToBondedMeanRatio =
                    nonbondedDistances.meanDistanceAngstrom / bondedDistances.meanDistanceAngstrom,
            },
        .metadata =
            BondedDistanceMetadata{
                .atomCount = distanceMatrix.atomIds.size(),
                .bondedPairCount = bondedDistances.count,
                .nonbondedPairCount = nonbondedDistances.count,
                .totalUniquePairCount = bondedDistances.count + nonbondedDistances.count,
                .sourceDistanceMethod = distanceMatrix.method,
                .units = distanceMatrix.metadata.units,
            },
    };
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

BioactivityAnalysisResult buildBioactivityAnalysis(const std::filesystem::path& csvPath)
{
    std::ifstream input(csvPath);
    if (!input) {
        throw BioactivityAnalysisError("Could not open bioactivity input file: " +
                                       csvPath.string());
    }

    auto records = parseCsvRecords(input);
    if (records.empty()) {
        throw BioactivityAnalysisError("Bioactivity CSV is empty: " + csvPath.string());
    }

    auto headers = records.front();
    if (!headers.empty()) {
        headers.front() = stripUtf8Bom(headers.front());
    }
    records.erase(records.begin());

    std::map<std::string, std::size_t> headerIndex;
    for (std::size_t index = 0; index < headers.size(); ++index) {
        headerIndex.emplace(headers[index], index);
    }

    for (const std::string_view requiredHeader :
         {"Bioactivity_ID", "BioAssay_AID", "Activity_Type", "Activity_Value"}) {
        if (!headerIndex.contains(std::string(requiredHeader))) {
            throw BioactivityAnalysisError("Bioactivity CSV is missing required column: " +
                                           std::string(requiredHeader));
        }
    }

    std::size_t numericValueCount = 0;
    std::size_t ic50TypeCount = 0;
    std::vector<std::vector<std::string>> filteredRows;
    std::vector<double> ic50Values;
    std::vector<double> pic50Values;

    const auto activityTypeIndex = headerIndex.at("Activity_Type");
    const auto activityValueIndex = headerIndex.at("Activity_Value");

    for (auto& row : records) {
        if (row.size() < headers.size()) {
            row.resize(headers.size());
        }

        const std::string normalizedActivityType =
            activityTypeIndex < row.size() ? normalizeActivityType(row[activityTypeIndex]) : "";
        const auto activityValue = activityValueIndex < row.size()
                                       ? parsePositiveDouble(row[activityValueIndex])
                                       : std::nullopt;

        if (activityValue.has_value()) {
            ++numericValueCount;
        }
        if (normalizedActivityType == "IC50") {
            ++ic50TypeCount;
        }

        if (normalizedActivityType != "IC50" || !activityValue.has_value()) {
            continue;
        }

        const double pIC50 = -std::log10(*activityValue);
        row[activityValueIndex] = formatDouble(*activityValue);
        row.push_back(formatDouble(*activityValue));
        row.push_back(formatDouble(pIC50));
        filteredRows.push_back(row);
        ic50Values.push_back(*activityValue);
        pic50Values.push_back(pIC50);
    }

    if (filteredRows.empty()) {
        throw BioactivityAnalysisError("No positive numeric IC50 rows were found in " +
                                       csvPath.filename().string());
    }

    headers.push_back("IC50_uM");
    headers.push_back("pIC50");
    headerIndex["IC50_uM"] = headers.size() - 2U;
    headerIndex["pIC50"] = headers.size() - 1U;

    std::stable_sort(
        filteredRows.begin(), filteredRows.end(), [&](const auto& left, const auto& right) {
            return std::stod(left.at(headerIndex.at("pIC50"))) >
                   std::stod(right.at(headerIndex.at("pIC50")));
        });

    const auto strongestRow = *std::max_element(
        filteredRows.begin(), filteredRows.end(), [&](const auto& left, const auto& right) {
            return std::stod(left.at(headerIndex.at("pIC50"))) <
                   std::stod(right.at(headerIndex.at("pIC50")));
        });
    const auto weakestRow = *std::min_element(
        filteredRows.begin(), filteredRows.end(), [&](const auto& left, const auto& right) {
            return std::stod(left.at(headerIndex.at("pIC50"))) <
                   std::stod(right.at(headerIndex.at("pIC50")));
        });

    return BioactivityAnalysisResult{
        .sourceFile = csvPath.filename().string(),
        .headers = std::move(headers),
        .filteredRows = std::move(filteredRows),
        .rowCounts =
            BioactivityRowCounts{
                .totalRows = records.size(),
                .rowsWithNumericActivityValue = numericValueCount,
                .rowsWithIc50ActivityType = ic50TypeCount,
                .retainedIc50Rows = ic50Values.size(),
                .droppedRows = records.size() - ic50Values.size(),
            },
        .statistics =
            BioactivityStatistics{
                .ic50Um =
                    BioactivityStatistic{
                        .min = *std::min_element(ic50Values.begin(), ic50Values.end()),
                        .median = computeMedian(ic50Values),
                        .max = *std::max_element(ic50Values.begin(), ic50Values.end()),
                    },
                .pIC50 =
                    BioactivityStatistic{
                        .min = *std::min_element(pic50Values.begin(), pic50Values.end()),
                        .median = computeMedian(pic50Values),
                        .max = *std::max_element(pic50Values.begin(), pic50Values.end()),
                    },
            },
        .analysis =
            BioactivitySummary{
                .transform = "pIC50 = -log10(IC50_uM)",
                .interpretation = "Lower IC50 values map to higher pIC50 values, so potency "
                                  "increases as the curve rises.",
                .observedIc50DomainUm = {*std::min_element(ic50Values.begin(), ic50Values.end()),
                                         *std::max_element(ic50Values.begin(), ic50Values.end())},
                .strongestRetainedMeasurement = buildMeasurement(strongestRow, headerIndex),
                .weakestRetainedMeasurement = buildMeasurement(weakestRow, headerIndex),
            },
    };
}

void writeBioactivityFilteredCsv(const BioactivityAnalysisResult& result,
                                 const std::filesystem::path& outputPath)
{
    writeCsvTable(result.headers, result.filteredRows, outputPath, "bioactivity CSV output path");
}

PosteriorBioactivityAnalysisResult
buildPosteriorBioactivityAnalysis(const std::filesystem::path& csvPath,
                                  const double priorAlpha,
                                  const double priorBeta,
                                  const double credibleIntervalMass)
{
    if (!(priorAlpha > 0.0) || !(priorBeta > 0.0)) {
        throw BioactivityAnalysisError("Posterior prior parameters must be positive");
    }
    if (!(credibleIntervalMass > 0.0 && credibleIntervalMass < 1.0)) {
        throw BioactivityAnalysisError("Credible interval mass must be within (0, 1)");
    }

    BinaryBioactivityContext context = loadBinaryBioactivityContext(csvPath);
    auto& retainedRows = context.retainedRows;

    std::stable_sort(
        retainedRows.begin(), retainedRows.end(), [&](const auto& left, const auto& right) {
            const std::string_view leftActivity = left.at(context.activityIndex);
            const std::string_view rightActivity = right.at(context.activityIndex);
            if (leftActivity != rightActivity) {
                return leftActivity < rightActivity;
            }
            const long long leftBioAssayAid =
                parseRequiredLong(left, context.headerIndex, "BioAssay_AID");
            const long long rightBioAssayAid =
                parseRequiredLong(right, context.headerIndex, "BioAssay_AID");
            if (leftBioAssayAid != rightBioAssayAid) {
                return leftBioAssayAid < rightBioAssayAid;
            }
            return parseRequiredLong(left, context.headerIndex, "Bioactivity_ID") <
                   parseRequiredLong(right, context.headerIndex, "Bioactivity_ID");
        });

    const double posteriorAlpha = priorAlpha + static_cast<double>(context.activeRows);
    const double posteriorBeta = priorBeta + static_cast<double>(context.inactiveRows);
    const boost::math::beta_distribution<double> posteriorDistribution(posteriorAlpha,
                                                                       posteriorBeta);
    const double tailProbability = (1.0 - credibleIntervalMass) / 2.0;
    const std::optional<double> posteriorMode =
        posteriorAlpha > 1.0 && posteriorBeta > 1.0
            ? std::optional<double>((posteriorAlpha - 1.0) / (posteriorAlpha + posteriorBeta - 2.0))
            : std::nullopt;

    std::vector<PosteriorBioactivityRepresentativeRow> representativeRows;
    for (const std::size_t position : representativeRowPositions(retainedRows.size())) {
        const auto& row = retainedRows[position];
        representativeRows.push_back(PosteriorBioactivityRepresentativeRow{
            .bioactivityId = parseRequiredLong(row, context.headerIndex, "Bioactivity_ID"),
            .bioAssayAid = parseRequiredLong(row, context.headerIndex, "BioAssay_AID"),
            .activity = row.at(context.activityIndex),
            .activityType =
                normalizeOptionalLabel(valueAtOrEmpty(row, context.activityTypeIndex), "Unknown"),
            .targetName =
                normalizeOptionalLabel(valueAtOrEmpty(row, context.targetNameIndex), "Unknown"),
            .bioAssayName =
                normalizeOptionalLabel(valueAtOrEmpty(row, context.bioAssayNameIndex), "Unknown"),
        });
    }

    return PosteriorBioactivityAnalysisResult{
        .sourceFile = context.sourceFile,
        .headers = std::move(context.headers),
        .rows = std::move(retainedRows),
        .rowCounts =
            PosteriorBioactivityRowCounts{
                .totalRows = context.totalRows,
                .activeRows = context.activeRows,
                .inactiveRows = context.inactiveRows,
                .unspecifiedRows = context.unspecifiedRows,
                .otherActivityRows = context.otherActivityRows,
                .retainedBinaryRows = context.activeRows + context.inactiveRows,
                .droppedNonBinaryRows =
                    context.totalRows - (context.activeRows + context.inactiveRows),
                .retainedUniqueBioassays = context.retainedBioassayIds.size(),
            },
        .posterior =
            PosteriorBioactivityPosteriorSection{
                .prior =
                    PosteriorBioactivityPrior{
                        .family = "beta",
                        .alpha = priorAlpha,
                        .beta = priorBeta,
                    },
                .likelihood =
                    PosteriorBioactivityLikelihood{
                        .family = "binomial",
                        .successLabel = "Active",
                        .failureLabel = "Inactive",
                    },
                .posteriorDistribution =
                    PosteriorBioactivityDistribution{
                        .family = "beta",
                        .alpha = posteriorAlpha,
                        .beta = posteriorBeta,
                    },
                .summary =
                    PosteriorBioactivitySummaryStatistics{
                        .posteriorMeanProbabilityActive =
                            posteriorAlpha / (posteriorAlpha + posteriorBeta),
                        .posteriorMedianProbabilityActive = quantile(posteriorDistribution, 0.5),
                        .posteriorModeProbabilityActive = posteriorMode,
                        .posteriorVariance = (posteriorAlpha * posteriorBeta) /
                                             (std::pow(posteriorAlpha + posteriorBeta, 2.0) *
                                              (posteriorAlpha + posteriorBeta + 1.0)),
                        .credibleIntervalProbabilityActive =
                            PosteriorBioactivityCredibleInterval{
                                .mass = credibleIntervalMass,
                                .lower = quantile(posteriorDistribution, tailProbability),
                                .upper = quantile(posteriorDistribution, 1.0 - tailProbability),
                            },
                        .posteriorProbabilityActiveGt0_5 = 1.0 - cdf(posteriorDistribution, 0.5),
                        .observedActiveFractionInRetainedRows =
                            static_cast<double>(context.activeRows) /
                            static_cast<double>(context.activeRows + context.inactiveRows),
                    },
            },
        .analysis =
            PosteriorBioactivityAnalysis{
                .targetQuantity = "P(Active | CID=4)",
                .model = "Beta-Binomial conjugate update",
                .updateEquations =
                    PosteriorBioactivityUpdateEquations{
                        .posteriorAlpha = "alphaPost = alphaPrior + activeCount",
                        .posteriorBeta = "betaPost = betaPrior + inactiveCount",
                        .posteriorMean = "E[p | data] = alphaPost / (alphaPost + betaPost)",
                    },
                .binaryEvidenceDefinition =
                    PosteriorBioactivityBinaryEvidenceDefinition{
                        .retainedLabels = {"Active", "Inactive"},
                        .excludedLabels = {"Unspecified"},
                        .interpretation = "Unspecified rows are excluded from the binary posterior "
                                          "update and reported only in row counts.",
                    },
                .representativeRows = std::move(representativeRows),
                .notes =
                    {
                        "This posterior is an aggregate CID 4 activity probability across retained "
                        "binary bioassay outcomes.",
                        "The update uses a Beta(1,1) prior and treats Active/Inactive outcomes as "
                        "exchangeable Bernoulli evidence.",
                        "Rows labeled Unspecified are kept out of the posterior update so they do "
                        "not contribute artificial failures.",
                    },
            },
    };
}

void writePosteriorBioactivityCsv(const PosteriorBioactivityAnalysisResult& result,
                                  const std::filesystem::path& outputPath)
{
    writeCsvTable(result.headers, result.rows, outputPath, "posterior bioactivity CSV output path");
}

BinomialActivityDistributionAnalysisResult
buildBinomialActivityDistributionAnalysis(const std::filesystem::path& csvPath)
{
    BinaryBioactivityContext context = loadBinaryBioactivityContext(csvPath);

    std::map<long long, AssayActivityCollapseRow> assays;
    for (const auto& row : context.retainedRows) {
        const long long bioAssayAid = parseRequiredLong(row, context.headerIndex, "BioAssay_AID");
        auto [iterator, inserted] =
            assays.try_emplace(bioAssayAid,
                               AssayActivityCollapseRow{
                                   .bioAssayAid = bioAssayAid,
                                   .assayActivity = "Inactive",
                                   .retainedBinaryRows = 0U,
                                   .activeRows = 0U,
                                   .inactiveRows = 0U,
                                   .mixedEvidence = false,
                                   .activityType = normalizeOptionalLabel(
                                       valueAtOrEmpty(row, context.activityTypeIndex), "Unknown"),
                                   .targetName = normalizeOptionalLabel(
                                       valueAtOrEmpty(row, context.targetNameIndex), "Unknown"),
                                   .bioAssayName = normalizeOptionalLabel(
                                       valueAtOrEmpty(row, context.bioAssayNameIndex), "Unknown"),
                               });

        auto& assay = iterator->second;
        assay.retainedBinaryRows += 1U;
        if (row.at(context.activityIndex) == "Active") {
            assay.activeRows += 1U;
            assay.assayActivity = "Active";
        }
        else {
            assay.inactiveRows += 1U;
        }
        assay.mixedEvidence = assay.activeRows > 0U && assay.inactiveRows > 0U;

        if (inserted) {
            assay.activityType =
                normalizeOptionalLabel(valueAtOrEmpty(row, context.activityTypeIndex), "Unknown");
            assay.targetName =
                normalizeOptionalLabel(valueAtOrEmpty(row, context.targetNameIndex), "Unknown");
            assay.bioAssayName =
                normalizeOptionalLabel(valueAtOrEmpty(row, context.bioAssayNameIndex), "Unknown");
        }
    }

    std::vector<AssayActivityCollapseRow> assayRows;
    assayRows.reserve(assays.size());
    for (const auto& [_, assay] : assays) {
        assayRows.push_back(assay);
    }

    std::stable_sort(assayRows.begin(), assayRows.end(), [](const auto& left, const auto& right) {
        if (left.assayActivity != right.assayActivity) {
            return left.assayActivity < right.assayActivity;
        }
        return left.bioAssayAid < right.bioAssayAid;
    });

    const std::size_t assayTrials = assayRows.size();
    const std::size_t activeAssayTrials =
        std::count_if(assayRows.begin(), assayRows.end(), [](const auto& assay) {
            return assay.assayActivity == "Active";
        });
    const std::size_t inactiveAssayTrials = assayTrials - activeAssayTrials;
    const std::size_t mixedEvidenceAssayTrials = std::count_if(
        assayRows.begin(), assayRows.end(), [](const auto& assay) { return assay.mixedEvidence; });
    const double successProbability =
        static_cast<double>(activeAssayTrials) / static_cast<double>(assayTrials);
    const boost::math::binomial_distribution<double> distribution(
        static_cast<unsigned>(assayTrials), successProbability);

    const std::vector<std::string> headers = {
        "k_active",
        "probability",
        "cumulative_probability_leq_k",
        "cumulative_probability_geq_k",
    };
    std::vector<std::vector<std::string>> rows;
    rows.reserve(assayTrials + 1U);
    double pmfProbabilitySum = 0.0;
    for (std::size_t k = 0; k <= assayTrials; ++k) {
        const double probability = pdf(distribution, static_cast<double>(k));
        const double cumulativeLeq = cdf(distribution, static_cast<double>(k));
        const double cumulativeGeq =
            k == 0U ? 1.0 : 1.0 - cdf(distribution, static_cast<double>(k - 1U));
        pmfProbabilitySum += probability;
        rows.push_back({std::to_string(k),
                        formatDouble(probability),
                        formatDouble(cumulativeLeq),
                        formatDouble(cumulativeGeq)});
    }

    const double observedPmf = pdf(distribution, static_cast<double>(activeAssayTrials));
    const double observedCumulativeLeq = cdf(distribution, static_cast<double>(activeAssayTrials));
    const double observedCumulativeGeq =
        activeAssayTrials == 0U
            ? 1.0
            : 1.0 - cdf(distribution, static_cast<double>(activeAssayTrials - 1U));

    std::vector<BinomialActivityRepresentativeAssay> representativeAssays;
    for (const std::size_t position : representativeRowPositions(assayRows.size())) {
        const auto& assay = assayRows[position];
        representativeAssays.push_back(BinomialActivityRepresentativeAssay{
            .bioAssayAid = assay.bioAssayAid,
            .assayActivity = assay.assayActivity,
            .retainedBinaryRows = assay.retainedBinaryRows,
            .activeRows = assay.activeRows,
            .inactiveRows = assay.inactiveRows,
            .mixedEvidence = assay.mixedEvidence,
            .activityType = assay.activityType,
            .targetName = assay.targetName,
            .bioAssayName = assay.bioAssayName,
        });
    }

    return BinomialActivityDistributionAnalysisResult{
        .sourceFile = context.sourceFile,
        .headers = headers,
        .rows = std::move(rows),
        .rowCounts =
            BinomialActivityRowCounts{
                .totalRows = context.totalRows,
                .activeRows = context.activeRows,
                .inactiveRows = context.inactiveRows,
                .unspecifiedRows = context.unspecifiedRows,
                .otherActivityRows = context.otherActivityRows,
                .retainedBinaryRows = context.activeRows + context.inactiveRows,
                .droppedNonBinaryRows =
                    context.totalRows - (context.activeRows + context.inactiveRows),
                .retainedUniqueBioassays = context.retainedBioassayIds.size(),
                .assayTrials = assayTrials,
                .activeAssayTrials = activeAssayTrials,
                .inactiveAssayTrials = inactiveAssayTrials,
                .mixedEvidenceAssayTrials = mixedEvidenceAssayTrials,
                .unanimousActiveAssayTrials = activeAssayTrials - mixedEvidenceAssayTrials,
                .unanimousInactiveAssayTrials = inactiveAssayTrials,
            },
        .binomial =
            BinomialActivityDistributionSection{
                .trialDefinition =
                    BinomialActivityTrialDefinition{
                        .unit = "unique_BioAssay_AID",
                        .successLabel = "Active assay",
                        .failureLabel = "Inactive assay",
                        .assayResolutionRule = "Active wins if any retained row for the assay is "
                                               "Active; otherwise the assay is Inactive.",
                    },
                .parameters =
                    BinomialActivityParameters{
                        .nAssays = assayTrials,
                        .observedActiveAssays = activeAssayTrials,
                        .successProbabilityActiveAssay = successProbability,
                    },
                .summary =
                    BinomialActivitySummaryStatistics{
                        .pmfAtObservedActiveAssayCount = observedPmf,
                        .cumulativeProbabilityLeqObservedActiveAssayCount = observedCumulativeLeq,
                        .cumulativeProbabilityGeqObservedActiveAssayCount = observedCumulativeGeq,
                        .binomialMeanActiveAssays =
                            static_cast<double>(assayTrials) * successProbability,
                        .binomialVarianceActiveAssays = static_cast<double>(assayTrials) *
                                                        successProbability *
                                                        (1.0 - successProbability),
                        .pmfProbabilitySum = pmfProbabilitySum,
                    },
            },
        .analysis =
            BinomialActivityAnalysis{
                .targetQuantity = "P(K = k active assays in n assays)",
                .model = "Binomial distribution with plug-in success probability",
                .equation = "P(K = k) = C(n, k) p^k (1-p)^(n-k)",
                .parameterEstimation = "p is estimated as the observed active assay fraction "
                                       "active_assays / n_assays.",
                .representativeAssays = std::move(representativeAssays),
                .notes =
                    {
                        "The binomial model operates at the assay level rather than the raw "
                        "retained-row level.",
                        "Rows with Activity = Unspecified are excluded before assay-level "
                        "collapsing, consistent with the posterior analysis.",
                        "This is a frequentist plug-in binomial model using the observed "
                        "assay-level active fraction, not a posterior-predictive distribution.",
                    },
            },
    };
}

void writeBinomialActivityDistributionCsv(const BinomialActivityDistributionAnalysisResult& result,
                                          const std::filesystem::path& outputPath)
{
    writeCsvTable(
        result.headers, result.rows, outputPath, "binomial activity distribution CSV output path");
}

ChiSquareActivityAidTypeAnalysisResult
buildChiSquareActivityAidTypeAnalysis(const std::filesystem::path& csvPath,
                                      const double expectedCountThreshold)
{
    if (!(expectedCountThreshold > 0.0)) {
        throw BioactivityAnalysisError("Chi-square expected-count threshold must be positive");
    }

    BinaryBioactivityContext context = loadBinaryBioactivityContext(csvPath);
    if (!context.aidTypeIndex.has_value()) {
        throw BioactivityAnalysisError("Bioactivity CSV is missing required column: Aid_Type");
    }

    std::map<std::string, std::map<std::string, std::size_t>> observedCounts;
    std::set<std::string> activityLevelsSet;
    std::set<std::string> aidTypeLevelsSet;
    for (const auto& row : context.retainedRows) {
        const std::string& activity = row.at(context.activityIndex);
        const std::string aidType =
            normalizeOptionalLabel(valueAtOrEmpty(row, context.aidTypeIndex), "Unknown");
        activityLevelsSet.insert(activity);
        aidTypeLevelsSet.insert(aidType);
        observedCounts[activity][aidType] += 1U;
    }

    std::vector<std::string> activityLevels(activityLevelsSet.begin(), activityLevelsSet.end());
    std::vector<std::string> aidTypeLevels(aidTypeLevelsSet.begin(), aidTypeLevelsSet.end());

    for (const auto& activity : activityLevels) {
        for (const auto& aidType : aidTypeLevels) {
            observedCounts[activity][aidType] += 0U;
        }
    }

    const bool hasMinimumShape = activityLevels.size() >= 2U && aidTypeLevels.size() >= 2U;
    std::map<std::string, std::map<std::string, std::optional<double>>> expectedCounts;
    std::optional<double> chi2Statistic;
    std::optional<double> pValue;
    std::optional<std::size_t> degreesOfFreedom;
    std::optional<std::size_t> sparseExpectedCellCount;
    std::optional<double> sparseExpectedCellFraction;
    std::optional<std::string> reasonNotComputed;

    if (hasMinimumShape) {
        std::map<std::string, std::size_t> rowTotals;
        std::map<std::string, std::size_t> columnTotals;
        std::size_t grandTotal = 0U;
        for (const auto& activity : activityLevels) {
            const auto total =
                std::accumulate(aidTypeLevels.begin(),
                                aidTypeLevels.end(),
                                std::size_t{0U},
                                [&](const std::size_t sum, const std::string& aidType) {
                                    return sum + observedCounts.at(activity).at(aidType);
                                });
            rowTotals.emplace(activity, total);
            grandTotal += total;
        }
        for (const auto& aidType : aidTypeLevels) {
            const auto total =
                std::accumulate(activityLevels.begin(),
                                activityLevels.end(),
                                std::size_t{0U},
                                [&](const std::size_t sum, const std::string& activity) {
                                    return sum + observedCounts.at(activity).at(aidType);
                                });
            columnTotals.emplace(aidType, total);
        }

        double chiSquareValue = 0.0;
        std::size_t sparseCount = 0U;
        for (const auto& activity : activityLevels) {
            for (const auto& aidType : aidTypeLevels) {
                const double expected = (static_cast<double>(rowTotals.at(activity)) *
                                         static_cast<double>(columnTotals.at(aidType))) /
                                        static_cast<double>(grandTotal);
                expectedCounts[activity][aidType] = expected;
                if (expected < expectedCountThreshold) {
                    ++sparseCount;
                }
                if (expected > 0.0) {
                    const double observed =
                        static_cast<double>(observedCounts.at(activity).at(aidType));
                    const double residual = observed - expected;
                    chiSquareValue += (residual * residual) / expected;
                }
            }
        }

        const std::size_t degrees = (activityLevels.size() - 1U) * (aidTypeLevels.size() - 1U);
        const boost::math::chi_squared_distribution<double> distribution(
            static_cast<double>(degrees));
        chi2Statistic = chiSquareValue;
        pValue = 1.0 - cdf(distribution, chiSquareValue);
        degreesOfFreedom = degrees;
        sparseExpectedCellCount = sparseCount;
        sparseExpectedCellFraction =
            static_cast<double>(sparseCount) /
            static_cast<double>(activityLevels.size() * aidTypeLevels.size());
    }
    else {
        reasonNotComputed = "Chi-square test requires at least two observed Activity levels and "
                            "two Aid_Type levels after binary filtering.";
        for (const auto& activity : activityLevels) {
            for (const auto& aidType : aidTypeLevels) {
                expectedCounts[activity][aidType] = std::nullopt;
            }
        }
    }

    const std::vector<std::string> headers = {
        "Activity",
        "Aid_Type",
        "observed_count",
        "expected_count",
    };
    std::vector<std::vector<std::string>> rows;
    rows.reserve(activityLevels.size() * aidTypeLevels.size());
    for (const auto& activity : activityLevels) {
        for (const auto& aidType : aidTypeLevels) {
            rows.push_back({activity,
                            aidType,
                            std::to_string(observedCounts.at(activity).at(aidType)),
                            expectedCounts.at(activity).at(aidType).has_value()
                                ? formatDouble(*expectedCounts.at(activity).at(aidType))
                                : std::string()});
        }
    }

    std::vector<ChiSquareRepresentativeCell> representativeCells;
    representativeCells.reserve(activityLevels.size() * aidTypeLevels.size());
    for (const auto& activity : activityLevels) {
        for (const auto& aidType : aidTypeLevels) {
            representativeCells.push_back(ChiSquareRepresentativeCell{
                .activity = activity,
                .aidType = aidType,
                .observedCount = observedCounts.at(activity).at(aidType),
                .expectedCount = expectedCounts.at(activity).at(aidType),
            });
        }
    }
    std::stable_sort(
        representativeCells.begin(),
        representativeCells.end(),
        [](const ChiSquareRepresentativeCell& left, const ChiSquareRepresentativeCell& right) {
            if (left.observedCount != right.observedCount) {
                return left.observedCount > right.observedCount;
            }
            if (left.activity != right.activity) {
                return left.activity < right.activity;
            }
            return left.aidType < right.aidType;
        });
    if (representativeCells.size() > 3U) {
        representativeCells.resize(3U);
    }

    return ChiSquareActivityAidTypeAnalysisResult{
        .sourceFile = context.sourceFile,
        .headers = headers,
        .rows = std::move(rows),
        .rowCounts =
            ChiSquareActivityAidTypeRowCounts{
                .totalRows = context.totalRows,
                .activeRows = context.activeRows,
                .inactiveRows = context.inactiveRows,
                .unspecifiedRows = context.unspecifiedRows,
                .otherActivityRows = context.otherActivityRows,
                .retainedBinaryRows = context.activeRows + context.inactiveRows,
                .droppedNonBinaryRows =
                    context.totalRows - (context.activeRows + context.inactiveRows),
                .retainedUniqueBioassays = context.retainedBioassayIds.size(),
                .retainedRowsWithAidType = context.retainedRows.size(),
                .activityLevelsTested = activityLevels.size(),
                .aidTypeLevelsTested = aidTypeLevels.size(),
            },
        .contingencyTable =
            ChiSquareContingencyTable{
                .activityLevels = std::move(activityLevels),
                .aidTypeLevels = std::move(aidTypeLevels),
                .observedCounts = std::move(observedCounts),
                .expectedCounts = std::move(expectedCounts),
            },
        .chiSquareTest =
            ChiSquareTestMetrics{
                .variables =
                    ChiSquareVariables{
                        .row = "Activity",
                        .column = "Aid_Type",
                    },
                .nullHypothesis = "Activity and Aid_Type are statistically independent within the "
                                  "retained binary bioactivity rows.",
                .alternativeHypothesis = "Activity and Aid_Type are statistically associated "
                                         "within the retained binary bioactivity rows.",
                .computed = hasMinimumShape,
                .reasonNotComputed = std::move(reasonNotComputed),
                .chi2Statistic = chi2Statistic,
                .pValue = pValue,
                .degreesOfFreedom = degreesOfFreedom,
                .minimumExpectedCountThreshold = expectedCountThreshold,
                .sparseExpectedCellCount = sparseExpectedCellCount,
                .sparseExpectedCellFraction = sparseExpectedCellFraction,
            },
        .analysis =
            ChiSquareActivityAidTypeAnalysis{
                .targetQuantity = "Activity independent of Aid_Type",
                .model = "Pearson chi-square test of independence",
                .binaryEvidenceDefinition =
                    ChiSquareBinaryEvidenceDefinition{
                        .retainedLabels = {"Active", "Inactive"},
                        .excludedLabels = {"Unspecified"},
                        .interpretation = "The chi-square table is built from the same binary "
                                          "Activity evidence used by the posterior analysis.",
                    },
                .representativeCells = std::move(representativeCells),
                .notes =
                    {
                        "Rows with Activity = Unspecified and other non-binary Activity labels are "
                        "excluded before the contingency table is built.",
                        "Aid_Type values are used as observed in the CSV after trimming whitespace "
                        "and filling blanks with Unknown.",
                        "If fewer than two observed Activity levels or fewer than two Aid_Type "
                        "levels remain after filtering, the summary records that the chi-square "
                        "test is not statistically identifiable on this dataset slice.",
                    },
            },
    };
}

void writeChiSquareActivityAidTypeCsv(const ChiSquareActivityAidTypeAnalysisResult& result,
                                      const std::filesystem::path& outputPath)
{
    writeCsvTable(
        result.headers, result.rows, outputPath, "chi-square activity Aid_Type CSV output path");
}

HillDoseResponseAnalysisResult buildHillDoseResponseAnalysis(const std::filesystem::path& csvPath,
                                                             const double hillCoefficient)
{
    if (hillCoefficient <= 0.0) {
        throw BioactivityAnalysisError("Hill coefficient must be positive");
    }

    std::ifstream input(csvPath);
    if (!input) {
        throw BioactivityAnalysisError("Could not open bioactivity input file: " +
                                       csvPath.string());
    }

    auto records = parseCsvRecords(input);
    if (records.empty()) {
        throw BioactivityAnalysisError("Bioactivity CSV is empty: " + csvPath.string());
    }

    auto headers = records.front();
    if (!headers.empty()) {
        headers.front() = stripUtf8Bom(headers.front());
    }
    records.erase(records.begin());

    std::map<std::string, std::size_t> headerIndex;
    for (std::size_t index = 0; index < headers.size(); ++index) {
        headerIndex.emplace(headers[index], index);
    }

    for (const std::string_view requiredHeader :
         {"Bioactivity_ID", "BioAssay_AID", "Activity_Type", "Activity_Value"}) {
        if (!headerIndex.contains(std::string(requiredHeader))) {
            throw BioactivityAnalysisError("Bioactivity CSV is missing required column: " +
                                           std::string(requiredHeader));
        }
    }

    const std::size_t baseHeaderCount = headers.size();
    const std::size_t activityTypeIndex = headerIndex.at("Activity_Type");
    const std::size_t activityValueIndex = headerIndex.at("Activity_Value");
    const std::optional<std::size_t> targetNameIndex =
        optionalColumnIndex(headerIndex, "Target_Name");
    const std::optional<std::size_t> hasDoseResponseCurveIndex =
        optionalColumnIndex(headerIndex, "Has_Dose_Response_Curve");

    headers.push_back("hill_coefficient_n");
    headers.push_back("inferred_K_activity_value");
    headers.push_back("midpoint_concentration");
    headers.push_back("midpoint_response");
    headers.push_back("midpoint_first_derivative");
    headers.push_back("auc_trapezoid_reference_curve");
    headers.push_back("log10_midpoint_concentration");
    headers.push_back("linear_inflection_concentration");
    headers.push_back("linear_inflection_response");
    headers.push_back("fit_status");
    headers.push_back("analysis_mode");

    std::map<std::string, std::size_t> augmentedHeaderIndex;
    for (std::size_t index = 0; index < headers.size(); ++index) {
        augmentedHeaderIndex.emplace(headers[index], index);
    }

    std::size_t numericValueCount = 0;
    std::size_t positiveValueCount = 0;
    std::size_t rowsFlaggedHasDoseResponseCurve = 0;
    std::size_t retainedRowsFlaggedHasDoseResponseCurve = 0;
    std::set<long long> retainedBioassayIds;
    std::map<std::string, std::size_t> activityTypeCounts;
    std::vector<double> inferredKValues;
    std::vector<double> midpointFirstDerivatives;
    std::vector<double> aucTrapezoidReferenceCurves;
    std::vector<std::vector<std::string>> retainedRows;

    const auto inflectionScale = hillLinearInflectionScale(hillCoefficient);

    for (auto& row : records) {
        if (row.size() < baseHeaderCount) {
            row.resize(baseHeaderCount);
        }

        const auto numericActivityValue = parseDouble(row[activityValueIndex]);
        if (numericActivityValue.has_value()) {
            ++numericValueCount;
        }

        const bool hasPositiveActivityValue =
            numericActivityValue.has_value() && *numericActivityValue > 0.0;
        if (hasPositiveActivityValue) {
            ++positiveValueCount;
        }

        const auto hasDoseResponseCurveValue =
            parseDouble(valueAtOrEmpty(row, hasDoseResponseCurveIndex));
        const bool isFlaggedHasDoseResponseCurve = hasDoseResponseCurveValue.has_value() &&
                                                   std::llround(*hasDoseResponseCurveValue) == 1LL;
        if (isFlaggedHasDoseResponseCurve) {
            ++rowsFlaggedHasDoseResponseCurve;
        }

        if (!hasPositiveActivityValue) {
            continue;
        }

        row.resize(headers.size());
        row[activityValueIndex] = formatDouble(*numericActivityValue);

        const double inferredK = *numericActivityValue;
        const double midpointConcentration = inferredK;
        const double midpointResponse = 0.5;
        const double midpointFirstDerivative =
            hillResponseFirstDerivative(midpointConcentration, inferredK, hillCoefficient);
        const double aucTrapezoidReferenceCurve =
            computeHillReferenceAucTrapezoid(inferredK, hillCoefficient);
        const double log10MidpointConcentration = std::log10(midpointConcentration);

        row[augmentedHeaderIndex.at("hill_coefficient_n")] = formatDouble(hillCoefficient);
        row[augmentedHeaderIndex.at("inferred_K_activity_value")] = formatDouble(inferredK);
        row[augmentedHeaderIndex.at("midpoint_concentration")] =
            formatDouble(midpointConcentration);
        row[augmentedHeaderIndex.at("midpoint_response")] = formatDouble(midpointResponse);
        row[augmentedHeaderIndex.at("midpoint_first_derivative")] =
            formatDouble(midpointFirstDerivative);
        row[augmentedHeaderIndex.at("auc_trapezoid_reference_curve")] =
            formatDouble(aucTrapezoidReferenceCurve);
        row[augmentedHeaderIndex.at("log10_midpoint_concentration")] =
            formatDouble(log10MidpointConcentration);
        row[augmentedHeaderIndex.at("linear_inflection_concentration")] = "";
        row[augmentedHeaderIndex.at("linear_inflection_response")] = "";

        if (inflectionScale.has_value()) {
            const double linearInflectionConcentration = inferredK * *inflectionScale;
            const double linearInflectionResponse =
                hillResponse(linearInflectionConcentration, inferredK, hillCoefficient);
            row[augmentedHeaderIndex.at("linear_inflection_concentration")] =
                formatDouble(linearInflectionConcentration);
            row[augmentedHeaderIndex.at("linear_inflection_response")] =
                formatDouble(linearInflectionResponse);
        }

        row[augmentedHeaderIndex.at("fit_status")] = "reference_curve_inferred_from_activity_value";
        row[augmentedHeaderIndex.at("analysis_mode")] = "reference_curve";

        const std::string activityTypeLabel = [&]() {
            const std::string value = trimWhitespace(row[activityTypeIndex]);
            return value.empty() ? std::string("Unknown") : value;
        }();
        ++activityTypeCounts[activityTypeLabel];

        if (isFlaggedHasDoseResponseCurve) {
            ++retainedRowsFlaggedHasDoseResponseCurve;
        }

        retainedBioassayIds.insert(parseRequiredLong(row, headerIndex, "BioAssay_AID"));
        inferredKValues.push_back(inferredK);
        midpointFirstDerivatives.push_back(midpointFirstDerivative);
        aucTrapezoidReferenceCurves.push_back(aucTrapezoidReferenceCurve);
        retainedRows.push_back(std::move(row));
    }

    if (retainedRows.empty()) {
        throw BioactivityAnalysisError("No positive numeric Activity_Value rows were found in " +
                                       csvPath.filename().string());
    }

    std::stable_sort(
        retainedRows.begin(), retainedRows.end(), [&](const auto& left, const auto& right) {
            const double leftK =
                std::stod(left.at(augmentedHeaderIndex.at("inferred_K_activity_value")));
            const double rightK =
                std::stod(right.at(augmentedHeaderIndex.at("inferred_K_activity_value")));
            if (std::abs(leftK - rightK) > 1.0e-12) {
                return leftK < rightK;
            }

            return parseRequiredLong(left, headerIndex, "BioAssay_AID") <
                   parseRequiredLong(right, headerIndex, "BioAssay_AID");
        });

    std::vector<HillDoseResponseRepresentativeRow> representativeRows;
    std::set<std::size_t> representativePositions{
        0U, retainedRows.size() / 2U, retainedRows.size() - 1U};
    representativeRows.reserve(representativePositions.size());
    for (const std::size_t position : representativePositions) {
        const auto& row = retainedRows[position];
        const std::string targetName = trimWhitespace(valueAtOrEmpty(row, targetNameIndex));
        representativeRows.push_back(HillDoseResponseRepresentativeRow{
            .bioactivityId = parseRequiredLong(row, headerIndex, "Bioactivity_ID"),
            .bioAssayAid = parseRequiredLong(row, headerIndex, "BioAssay_AID"),
            .activityType =
                [&]() {
                    const std::string value = trimWhitespace(row.at(activityTypeIndex));
                    return value.empty() ? std::string("Unknown") : value;
                }(),
            .targetName = targetName.empty() ? std::string("Unknown") : targetName,
            .activityValue = std::stod(row.at(activityValueIndex)),
            .inferredKActivityValue =
                std::stod(row.at(augmentedHeaderIndex.at("inferred_K_activity_value"))),
            .aucTrapezoidReferenceCurve =
                std::stod(row.at(augmentedHeaderIndex.at("auc_trapezoid_reference_curve"))),
            .log10MidpointConcentration =
                std::stod(row.at(augmentedHeaderIndex.at("log10_midpoint_concentration"))),
        });
    }

    std::vector<HillDoseResponseActivityTypeCount> activityTypeCountRows;
    activityTypeCountRows.reserve(activityTypeCounts.size());
    for (const auto& [activityType, count] : activityTypeCounts) {
        activityTypeCountRows.push_back(HillDoseResponseActivityTypeCount{
            .activityType = activityType,
            .count = count,
        });
    }
    std::stable_sort(activityTypeCountRows.begin(),
                     activityTypeCountRows.end(),
                     [](const auto& left, const auto& right) {
                         if (left.count != right.count) {
                             return left.count > right.count;
                         }
                         return left.activityType < right.activityType;
                     });

    std::optional<HillDoseResponseLinearInflectionSummary> linearInflectionSummary;
    if (inflectionScale.has_value()) {
        linearInflectionSummary = HillDoseResponseLinearInflectionSummary{
            .formula = "c* = K * ((n - 1)/(n + 1))^(1/n)",
            .responseFormula = "f(c*) = (n - 1)/(2n)",
            .relativeToK = *inflectionScale,
            .normalizedResponse = (hillCoefficient - 1.0) / (2.0 * hillCoefficient),
        };
    }

    return HillDoseResponseAnalysisResult{
        .sourceFile = csvPath.filename().string(),
        .headers = std::move(headers),
        .rows = std::move(retainedRows),
        .rowCounts =
            HillDoseResponseRowCounts{
                .totalRows = records.size(),
                .rowsWithNumericActivityValue = numericValueCount,
                .rowsWithPositiveActivityValue = positiveValueCount,
                .rowsFlaggedHasDoseResponseCurve = rowsFlaggedHasDoseResponseCurve,
                .retainedRows = inferredKValues.size(),
                .retainedRowsFlaggedHasDoseResponseCurve = retainedRowsFlaggedHasDoseResponseCurve,
                .retainedUniqueBioassays = retainedBioassayIds.size(),
            },
        .statistics =
            HillDoseResponseStatistics{
                .activityValueAsInferredK =
                    HillDoseResponseStatistic{
                        .min = *std::min_element(inferredKValues.begin(), inferredKValues.end()),
                        .median = computeMedian(inferredKValues),
                        .max = *std::max_element(inferredKValues.begin(), inferredKValues.end()),
                    },
                .midpointFirstDerivative =
                    HillDoseResponseStatistic{
                        .min = *std::min_element(midpointFirstDerivatives.begin(),
                                                 midpointFirstDerivatives.end()),
                        .median = computeMedian(midpointFirstDerivatives),
                        .max = *std::max_element(midpointFirstDerivatives.begin(),
                                                 midpointFirstDerivatives.end()),
                    },
                .aucTrapezoidReferenceCurve =
                    HillDoseResponseStatistic{
                        .min = *std::min_element(aucTrapezoidReferenceCurves.begin(),
                                                 aucTrapezoidReferenceCurves.end()),
                        .median = computeMedian(aucTrapezoidReferenceCurves),
                        .max = *std::max_element(aucTrapezoidReferenceCurves.begin(),
                                                 aucTrapezoidReferenceCurves.end()),
                    },
            },
        .activityTypeCounts = std::move(activityTypeCountRows),
        .analysis =
            HillDoseResponseSummary{
                .model = "normalized Hill equation",
                .equation = "f(c) = c^n / (K^n + c^n)",
                .firstDerivative = "f'(c) = n K^n c^(n-1) / (K^n + c^n)^2",
                .secondDerivative =
                    "f''(c) = n K^n c^(n-2) * ((n - 1)K^n - (n + 1)c^n) / (K^n + c^n)^3",
                .referenceHillCoefficientN = hillCoefficient,
                .parameterInterpretation =
                    "Activity_Value is treated as an inferred K parameter because this dataset "
                    "provides potency-style summary values rather than raw concentration-response "
                    "observations for CID 4.",
                .midpointInLogConcentrationSpace =
                    HillDoseResponseMidpointSummary{
                        .condition = "c = K",
                        .response = 0.5,
                        .interpretation =
                            "The Hill curve is centered at c = K in log-concentration space.",
                    },
                .aucTrapezoidReferenceCurve =
                    HillDoseResponseAucSummary{
                        .integrationMethod = "trapezoidal_rule",
                        .curveBasis = "reference_curve_inferred_from_activity_value",
                        .concentrationBoundsDefinition =
                            "[" + formatCompactDouble(kHillAucLowerBoundScale) + " * K, " +
                            formatCompactDouble(kHillAucUpperBoundScale) + " * K]",
                        .gridSize = kHillAucGridSize,
                        .concentrationUnits = "same units as Activity_Value",
                        .interpretation =
                            "AUC is approximated numerically over an inferred Hill reference "
                            "curve rather than over raw experimental dose-response points.",
                    },
                .linearConcentrationInflection = linearInflectionSummary,
                .fitStatus = "reference_curve_inferred_from_activity_value",
                .representativeRows = std::move(representativeRows),
                .notes =
                    {
                        "No nonlinear dose-response fitting was performed because the CSV does not "
                        "contain raw per-concentration response series for CID 4.",
                        "Rows with positive numeric Activity_Value are modeled as reference Hill "
                        "curves using Activity_Value as the inferred half-maximal scale K.",
                        "The trapezoidal-rule AUC is computed on those inferred reference curves "
                        "across a concentration grid scaled relative to each row's inferred K "
                        "value.",
                    },
            },
    };
}

void writeHillDoseResponseCsv(const HillDoseResponseAnalysisResult& result,
                              const std::filesystem::path& outputPath)
{
    writeCsvTable(result.headers, result.rows, outputPath, "Hill dose-response CSV output path");
}

void writeHillDoseResponsePlotSvg(const HillDoseResponseAnalysisResult& result,
                                  const std::filesystem::path& outputPath)
{
    if (result.analysis.representativeRows.empty()) {
        throw BioactivityAnalysisError("Hill plot requires at least one representative row");
    }

    std::ofstream output(outputPath);
    if (!output) {
        throw BioactivityAnalysisError("Could not open Hill plot output path: " +
                                       outputPath.string());
    }

    std::vector<double> representativeKValues;
    representativeKValues.reserve(result.analysis.representativeRows.size());
    for (const auto& row : result.analysis.representativeRows) {
        representativeKValues.push_back(row.inferredKActivityValue);
    }

    const double minK =
        *std::min_element(representativeKValues.begin(), representativeKValues.end());
    const double maxK =
        *std::max_element(representativeKValues.begin(), representativeKValues.end());
    const double minConcentration = std::max(minK / 100.0, kMinimumPositiveConcentration);
    const double maxConcentration = maxK * 100.0;
    const auto curveX = geometricSpace(minConcentration, maxConcentration, 400U);

    constexpr double width = 1280.0;
    constexpr double height = 720.0;
    constexpr double left = 100.0;
    constexpr double right = 80.0;
    constexpr double top = 70.0;
    constexpr double bottom = 90.0;
    constexpr double plotMinY = -0.02;
    constexpr double plotMaxY = 1.02;
    const double plotWidth = width - left - right;
    const double plotHeight = height - top - bottom;
    const double logMinX = std::log10(minConcentration);
    const double logMaxX = std::log10(maxConcentration);

    auto xToSvg = [&](const double xValue) {
        return left + (std::log10(xValue) - logMinX) / (logMaxX - logMinX) * plotWidth;
    };
    auto yToSvg = [&](const double yValue) {
        return top + (plotMaxY - yValue) / (plotMaxY - plotMinY) * plotHeight;
    };

    output << "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n";
    output << "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"" << width << "\" height=\""
           << height << "\" viewBox=\"0 0 " << width << ' ' << height << "\">\n";
    output << "<rect width=\"100%\" height=\"100%\" fill=\"#ffffff\"/>\n";
    output << "<rect x=\"" << left << "\" y=\"" << top << "\" width=\"" << plotWidth
           << "\" height=\"" << plotHeight << "\" fill=\"#f8fafc\" stroke=\"#cbd5e1\"/>\n";

    std::set<double> xTicks{minConcentration, maxConcentration};
    for (const auto& row : result.analysis.representativeRows) {
        xTicks.insert(row.inferredKActivityValue);
    }

    for (const double xTick : xTicks) {
        const double x = xToSvg(xTick);
        output << "<line x1=\"" << x << "\" y1=\"" << top << "\" x2=\"" << x << "\" y2=\""
               << top + plotHeight << "\" stroke=\"#cbd5e1\" stroke-dasharray=\"4 6\"/>\n";
        output << svgText(x - 22.0, top + plotHeight + 28.0, formatCompactDouble(xTick)) << '\n';
    }

    for (const double yTick : std::vector<double>{0.0, 0.25, 0.5, 0.75, 1.0}) {
        const double y = yToSvg(yTick);
        output << "<line x1=\"" << left << "\" y1=\"" << y << "\" x2=\"" << left + plotWidth
               << "\" y2=\"" << y << "\" stroke=\"#cbd5e1\" stroke-dasharray=\"4 6\"/>\n";
        output << svgText(40.0, y + 5.0, formatCompactDouble(yTick)) << '\n';
    }

    const std::vector<std::string> colors{"#1d4ed8", "#ea580c", "#059669"};
    for (std::size_t rowIndex = 0; rowIndex < result.analysis.representativeRows.size();
         ++rowIndex) {
        const auto& representativeRow = result.analysis.representativeRows[rowIndex];
        const std::string& color = colors[rowIndex % colors.size()];

        std::ostringstream polyline;
        for (std::size_t pointIndex = 0; pointIndex < curveX.size(); ++pointIndex) {
            if (pointIndex > 0) {
                polyline << ' ';
            }
            polyline << xToSvg(curveX[pointIndex]) << ','
                     << yToSvg(hillResponse(curveX[pointIndex],
                                            representativeRow.inferredKActivityValue,
                                            result.analysis.referenceHillCoefficientN));
        }

        output << "<polyline fill=\"none\" stroke=\"" << color << "\" stroke-width=\"4\" points=\""
               << polyline.str() << "\"/>\n";
        output << "<line x1=\"" << xToSvg(representativeRow.inferredKActivityValue) << "\" y1=\""
               << top << "\" x2=\"" << xToSvg(representativeRow.inferredKActivityValue)
               << "\" y2=\"" << top + plotHeight << "\" stroke=\"" << color
               << "\" stroke-dasharray=\"8 8\" stroke-width=\"2\" stroke-opacity=\"0.7\"/>\n";
    }

    output << svgText(width / 2.0 - 280.0,
                      35.0,
                      "Reference Hill Curves Inferred from Activity_Value (n = " +
                          formatCompactDouble(result.analysis.referenceHillCoefficientN) + ")",
                      "font-size=\"28\" font-weight=\"700\"")
           << '\n';
    output << svgText(width / 2.0 - 160.0,
                      height - 25.0,
                      "Concentration c (same units as Activity_Value)",
                      "font-size=\"22\" font-weight=\"600\"")
           << '\n';
    output << "<g transform=\"translate(30 " << (top + plotHeight / 2.0 + 80.0)
           << ") rotate(-90)\">\n";
    output << svgText(0.0, 0.0, "Normalized response f(c)", "font-size=\"22\" font-weight=\"600\"")
           << '\n';
    output << "</g>\n";

        const double legendX = width - 520.0;
        const double legendY = top + 16.0;
        const double legendHeight = 32.0 + (result.analysis.representativeRows.size() * 28.0);
        output << "<rect x=\"" << legendX << "\" y=\"" << legendY << "\" width=\"440\" height=\""
            << legendHeight << "\" fill=\"#ffffff\" stroke=\"#cbd5e1\"/>\n";

        for (std::size_t rowIndex = 0; rowIndex < result.analysis.representativeRows.size();
          ++rowIndex) {
         const auto& representativeRow = result.analysis.representativeRows[rowIndex];
         const std::string& color = colors[rowIndex % colors.size()];
         const double y = legendY + 24.0 + (rowIndex * 28.0);
         output << "<line x1=\"" << legendX + 20.0 << "\" y1=\"" << y << "\" x2=\""
             << legendX + 68.0 << "\" y2=\"" << y << "\" stroke=\"" << color
             << "\" stroke-width=\"4\"/>\n";
         output << svgText(legendX + 82.0,
                     y + 5.0,
                     "AID " + std::to_string(representativeRow.bioAssayAid) + " | " +
                      representativeRow.activityType + " | K=" +
                      formatCompactDouble(representativeRow.inferredKActivityValue))
             << '\n';
        }

        output << "</svg>\n";
    }


ActivityValueStatisticsAnalysisResult
buildActivityValueStatisticsAnalysis(const std::filesystem::path& csvPath,
                                     const double shapiroAlpha)
{
    if (!(shapiroAlpha > 0.0 && shapiroAlpha < 1.0)) {
        throw BioactivityAnalysisError("Shapiro alpha must be within (0, 1)");
    }

    std::ifstream input(csvPath);
    if (!input) {
        throw BioactivityAnalysisError("Could not open bioactivity input file: " +
                                       csvPath.string());
    }

    auto records = parseCsvRecords(input);
    if (records.empty()) {
        throw BioactivityAnalysisError("Bioactivity CSV is empty: " + csvPath.string());
    }

    auto headers = records.front();
    if (!headers.empty()) {
        headers.front() = stripUtf8Bom(headers.front());
    }
    records.erase(records.begin());

    std::map<std::string, std::size_t> headerIndex;
    for (std::size_t index = 0; index < headers.size(); ++index) {
        headerIndex.emplace(headers[index], index);
    }

    for (const std::string_view requiredHeader :
         {"Bioactivity_ID", "BioAssay_AID", "Activity_Type", "Activity_Value"}) {
        if (!headerIndex.contains(std::string(requiredHeader))) {
            throw BioactivityAnalysisError("Bioactivity CSV is missing required column: " +
                                           std::string(requiredHeader));
        }
    }

    const std::size_t activityTypeIndex = headerIndex.at("Activity_Type");
    const std::size_t activityValueIndex = headerIndex.at("Activity_Value");
    const std::optional<std::size_t> activityIndex = optionalColumnIndex(headerIndex, "Activity");
    const std::optional<std::size_t> aidTypeIndex = optionalColumnIndex(headerIndex, "Aid_Type");

    const std::vector<std::string> retainedHeaders{
        "Bioactivity_ID", "BioAssay_AID", "Activity", "Aid_Type", "Activity_Type", "Activity_Value"};

    std::size_t numericValueCount = 0U;
    std::size_t positiveValueCount = 0U;
    std::size_t zeroValueCount = 0U;
    std::size_t negativeValueCount = 0U;
    std::set<long long> retainedBioassayIds;
    std::vector<std::vector<std::string>> retainedRows;
    std::vector<double> retainedValues;

    for (auto& row : records) {
        if (row.size() < headers.size()) {
            row.resize(headers.size());
        }

        const auto activityValue = parseDouble(row[activityValueIndex]);
        if (activityValue.has_value()) {
            ++numericValueCount;
            if (*activityValue > 0.0) {
                ++positiveValueCount;
            }
            else if (*activityValue < 0.0) {
                ++negativeValueCount;
            }
            else {
                ++zeroValueCount;
            }
        }

        if (!activityValue.has_value() || *activityValue <= 0.0) {
            continue;
        }

        retainedBioassayIds.insert(parseRequiredLong(row, headerIndex, "BioAssay_AID"));
        retainedValues.push_back(*activityValue);
        retainedRows.push_back({row.at(headerIndex.at("Bioactivity_ID")),
                                row.at(headerIndex.at("BioAssay_AID")),
                                normalizeOptionalLabel(valueAtOrEmpty(row, activityIndex), "Unknown"),
                                normalizeOptionalLabel(valueAtOrEmpty(row, aidTypeIndex), "Unknown"),
                                normalizeOptionalLabel(row.at(activityTypeIndex), "Unknown"),
                                formatDouble(*activityValue)});
    }

    if (retainedRows.empty()) {
        throw BioactivityAnalysisError("No positive numeric Activity_Value rows were found in " +
                                       csvPath.filename().string());
    }

    std::stable_sort(retainedRows.begin(), retainedRows.end(), [](const auto& left, const auto& right) {
        const double leftValue = std::stod(left.back());
        const double rightValue = std::stod(right.back());
        if (std::abs(leftValue - rightValue) > 1.0e-12) {
            return leftValue < rightValue;
        }
        const long long leftAid = std::stoll(left[1]);
        const long long rightAid = std::stoll(right[1]);
        if (leftAid != rightAid) {
            return leftAid < rightAid;
        }
        return std::stoll(left[0]) < std::stoll(right[0]);
    });

    std::vector<double> sortedValues = retainedValues;
    std::sort(sortedValues.begin(), sortedValues.end());

    const double mean = computeMean(sortedValues);
    const double variance = computeSampleVariance(sortedValues, mean);
    const std::optional<double> skewness = computeBiasCorrectedSampleSkewness(sortedValues, mean);

    std::vector<ActivityValueRepresentativeRow> representativeRows;
    for (const std::size_t position : representativeRowPositions(retainedRows.size())) {
        const auto& row = retainedRows[position];
        representativeRows.push_back(ActivityValueRepresentativeRow{
            .bioactivityId = std::stoll(row[0]),
            .bioAssayAid = std::stoll(row[1]),
            .activity = row[2],
            .aidType = row[3],
            .activityType = row[4],
            .activityValue = std::stod(row[5]),
        });
    }

    const bool hasEnoughRowsForShapiro = sortedValues.size() >= 3U;
    const std::optional<std::string> reasonNotComputed =
        hasEnoughRowsForShapiro
            ? std::optional<std::string>(
                  "Shapiro-Wilk is not implemented in the current C++ dependency set.")
            : std::optional<std::string>(
                  "Shapiro-Wilk requires at least 3 retained observations.");
    const std::string interpretation =
        hasEnoughRowsForShapiro
            ? "Normality was not tested because Shapiro-Wilk is not implemented in the current C++ dependency set."
            : "Normality was not tested because too few positive numeric rows were retained.";

    return ActivityValueStatisticsAnalysisResult{
        .sourceFile = csvPath.filename().string(),
        .headers = retainedHeaders,
        .rows = std::move(retainedRows),
        .rowCounts =
            ActivityValueStatisticsRowCounts{
                .totalRows = records.size(),
                .rowsWithNumericActivityValue = numericValueCount,
                .positiveNumericRows = positiveValueCount,
                .zeroActivityValueRows = zeroValueCount,
                .negativeActivityValueRows = negativeValueCount,
                .nonNumericOrMissingActivityValueRows = records.size() - numericValueCount,
                .retainedPositiveNumericRows = sortedValues.size(),
                .droppedRows = records.size() - sortedValues.size(),
                .retainedUniqueBioassays = retainedBioassayIds.size(),
            },
        .statistics =
            ActivityValueDescriptiveStatistics{
                .sampleSize = sortedValues.size(),
                .mean = mean,
                .variance = variance,
                .varianceDefinition = "sample_variance_ddof_1",
                .skewness = skewness,
                .min = sortedValues.front(),
                .q25 = computeLinearQuantileFromSorted(sortedValues, 0.25),
                .median = computeLinearQuantileFromSorted(sortedValues, 0.5),
                .q75 = computeLinearQuantileFromSorted(sortedValues, 0.75),
                .max = sortedValues.back(),
            },
        .normalityTest =
            ActivityValueNormalityTest{
                .name = "Shapiro-Wilk",
                .computed = false,
                .reasonNotComputed = reasonNotComputed,
                .sampleSize = sortedValues.size(),
                .alpha = shapiroAlpha,
                .statistic = std::nullopt,
                .pValue = std::nullopt,
                .rejectNormality = std::nullopt,
                .interpretation = interpretation,
            },
        .analysis =
            ActivityValueAnalysis{
                .targetQuantity = "Positive numeric Activity_Value distribution",
                .retainedRowDefinition =
                    ActivityValueRetainedRowDefinition{
                        .predicate = "Activity_Value is numeric and strictly greater than 0",
                        .excludedRows = {"missing Activity_Value",
                                         "non-numeric Activity_Value",
                                         "Activity_Value = 0",
                                         "Activity_Value < 0"},
                    },
                .representativeRows = std::move(representativeRows),
                .notes =
                    {"The retained distribution aggregates all positive numeric Activity_Value rows regardless of Activity_Type.",
                     "Variance is reported as the sample variance with ddof = 1 to match the Python and Scala implementations.",
                     "The SVG plot shows a log-scale histogram and a diagnostic status panel for Shapiro-Wilk availability."},
            },
    };
}

void writeActivityValueStatisticsCsv(const ActivityValueStatisticsAnalysisResult& result,
                                     const std::filesystem::path& outputPath)
{
    writeCsvTable(result.headers,
                  result.rows,
                  outputPath,
                  "Activity_Value statistics CSV output path");
}

void writeActivityValueStatisticsPlotSvg(const ActivityValueStatisticsAnalysisResult& result,
                                         const std::filesystem::path& outputPath)
{
    if (result.rows.empty()) {
        throw BioactivityAnalysisError("Activity_Value statistics plot requires retained rows");
    }

    std::ofstream output(outputPath);
    if (!output) {
        throw BioactivityAnalysisError("Could not open Activity_Value statistics plot output path: " +
                                       outputPath.string());
    }

    std::vector<double> logValues;
    logValues.reserve(result.rows.size());
    for (const auto& row : result.rows) {
        logValues.push_back(std::log10(std::stod(row.back())));
    }

    const std::size_t binCount = logValues.size() == 1U ? 1U : std::min<std::size_t>(6U, logValues.size());
    double minLogValue = *std::min_element(logValues.begin(), logValues.end());
    double maxLogValue = *std::max_element(logValues.begin(), logValues.end());
    if (std::abs(maxLogValue - minLogValue) < 1.0e-12) {
        minLogValue -= 0.5;
        maxLogValue += 0.5;
    }

    std::vector<std::size_t> histogramCounts(binCount, 0U);
    for (const double value : logValues) {
        const double normalized = (value - minLogValue) / (maxLogValue - minLogValue);
        const std::size_t binIndex =
            std::min<std::size_t>(binCount - 1U,
                                  static_cast<std::size_t>(std::floor(normalized * static_cast<double>(binCount))));
        histogramCounts[binIndex] += 1U;
    }

    const std::size_t maxCount =
        *std::max_element(histogramCounts.begin(), histogramCounts.end());

    constexpr double width = 1280.0;
    constexpr double height = 720.0;
    constexpr double outerLeft = 60.0;
    constexpr double outerTop = 85.0;
    constexpr double panelWidth = 540.0;
    constexpr double panelHeight = 520.0;
    constexpr double panelGap = 70.0;
    constexpr double innerLeftPad = 55.0;
    constexpr double innerRightPad = 25.0;
    constexpr double innerTopPad = 25.0;
    constexpr double innerBottomPad = 60.0;

    const double leftPanelX = outerLeft;
    const double rightPanelX = outerLeft + panelWidth + panelGap;
    const double panelY = outerTop;
    const double leftPlotWidth = panelWidth - innerLeftPad - innerRightPad;
    const double leftPlotHeight = panelHeight - innerTopPad - innerBottomPad;
    const double binWidth = leftPlotWidth / static_cast<double>(binCount);

    output << "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n";
    output << "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"" << width << "\" height=\""
           << height << "\" viewBox=\"0 0 " << width << ' ' << height << "\">\n";
    output << "<rect width=\"100%\" height=\"100%\" fill=\"#ffffff\"/>\n";
    output << svgText(width / 2.0 - 260.0,
                      42.0,
                      "Positive Numeric Activity_Value Diagnostics",
                      "font-size=\"20\" font-weight=\"700\"")
           << '\n';

    output << "<rect x=\"" << leftPanelX << "\" y=\"" << panelY << "\" width=\""
           << panelWidth << "\" height=\"" << panelHeight
           << "\" fill=\"#f8fafc\" stroke=\"#cbd5e1\"/>\n";
    output << "<rect x=\"" << rightPanelX << "\" y=\"" << panelY << "\" width=\""
           << panelWidth << "\" height=\"" << panelHeight
           << "\" fill=\"#f8fafc\" stroke=\"#cbd5e1\"/>\n";

    output << svgText(leftPanelX + 100.0,
                      panelY - 14.0,
                      "Positive Numeric Activity_Value Histogram",
                      "font-size=\"16\" font-weight=\"600\"")
           << '\n';
    output << svgText(rightPanelX + 150.0,
                      panelY - 14.0,
                      "Normality / Q-Q Diagnostics",
                      "font-size=\"16\" font-weight=\"600\"")
           << '\n';

    for (std::size_t tick = 0U; tick <= maxCount; ++tick) {
        const double y = panelY + innerTopPad +
                         (1.0 - static_cast<double>(tick) / static_cast<double>(std::max<std::size_t>(1U, maxCount))) *
                             leftPlotHeight;
        output << "<line x1=\"" << leftPanelX + innerLeftPad << "\" y1=\"" << y
               << "\" x2=\"" << leftPanelX + innerLeftPad + leftPlotWidth << "\" y2=\""
               << y << "\" stroke=\"#e2e8f0\" stroke-dasharray=\"4 6\"/>\n";
        output << svgText(leftPanelX + 18.0, y + 5.0, std::to_string(tick)) << '\n';
    }

    for (std::size_t binIndex = 0U; binIndex < binCount; ++binIndex) {
        const double barHeight = maxCount == 0U
                                     ? 0.0
                                     : leftPlotHeight * static_cast<double>(histogramCounts[binIndex]) /
                                           static_cast<double>(maxCount);
        const double x = leftPanelX + innerLeftPad + static_cast<double>(binIndex) * binWidth + 6.0;
        const double y = panelY + innerTopPad + leftPlotHeight - barHeight;
        output << "<rect x=\"" << x << "\" y=\"" << y << "\" width=\""
               << std::max(1.0, binWidth - 12.0) << "\" height=\"" << barHeight
               << "\" fill=\"#4f83b6\" fill-opacity=\"0.85\" stroke=\"#1f2937\"/>\n";

        const double lowerLog = minLogValue + static_cast<double>(binIndex) / static_cast<double>(binCount) *
                                                  (maxLogValue - minLogValue);
        const double xLabel = x + std::max(1.0, binWidth - 12.0) / 2.0 - 16.0;
        output << svgText(xLabel,
                          panelY + innerTopPad + leftPlotHeight + 28.0,
                          formatCompactDouble(std::pow(10.0, lowerLog)))
               << '\n';
    }

    output << svgText(leftPanelX + panelWidth / 2.0 - 85.0,
                      panelY + panelHeight - 12.0,
                      "Activity_Value (log10 scale)")
           << '\n';
    output << svgText(leftPanelX + 8.0,
                      panelY + panelHeight / 2.0,
                      "Frequency",
                      "transform=\"rotate(-90 68 345)\"")
           << '\n';

    output << svgText(rightPanelX + 130.0,
                      panelY + 72.0,
                      result.normalityTest.computed ? "Shapiro-Wilk computed" : "Shapiro-Wilk not computed",
                      "font-size=\"18\" font-weight=\"600\"")
           << '\n';
    output << svgText(rightPanelX + 60.0,
                      panelY + 140.0,
                      "sample size = " + std::to_string(result.normalityTest.sampleSize),
                      "font-size=\"16\"")
           << '\n';
    output << svgText(rightPanelX + 60.0,
                      panelY + 200.0,
                      "alpha = " + formatCompactDouble(result.normalityTest.alpha),
                      "font-size=\"16\"")
           << '\n';
    if (result.normalityTest.reasonNotComputed.has_value()) {
        output << svgText(rightPanelX + 60.0,
                          panelY + 280.0,
                          *result.normalityTest.reasonNotComputed,
                          "font-size=\"16\"")
               << '\n';
    }
    output << svgText(rightPanelX + 60.0,
                      panelY + 350.0,
                      result.normalityTest.interpretation,
                      "font-size=\"16\"")
           << '\n';

    output << "</svg>\n";
}

GradientDescentAnalysisResult buildGradientDescentAnalysis(const std::vector<AtomRecord>& atoms,
                                                           const std::string_view sourceFile,
                                                           const double learningRate,
                                                           const std::size_t epochs,
                                                           const double initialWeight)
{
    if (atoms.empty()) {
        throw GradientDescentAnalysisError(
            "Gradient descent requires at least one atom record with mass and atomic number");
    }
    if (learningRate <= 0.0) {
        throw GradientDescentAnalysisError("Gradient descent learning rate must be positive");
    }
    if (epochs == 0U) {
        throw GradientDescentAnalysisError("Gradient descent epochs must be greater than zero");
    }

    std::vector<GradientDescentAtomRow> atomRows;
    atomRows.reserve(atoms.size());
    std::vector<double> xValues;
    xValues.reserve(atoms.size());
    std::vector<double> yValues;
    yValues.reserve(atoms.size());

    for (const auto& atom : atoms) {
        atomRows.push_back(GradientDescentAtomRow{
            .index = atom.index,
            .symbol = atom.symbol,
            .mass = atom.mass,
            .atomicNumber = atom.atomicNumber,
        });
        xValues.push_back(atom.mass);
        yValues.push_back(static_cast<double>(atom.atomicNumber));
    }

    const double denominator = std::transform_reduce(
        xValues.begin(), xValues.end(), xValues.begin(), 0.0, std::plus<>(), std::multiplies<>());
    if (std::abs(denominator) < 1.0e-12) {
        throw GradientDescentAnalysisError(
            "Gradient descent closed-form solution is undefined when all masses are zero");
    }

    std::vector<GradientDescentTraceRow> traceRows;
    traceRows.reserve(epochs + 1U);

    double weight = initialWeight;
    for (std::size_t epoch = 0; epoch <= epochs; ++epoch) {
        const double sumSquaredError = computeSumSquaredError(xValues, yValues, weight);
        const double meanSquaredError = computeMeanSquaredError(xValues, yValues, weight);
        const double gradient = computeSumSquaredErrorGradient(xValues, yValues, weight);

        traceRows.push_back(GradientDescentTraceRow{
            .epoch = epoch,
            .weight = weight,
            .gradient = gradient,
            .sumSquaredError = sumSquaredError,
            .meanSquaredError = meanSquaredError,
        });

        if (epoch < epochs) {
            weight -= learningRate * gradient;
        }
    }

    const double numerator = std::transform_reduce(
        xValues.begin(), xValues.end(), yValues.begin(), 0.0, std::plus<>(), std::multiplies<>());
    const double closedFormWeight = numerator / denominator;
    const auto bestTraceRow = std::min_element(
        traceRows.begin(), traceRows.end(), [](const auto& left, const auto& right) {
            return left.meanSquaredError < right.meanSquaredError;
        });
    const auto [minMass, maxMass] = std::minmax_element(xValues.begin(), xValues.end());
    const auto [minAtomicNumber, maxAtomicNumber] =
        std::minmax_element(yValues.begin(), yValues.end());

    GradientDescentSummary summary{
        .dataset =
            GradientDescentDatasetSummary{
                .rowCount = atomRows.size(),
                .feature = "mass",
                .target = "atomicNumber",
                .featureMatrixShape = {static_cast<int>(atomRows.size()), 1},
                .massRange = {*minMass, *maxMass},
                .atomicNumberRange = {static_cast<int>(*minAtomicNumber),
                                      static_cast<int>(*maxAtomicNumber)},
                .atomRows = std::move(atomRows),
            },
        .model =
            GradientDescentModelSummary{
                .predictionEquation = "y_hat = w * x",
                .objectiveName = "sum_squared_error",
                .objectiveEquation = "L(w) = sum_i (y_i - w x_i)^2",
                .meanSquaredErrorEquation = "MSE(w) = (1 / n) * sum_i (y_i - w x_i)^2",
                .gradientEquation =
                    "dL/dw = sum_i -2 x_i (y_i - w x_i) = 2 sum_i x_i (w x_i - y_i)",
                .featureName = "atom mass",
                .targetName = "atomic number",
            },
        .optimization =
            GradientDescentOptimizationSummary{
                .initialWeight = initialWeight,
                .finalWeight = traceRows.back().weight,
                .learningRate = learningRate,
                .epochs = epochs,
                .closedFormWeight = closedFormWeight,
                .initialSumSquaredError = traceRows.front().sumSquaredError,
                .finalSumSquaredError = traceRows.back().sumSquaredError,
                .initialMeanSquaredError = traceRows.front().meanSquaredError,
                .finalMeanSquaredError = traceRows.back().meanSquaredError,
                .weightErrorVsClosedForm = traceRows.back().weight - closedFormWeight,
                .gradientChecks =
                    GradientCheckSummary{
                        .initialWeight =
                            GradientCheck{
                                .analytic =
                                    computeSumSquaredErrorGradient(xValues, yValues, initialWeight),
                                .finiteDifference =
                                    finiteDifferenceGradient(xValues, yValues, initialWeight),
                            },
                        .finalWeight =
                            GradientCheck{
                                .analytic = computeSumSquaredErrorGradient(
                                    xValues, yValues, traceRows.back().weight),
                                .finiteDifference = finiteDifferenceGradient(
                                    xValues, yValues, traceRows.back().weight),
                            },
                    },
                .lossTrace =
                    GradientDescentLossTraceSummary{
                        .monotonicNonincreasingMeanSquaredError =
                            std::adjacent_find(traceRows.begin(),
                                               traceRows.end(),
                                               [](const auto& left, const auto& right) {
                                                   return right.meanSquaredError >
                                                          left.meanSquaredError + 1.0e-12;
                                               }) == traceRows.end(),
                        .bestEpoch = bestTraceRow->epoch,
                    },
            },
    };

    return GradientDescentAnalysisResult{
        .sourceFile = std::string(sourceFile),
        .headers = {"epoch", "weight", "gradient", "sum_squared_error", "mse"},
        .traceRows = std::move(traceRows),
        .summary = std::move(summary),
    };
}

void writeGradientDescentCsv(const GradientDescentAnalysisResult& result,
                             const std::filesystem::path& outputPath)
{
    std::vector<std::vector<std::string>> rows;
    rows.reserve(result.traceRows.size());
    for (const auto& row : result.traceRows) {
        rows.push_back({std::to_string(row.epoch),
                        formatDouble(row.weight),
                        formatDouble(row.gradient),
                        formatDouble(row.sumSquaredError),
                        formatDouble(row.meanSquaredError)});
    }

    writeCsvTable(result.headers, rows, outputPath, "gradient descent CSV output path");
}

void writeGradientDescentLossPlotSvg(const GradientDescentAnalysisResult& result,
                                     const std::filesystem::path& outputPath)
{
    if (result.traceRows.empty()) {
        throw GradientDescentAnalysisError(
            "Gradient descent loss plot requires at least one optimization step");
    }

    std::ofstream output(outputPath);
    if (!output) {
        throw GradientDescentAnalysisError(
            "Could not open gradient descent loss plot output path: " + outputPath.string());
    }

    constexpr double width = 1280.0;
    constexpr double height = 720.0;
    constexpr double left = 100.0;
    constexpr double right = 60.0;
    constexpr double top = 70.0;
    constexpr double bottom = 90.0;
    const double plotWidth = width - left - right;
    const double plotHeight = height - top - bottom;
    const double maxEpoch = static_cast<double>(result.traceRows.back().epoch);

    double minMse = result.traceRows.front().meanSquaredError;
    double maxMse = result.traceRows.front().meanSquaredError;
    for (const auto& row : result.traceRows) {
        minMse = std::min(minMse, row.meanSquaredError);
        maxMse = std::max(maxMse, row.meanSquaredError);
    }
    const auto [plotMinMse, plotMaxMse] = expandedDomain(minMse, maxMse);

    auto xToSvg = [&](const double epoch) {
        if (maxEpoch <= 0.0) {
            return left;
        }
        return left + (epoch / maxEpoch) * plotWidth;
    };
    auto yToSvg = [&](const double mse) {
        return top + (plotMaxMse - mse) / (plotMaxMse - plotMinMse) * plotHeight;
    };

    std::ostringstream polyline;
    for (std::size_t index = 0; index < result.traceRows.size(); ++index) {
        if (index > 0U) {
            polyline << ' ';
        }
        polyline << xToSvg(static_cast<double>(result.traceRows[index].epoch)) << ','
                 << yToSvg(result.traceRows[index].meanSquaredError);
    }

    output << "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"" << width << "\" height=\""
           << height << "\" viewBox=\"0 0 " << width << ' ' << height << "\">\n";
    output << "<rect width=\"100%\" height=\"100%\" fill=\"#ffffff\"/>\n";
    output << svgText(left,
                      40.0,
                      "Manual Gradient Descent MSE Trace",
                      "font-size=\"24\" font-weight=\"700\"")
           << '\n';
    output << "<line x1=\"" << left << "\" y1=\"" << top + plotHeight << "\" x2=\""
           << left + plotWidth << "\" y2=\"" << top + plotHeight
           << "\" stroke=\"#111827\" stroke-width=\"2\"/>\n";
    output << "<line x1=\"" << left << "\" y1=\"" << top << "\" x2=\"" << left << "\" y2=\""
           << top + plotHeight << "\" stroke=\"#111827\" stroke-width=\"2\"/>\n";
    output << "<polyline fill=\"none\" stroke=\"#0f766e\" stroke-width=\"3\" points=\""
           << polyline.str() << "\"/>\n";
    output << svgText(width / 2.0 - 20.0,
                      height - 25.0,
                      "Epoch",
                      "font-size=\"18\" font-weight=\"600\"")
           << '\n';
    output << svgText(20.0,
                      height / 2.0,
                      "MSE",
                      "font-size=\"18\" font-weight=\"600\" transform=\"rotate(-90 20 " +
                          formatCompactDouble(height / 2.0) + ")\"")
           << '\n';
    output << svgText(left, top + plotHeight + 35.0, "0") << '\n';
    output << svgText(left + plotWidth - 35.0,
                      top + plotHeight + 35.0,
                      std::to_string(result.traceRows.back().epoch))
           << '\n';
    output << svgText(25.0, top + 5.0, formatCompactDouble(plotMaxMse)) << '\n';
    output << svgText(25.0, top + plotHeight + 5.0, formatCompactDouble(plotMinMse)) << '\n';
    output << "</svg>\n";
}

void writeGradientDescentFitPlotSvg(const GradientDescentAnalysisResult& result,
                                    const std::filesystem::path& outputPath)
{
    if (result.summary.dataset.atomRows.empty()) {
        throw GradientDescentAnalysisError(
            "Gradient descent fit plot requires at least one atom feature row");
    }

    std::ofstream output(outputPath);
    if (!output) {
        throw GradientDescentAnalysisError(
            "Could not open gradient descent fit plot output path: " + outputPath.string());
    }

    constexpr double width = 1280.0;
    constexpr double height = 720.0;
    constexpr double left = 100.0;
    constexpr double right = 80.0;
    constexpr double top = 70.0;
    constexpr double bottom = 90.0;
    const double plotWidth = width - left - right;
    const double plotHeight = height - top - bottom;
    const double maxMass = result.summary.dataset.massRange[1] * 1.05;
    const double maxAtomicNumber =
        static_cast<double>(result.summary.dataset.atomicNumberRange[1]) * 1.05;
    const double finalWeight = result.summary.optimization.finalWeight;

    auto xToSvg = [&](const double mass) { return left + (mass / maxMass) * plotWidth; };
    auto yToSvg = [&](const double atomicNumber) {
        return top + (maxAtomicNumber - atomicNumber) / maxAtomicNumber * plotHeight;
    };

    output << "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"" << width << "\" height=\""
           << height << "\" viewBox=\"0 0 " << width << ' ' << height << "\">\n";
    output << "<rect width=\"100%\" height=\"100%\" fill=\"#ffffff\"/>\n";
    output << svgText(left,
                      40.0,
                      "Manual Gradient Descent Fit: Mass to Atomic Number",
                      "font-size=\"24\" font-weight=\"700\"")
           << '\n';
    output << "<line x1=\"" << left << "\" y1=\"" << top + plotHeight << "\" x2=\""
           << left + plotWidth << "\" y2=\"" << top + plotHeight
           << "\" stroke=\"#111827\" stroke-width=\"2\"/>\n";
    output << "<line x1=\"" << left << "\" y1=\"" << top << "\" x2=\"" << left << "\" y2=\""
           << top + plotHeight << "\" stroke=\"#111827\" stroke-width=\"2\"/>\n";

    const double lineX1 = 0.0;
    const double lineY1 = 0.0;
    const double lineX2 = maxMass;
    const double lineY2 = finalWeight * maxMass;
    output << "<line x1=\"" << xToSvg(lineX1) << "\" y1=\"" << yToSvg(lineY1) << "\" x2=\""
           << xToSvg(lineX2) << "\" y2=\"" << yToSvg(lineY2)
           << "\" stroke=\"#b91c1c\" stroke-width=\"3\"/>\n";

    for (const auto& atomRow : result.summary.dataset.atomRows) {
        output << "<circle cx=\"" << xToSvg(atomRow.mass) << "\" cy=\""
               << yToSvg(static_cast<double>(atomRow.atomicNumber))
               << "\" r=\"6\" fill=\"#4f46e5\" stroke=\"#111827\" stroke-width=\"1\"/>\n";
    }

    output << svgText(width / 2.0 - 40.0,
                      height - 25.0,
                      "Atom mass",
                      "font-size=\"18\" font-weight=\"600\"")
           << '\n';
    output << svgText(20.0,
                      height / 2.0,
                      "Atomic number",
                      "font-size=\"18\" font-weight=\"600\" transform=\"rotate(-90 20 " +
                          formatCompactDouble(height / 2.0) + ")\"")
           << '\n';
    output << svgText(left + plotWidth - 220.0,
                      top + 30.0,
                      "y_hat = " + formatCompactDouble(finalWeight) + "x",
                      "font-size=\"18\" font-weight=\"600\"")
           << '\n';
    output << "</svg>\n";
}

AtomElementEntropyAnalysisResult buildAtomElementEntropyAnalysis(const std::vector<AtomRecord>& atoms,
                                                                std::string_view sourceFile)
{
    if (atoms.empty()) {
        throw BioactivityAnalysisError("Atom entropy analysis requires at least one atom record");
    }

    std::map<std::string, std::size_t> requiredCounts;
    for (const auto& element : kRequiredAtomEntropyElements) {
        requiredCounts.emplace(element, 0U);
    }
    std::map<std::string, std::size_t> unexpectedCounts;

    for (const auto& atom : atoms) {
        const std::string symbol = trimWhitespace(atom.symbol);
        if (requiredCounts.contains(symbol)) {
            requiredCounts[symbol] += 1U;
        }
        else if (!symbol.empty()) {
            unexpectedCounts[symbol] += 1U;
        }
    }

    const std::size_t retainedAtomRows = std::accumulate(
        requiredCounts.begin(), requiredCounts.end(), std::size_t{0U}, [](const std::size_t sum, const auto& entry) {
            return sum + entry.second;
        });
    if (retainedAtomRows == 0U) {
        throw BioactivityAnalysisError("Atom entropy analysis retained no O/N/C/H atoms");
    }

    const std::size_t observedRequiredElementCategories = std::count_if(
        requiredCounts.begin(), requiredCounts.end(), [](const auto& entry) { return entry.second > 0U; });
    const std::size_t unexpectedElementRows = std::accumulate(
        unexpectedCounts.begin(), unexpectedCounts.end(), std::size_t{0U}, [](const std::size_t sum, const auto& entry) {
            return sum + entry.second;
        });

    std::map<std::string, AtomElementDistributionEntry> distribution;
    std::vector<std::vector<std::string>> rows;
    rows.reserve(kRequiredAtomEntropyElements.size());
    double entropyValue = 0.0;
    std::string dominantElement;
    std::size_t dominantCount = 0U;
    double dominantProportion = 0.0;

    for (const auto& element : kRequiredAtomEntropyElements) {
        const std::size_t count = requiredCounts.at(element);
        const double proportion = static_cast<double>(count) / static_cast<double>(retainedAtomRows);
        const double logProportion = proportion > 0.0 ? std::log(proportion) : 0.0;
        const double shannonContribution = proportion > 0.0 ? -(proportion * logProportion) : 0.0;
        entropyValue += shannonContribution;
        distribution.emplace(element,
                             AtomElementDistributionEntry{
                                 .count = count,
                                 .proportion = proportion,
                                 .logProportion = logProportion,
                                 .shannonContribution = shannonContribution,
                             });
        rows.push_back({element,
                        std::to_string(count),
                        formatDouble(proportion),
                        formatDouble(logProportion),
                        formatDouble(shannonContribution)});

        if (count > dominantCount) {
            dominantElement = element;
            dominantCount = count;
            dominantProportion = proportion;
        }
    }

    const double maximumEntropy =
        observedRequiredElementCategories == 0U
            ? 0.0
            : std::log(static_cast<double>(observedRequiredElementCategories));
    const double normalizedEntropy =
        maximumEntropy > 0.0 ? entropyValue / maximumEntropy : 0.0;

    return AtomElementEntropyAnalysisResult{
        .sourceFile = std::string(sourceFile),
        .headers = {"element", "count", "proportion", "log_proportion", "shannon_contribution"},
        .rows = std::move(rows),
        .rowCounts =
            AtomElementEntropyRowCounts{
                .totalAtomRows = atoms.size(),
                .retainedAtomRows = retainedAtomRows,
                .requiredElementCategories = kRequiredAtomEntropyElements.size(),
                .observedRequiredElementCategories = observedRequiredElementCategories,
                .unexpectedElementRows = unexpectedElementRows,
                .unexpectedElementCategories = unexpectedCounts.size(),
            },
        .entropy =
            AtomElementEntropyMetrics{
                .formula = "H = -sum(p_i * log(p_i))",
                .logBase = "natural_log",
                .value = entropyValue,
                .maximumEntropyForObservedSupport = maximumEntropy,
                .normalizedEntropy = normalizedEntropy,
            },
        .distribution = std::move(distribution),
        .analysis =
            AtomElementEntropyAnalysis{
                .targetQuantity = "Atom element entropy over O/N/C/H proportions",
                .requiredElements = kRequiredAtomEntropyElements,
                .uniqueRetainedElements = observedRequiredElementCategories,
                .dominantElement =
                    AtomElementDominantElement{
                        .element = dominantElement,
                        .count = dominantCount,
                        .proportion = dominantProportion,
                    },
                .unexpectedElements = std::move(unexpectedCounts),
                .notes =
                    {"Entropy is computed only over the required O/N/C/H support requested in the README exercise.",
                     "Unexpected atom symbols are excluded from the entropy sum and reported separately for transparency.",
                     "Normalized entropy uses the maximum entropy over the observed required-element support rather than the fixed four-element support."},
            },
    };
}

void writeAtomElementEntropyCsv(const AtomElementEntropyAnalysisResult& result,
                                const std::filesystem::path& outputPath)
{
    writeCsvTable(result.headers,
                  result.rows,
                  outputPath,
                  "atom element entropy CSV output path");
}

void writeAtomElementEntropyPlotSvg(const AtomElementEntropyAnalysisResult& result,
                                    const std::filesystem::path& outputPath)
{
    std::ofstream output(outputPath);
    if (!output) {
        throw BioactivityAnalysisError("Could not open atom element entropy plot output path: " +
                                       outputPath.string());
    }

    constexpr double width = 1100.0;
    constexpr double height = 720.0;
    constexpr double left = 90.0;
    constexpr double right = 60.0;
    constexpr double top = 80.0;
    constexpr double bottom = 100.0;
    const double plotWidth = width - left - right;
    const double plotHeight = height - top - bottom;
    const double barWidth = plotWidth / static_cast<double>(result.rows.size());

    output << "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n";
    output << "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"" << width << "\" height=\""
           << height << "\" viewBox=\"0 0 " << width << ' ' << height << "\">\n";
    output << "<rect width=\"100%\" height=\"100%\" fill=\"#ffffff\"/>\n";
    output << "<rect x=\"" << left << "\" y=\"" << top << "\" width=\"" << plotWidth
           << "\" height=\"" << plotHeight << "\" fill=\"#f8fafc\" stroke=\"#cbd5e1\"/>\n";

    for (const double yTick : std::vector<double>{0.0, 0.25, 0.5, 0.75, 1.0}) {
        const double y = top + (1.0 - yTick) * plotHeight;
        output << "<line x1=\"" << left << "\" y1=\"" << y << "\" x2=\"" << left + plotWidth
               << "\" y2=\"" << y << "\" stroke=\"#cbd5e1\" stroke-dasharray=\"4 6\"/>\n";
        output << svgText(28.0, y + 5.0, formatCompactDouble(yTick)) << '\n';
    }

    for (std::size_t index = 0U; index < result.rows.size(); ++index) {
        const auto& row = result.rows[index];
        const double proportion = std::stod(row[2]);
        const double barHeight = proportion * plotHeight;
        const double x = left + static_cast<double>(index) * barWidth + 18.0;
        const double y = top + plotHeight - barHeight;
        output << "<rect x=\"" << x << "\" y=\"" << y << "\" width=\""
               << std::max(1.0, barWidth - 36.0) << "\" height=\"" << barHeight
               << "\" fill=\"#2563eb\" fill-opacity=\"0.8\" stroke=\"#1e3a8a\"/>\n";
        output << svgText(x + std::max(1.0, barWidth - 36.0) / 2.0 - 8.0,
                          top + plotHeight + 30.0,
                          row[0])
               << '\n';
    }

    output << svgText(width / 2.0 - 150.0,
                      40.0,
                      "Atom Element Proportions (H = " + formatCompactDouble(result.entropy.value) + ")",
                      "font-size=\"20\" font-weight=\"700\"")
           << '\n';
    output << svgText(width / 2.0 - 30.0, height - 20.0, "Element") << '\n';
    output << svgText(25.0,
                      height / 2.0 + 10.0,
                      "Proportion",
                      "transform=\"rotate(-90 40 360)\"")
           << '\n';
    output << "</svg>\n";
}

void writeBioactivityPlotSvg(const BioactivityAnalysisResult& result,
                             const std::filesystem::path& outputPath)
{
    std::ofstream output(outputPath);
    if (!output) {
        throw BioactivityAnalysisError("Could not open bioactivity plot output path: " +
                                       outputPath.string());
    }

    const std::size_t ic50Index = result.headers.size() - 2U;
    const std::size_t pIC50Index = result.headers.size() - 1U;
    std::vector<double> observedIc50;
    std::vector<double> observedPIC50;
    observedIc50.reserve(result.filteredRows.size());
    observedPIC50.reserve(result.filteredRows.size());
    for (const auto& row : result.filteredRows) {
        observedIc50.push_back(std::stod(row.at(ic50Index)));
        observedPIC50.push_back(std::stod(row.at(pIC50Index)));
    }

    const auto [minIc50, maxIc50] =
        expandedDomain(*std::min_element(observedIc50.begin(), observedIc50.end()),
                       *std::max_element(observedIc50.begin(), observedIc50.end()));
    const auto curveX = geometricSpace(minIc50, maxIc50, 200U);

    std::vector<double> curveY;
    curveY.reserve(curveX.size());
    for (const double value : curveX) {
        curveY.push_back(-std::log10(value));
    }

    const double minY = *std::min_element(curveY.begin(), curveY.end());
    const double maxY = *std::max_element(curveY.begin(), curveY.end());
    const double yPadding = std::max((maxY - minY) * 0.08, 0.05);
    const double plotMinY = minY - yPadding;
    const double plotMaxY = maxY + yPadding;
    const double logMinX = std::log10(minIc50);
    const double logMaxX = std::log10(maxIc50);

    constexpr double width = 1200.0;
    constexpr double height = 720.0;
    constexpr double left = 100.0;
    constexpr double right = 60.0;
    constexpr double top = 70.0;
    constexpr double bottom = 90.0;
    const double plotWidth = width - left - right;
    const double plotHeight = height - top - bottom;

    auto xToSvg = [&](const double xValue) {
        return left + (std::log10(xValue) - logMinX) / (logMaxX - logMinX) * plotWidth;
    };
    auto yToSvg = [&](const double yValue) {
        return top + (plotMaxY - yValue) / (plotMaxY - plotMinY) * plotHeight;
    };

    output << "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n";
    output << "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"" << width << "\" height=\""
           << height << "\" viewBox=\"0 0 " << width << ' ' << height << "\">\n";
    output << "<rect width=\"100%\" height=\"100%\" fill=\"#ffffff\"/>\n";
    output << "<rect x=\"" << left << "\" y=\"" << top << "\" width=\"" << plotWidth
           << "\" height=\"" << plotHeight << "\" fill=\"#f8fafc\" stroke=\"#cbd5e1\"/>\n";

    for (const double xTick : std::vector<double>{minIc50, observedIc50.front(), maxIc50}) {
        const double x = xToSvg(xTick);
        output << "<line x1=\"" << x << "\" y1=\"" << top << "\" x2=\"" << x << "\" y2=\""
               << top + plotHeight << "\" stroke=\"#cbd5e1\" stroke-dasharray=\"4 6\"/>\n";
        output << svgText(x - 18.0, top + plotHeight + 28.0, formatDouble(xTick));
        output << '\n';
    }

    for (int index = 0; index <= 4; ++index) {
        const double yValue = plotMinY + (plotMaxY - plotMinY) * static_cast<double>(index) / 4.0;
        const double y = yToSvg(yValue);
        output << "<line x1=\"" << left << "\" y1=\"" << y << "\" x2=\"" << left + plotWidth
               << "\" y2=\"" << y << "\" stroke=\"#cbd5e1\" stroke-dasharray=\"4 6\"/>\n";
        output << svgText(28.0, y + 5.0, formatDouble(yValue));
        output << '\n';
    }

    std::ostringstream polyline;
    for (std::size_t index = 0; index < curveX.size(); ++index) {
        if (index > 0) {
            polyline << ' ';
        }
        polyline << xToSvg(curveX[index]) << ',' << yToSvg(curveY[index]);
    }
    output << "<polyline fill=\"none\" stroke=\"#1d4ed8\" stroke-width=\"3\" points=\""
           << polyline.str() << "\"/>\n";

    for (std::size_t index = 0; index < observedIc50.size(); ++index) {
        output << "<circle cx=\"" << xToSvg(observedIc50[index]) << "\" cy=\""
               << yToSvg(observedPIC50[index])
               << "\" r=\"6\" fill=\"#f59e0b\" stroke=\"#111827\" stroke-width=\"1\"/>\n";
    }

    output << svgText(width / 2.0 - 190.0,
                      35.0,
                      "pIC50 Transform Across Observed IC50 Range",
                      "font-size=\"28\" font-weight=\"700\"")
           << '\n';
    output << svgText(width / 2.0 - 40.0,
                      height - 25.0,
                      "IC50 (uM)",
                      "font-size=\"22\" font-weight=\"600\"")
           << '\n';
    output << "<g transform=\"translate(30 " << (top + plotHeight / 2.0 + 40.0)
           << ") rotate(-90)\">\n";
    output << svgText(0.0, 0.0, "pIC50", "font-size=\"22\" font-weight=\"600\"") << '\n';
    output << "</g>\n";
    output << "<rect x=\"" << (width - 265.0) << "\" y=\"" << (top + 10.0)
           << "\" width=\"220\" height=\"84\" fill=\"#ffffff\" stroke=\"#cbd5e1\"/>\n";
    output << "<line x1=\"" << (width - 245.0) << "\" y1=\"" << (top + 34.0) << "\" x2=\""
           << (width - 195.0) << "\" y2=\"" << (top + 34.0)
           << "\" stroke=\"#1d4ed8\" stroke-width=\"3\"/>\n";
    output << svgText(width - 180.0, top + 40.0, "y = -log10(x)") << '\n';
    output << "<circle cx=\"" << (width - 220.0) << "\" cy=\"" << (top + 66.0)
           << "\" r=\"6\" fill=\"#f59e0b\" stroke=\"#111827\" stroke-width=\"1\"/>\n";
    output << svgText(width - 180.0, top + 72.0, "Observed IC50 rows") << '\n';
    output << "</svg>\n";
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

BondedDistanceAnalysisResult buildBondedDistanceAnalysis(const DistanceMatrixResult& distanceMatrix,
                                                         const AdjacencyMatrix& adjacencyMatrix)
{
    validateBondedDistanceAlignment(distanceMatrix, adjacencyMatrix);

    std::vector<BondedAtomPair> bondedAtomPairs = bondedAtomPairsFromAdjacency(adjacencyMatrix);
    std::set<std::pair<int, int>> bondedPairSet;
    for (const auto& pair : bondedAtomPairs) {
        bondedPairSet.emplace(pair.atomId1, pair.atomId2);
    }

    std::vector<AtomPairDistance> bondedPairDistances;
    std::vector<AtomPairDistance> nonbondedPairDistances;

    for (std::size_t rowIndex = 0; rowIndex < distanceMatrix.atomIds.size(); ++rowIndex) {
        for (std::size_t columnIndex = rowIndex + 1; columnIndex < distanceMatrix.atomIds.size();
             ++columnIndex) {
            AtomPairDistance pairDistance{
                .atomId1 = distanceMatrix.atomIds[rowIndex],
                .atomId2 = distanceMatrix.atomIds[columnIndex],
                .distanceAngstrom = distanceMatrix.distanceMatrix[rowIndex][columnIndex],
            };

            if (bondedPairSet.contains({pairDistance.atomId1, pairDistance.atomId2})) {
                bondedPairDistances.push_back(pairDistance);
            }
            else {
                nonbondedPairDistances.push_back(pairDistance);
            }
        }
    }

    const std::size_t expectedPairCount =
        distanceMatrix.atomIds.size() * (distanceMatrix.atomIds.size() - 1U) / 2U;
    if (bondedPairDistances.size() + nonbondedPairDistances.size() != expectedPairCount) {
        throw DistanceAnalysisError(
            "Expected " + std::to_string(expectedPairCount) + " unique atom pairs, partitioned " +
            std::to_string(bondedPairDistances.size() + nonbondedPairDistances.size()) +
            " instead");
    }

    return makeBondedDistanceAnalysisResult(distanceMatrix,
                                            std::move(bondedAtomPairs),
                                            std::move(bondedPairDistances),
                                            std::move(nonbondedPairDistances));
}

BondAngleAnalysisResult buildBondAngleAnalysis(const DistanceMatrixResult& distanceMatrix,
                                               const AdjacencyMatrix& adjacencyMatrix)
{
    validateBondAngleAlignment(distanceMatrix, adjacencyMatrix);

    const std::vector<BondAngleTriplet> triplets = bondAngleTripletsFromAdjacency(adjacencyMatrix);
    std::map<int, std::size_t> atomIndexById;
    for (std::size_t index = 0; index < distanceMatrix.atomIds.size(); ++index) {
        atomIndexById.emplace(distanceMatrix.atomIds[index], index);
    }

    std::vector<BondAngleMeasurement> bondAngles;
    bondAngles.reserve(triplets.size());
    for (const auto& triplet : triplets) {
        const std::size_t aIndex = atomIndexById.at(triplet.atomIdA);
        const std::size_t centerIndex = atomIndexById.at(triplet.atomIdBCenter);
        const std::size_t cIndex = atomIndexById.at(triplet.atomIdC);
        const auto firstBondVector = subtractCoordinates(
            distanceMatrix.xyzCoordinates[aIndex], distanceMatrix.xyzCoordinates[centerIndex]);
        const auto secondBondVector = subtractCoordinates(
            distanceMatrix.xyzCoordinates[cIndex], distanceMatrix.xyzCoordinates[centerIndex]);

        bondAngles.push_back(BondAngleMeasurement{
            .atomIdA = triplet.atomIdA,
            .atomIdBCenter = triplet.atomIdBCenter,
            .atomIdC = triplet.atomIdC,
            .angleDegrees = computeBondAngleDegrees(firstBondVector, secondBondVector),
        });
    }

    return makeBondAngleAnalysisResult(distanceMatrix, triplets, std::move(bondAngles));
}

SpringBondPotentialAnalysisResult
buildSpringBondPotentialAnalysis(const DistanceMatrixResult& distanceMatrix,
                                 const AdjacencyMatrix& adjacencyMatrix,
                                 const std::vector<AtomRecord>& atoms)
{
    validateSpringBondPotentialAlignment(distanceMatrix, adjacencyMatrix, atoms);

    std::map<int, std::size_t> atomIndexById;
    std::map<int, std::string> atomSymbolById;
    for (std::size_t index = 0; index < distanceMatrix.atomIds.size(); ++index) {
        const int atomId = distanceMatrix.atomIds[index];
        atomIndexById.emplace(atomId, index);
        atomSymbolById.emplace(atomId, normalizedAtomSymbol(atoms[index]));
    }

    const std::vector<BondedPairWithOrder> bondedPairs =
        bondedPairsWithOrderFromAdjacency(adjacencyMatrix);
    std::map<int, AtomGradientAccumulator> atomGradientAccumulators;
    for (const int atomId : distanceMatrix.atomIds) {
        atomGradientAccumulators.emplace(
            atomId,
            AtomGradientAccumulator{.atomId = atomId,
                                    .atomSymbol = atomSymbolById.at(atomId),
                                    .incidentBondCount = 0U,
                                    .gradientVector = {0.0, 0.0, 0.0}});
    }

    std::map<std::string, std::size_t> referenceDistanceSourceCounts;
    std::vector<BondedPairSpringRecord> bondRecords;
    bondRecords.reserve(bondedPairs.size());

    for (const auto& bondedPair : bondedPairs) {
        const std::size_t atomIndex1 = atomIndexById.at(bondedPair.atomId1);
        const std::size_t atomIndex2 = atomIndexById.at(bondedPair.atomId2);
        const std::string& atomSymbol1 = atomSymbolById.at(bondedPair.atomId1);
        const std::string& atomSymbol2 = atomSymbolById.at(bondedPair.atomId2);
        const std::vector<double> bondVector = subtractCoordinates(
            distanceMatrix.xyzCoordinates[atomIndex1], distanceMatrix.xyzCoordinates[atomIndex2]);
        const double distance = distanceMatrix.distanceMatrix[atomIndex1][atomIndex2];
        if (distance <= kSpringDistanceTolerance) {
            throw DistanceAnalysisError(
                "Spring bond derivative analysis requires non-zero bonded distances");
        }

        const auto [referenceDistance, referenceDistanceSource] =
            inferReferenceBondLengthAngstrom(atomSymbol1, atomSymbol2, bondedPair.bondOrder);
        const double springConstant = resolveSpringConstantForBondOrder(bondedPair.bondOrder);
        const double distanceResidual = distance - referenceDistance;
        const double dEDDistance = springConstant * distanceResidual;
        const std::vector<double> gradientAtom1 =
            scaleCoordinates(bondVector, dEDDistance / distance);
        const std::vector<double> gradientAtom2 = scaleCoordinates(gradientAtom1, -1.0);
        const double springEnergy = 0.5 * springConstant * distanceResidual * distanceResidual;

        ++referenceDistanceSourceCounts[referenceDistanceSource];
        auto& atomAccumulator1 = atomGradientAccumulators.at(bondedPair.atomId1);
        atomAccumulator1.gradientVector =
            addCoordinates(atomAccumulator1.gradientVector, gradientAtom1);
        ++atomAccumulator1.incidentBondCount;
        auto& atomAccumulator2 = atomGradientAccumulators.at(bondedPair.atomId2);
        atomAccumulator2.gradientVector =
            addCoordinates(atomAccumulator2.gradientVector, gradientAtom2);
        ++atomAccumulator2.incidentBondCount;

        bondRecords.push_back(BondedPairSpringRecord{
            .atomId1 = bondedPair.atomId1,
            .atomId2 = bondedPair.atomId2,
            .atomSymbol1 = atomSymbol1,
            .atomSymbol2 = atomSymbol2,
            .bondOrder = bondedPair.bondOrder,
            .distanceAngstrom = distance,
            .referenceDistanceAngstrom = referenceDistance,
            .referenceDistanceSource = referenceDistanceSource,
            .distanceResidualAngstrom = distanceResidual,
            .springConstant = springConstant,
            .springEnergy = springEnergy,
            .dEDDistance = dEDDistance,
            .atom1PartialDerivatives = toCartesianPartialDerivatives(gradientAtom1),
            .atom2PartialDerivatives = toCartesianPartialDerivatives(gradientAtom2)});
    }

    std::vector<AtomGradientRecord> atomGradientRecords;
    atomGradientRecords.reserve(distanceMatrix.atomIds.size());
    std::vector<double> netGradientVector{0.0, 0.0, 0.0};
    for (const int atomId : distanceMatrix.atomIds) {
        const auto& accumulator = atomGradientAccumulators.at(atomId);
        netGradientVector = addCoordinates(netGradientVector, accumulator.gradientVector);
        atomGradientRecords.push_back(
            AtomGradientRecord{.atomId = accumulator.atomId,
                               .atomSymbol = accumulator.atomSymbol,
                               .incidentBondCount = accumulator.incidentBondCount,
                               .dEDx = accumulator.gradientVector[0],
                               .dEDy = accumulator.gradientVector[1],
                               .dEDz = accumulator.gradientVector[2],
                               .gradientNorm = vectorMagnitude(accumulator.gradientVector)});
    }

    std::vector<double> distanceResiduals;
    std::vector<double> springEnergies;
    std::vector<double> atomGradientNorms;
    distanceResiduals.reserve(bondRecords.size());
    springEnergies.reserve(bondRecords.size());
    atomGradientNorms.reserve(atomGradientRecords.size());
    for (const auto& bondRecord : bondRecords) {
        distanceResiduals.push_back(bondRecord.distanceResidualAngstrom);
        springEnergies.push_back(bondRecord.springEnergy);
    }
    for (const auto& atomGradientRecord : atomGradientRecords) {
        atomGradientNorms.push_back(atomGradientRecord.gradientNorm);
    }

    std::vector<std::pair<std::string, double>> bondOrderSpringConstants;
    for (const auto& [bondOrder, value] : kDefaultBondOrderSpringConstants) {
        bondOrderSpringConstants.emplace_back(std::to_string(bondOrder), value);
    }

    std::vector<std::pair<std::string, double>> referenceDistanceLookupExamples;
    for (const auto& [key, value] : kDefaultReferenceBondLengthsAngstrom) {
        const auto& [symbol1, symbol2, bondOrder] = key;
        referenceDistanceLookupExamples.emplace_back(
            symbol1 + "-" + symbol2 + "-order-" + std::to_string(bondOrder), value);
    }

    std::vector<std::pair<std::string, std::size_t>> sortedSourceCounts;
    for (const auto& [source, count] : referenceDistanceSourceCounts) {
        sortedSourceCounts.emplace_back(source, count);
    }

    return SpringBondPotentialAnalysisResult{
        .atomIds = distanceMatrix.atomIds,
        .bondedPairSpringRecords = std::move(bondRecords),
        .atomGradientRecords = std::move(atomGradientRecords),
        .statistics =
            SpringBondPotentialStatistics{
                .distanceResidualAngstrom = summarizeDistanceResiduals(distanceResiduals),
                .springEnergy = summarizeSpringEnergies(springEnergies),
                .atomGradientNorm = summarizeAtomGradientNorms(atomGradientNorms),
                .gradientBalance =
                    NetCartesianGradient{.dEDx = netGradientVector[0],
                                         .dEDy = netGradientVector[1],
                                         .dEDz = netGradientVector[2],
                                         .gradientNorm = vectorMagnitude(netGradientVector)},
            },
        .analysis =
            SpringBondPotentialAnalysis{
                .energyEquation = "E_ij = 0.5 * k_ij * (d_ij - d0_ij)^2",
                .distanceEquation = "d_ij = ||r_i - r_j||",
                .distanceDerivativeEquation = "dE_ij/dd_ij = k_ij * (d_ij - d0_ij)",
                .cartesianGradientEquation =
                    "dE_ij/dr_i = k_ij * (d_ij - d0_ij) * (r_i - r_j) / d_ij",
                .reactionGradientEquation = "dE_ij/dr_j = -dE_ij/dr_i",
                .referenceDistancePolicy = "Chemistry-informed lookup keyed by atom symbols and "
                                           "bond order with a covalent-radius fallback",
                .springConstantPolicy =
                    "Bond-order-specific constants for an educational harmonic bond model",
                .bondOrderSpringConstants = std::move(bondOrderSpringConstants),
                .referenceDistanceLookupExamplesAngstrom =
                    std::move(referenceDistanceLookupExamples),
                .interpretation =
                    "Positive and negative Cartesian partial derivatives quantify how the "
                    "spring-bond energy changes under infinitesimal coordinate displacements of "
                    "each bonded atom in the current CID 4 conformer.",
            },
        .metadata = SpringBondPotentialMetadata{
            .atomCount = distanceMatrix.atomIds.size(),
            .bondedPairCount = bondedPairs.size(),
            .sourceDistanceMethod = distanceMatrix.method,
            .sourceAdjacencyMethod = adjacencyMatrix.method,
            .distanceUnits = distanceMatrix.metadata.units,
            .referenceDistanceUnits = "angstrom",
            .springConstantUnits = "relative spring units / angstrom^2",
            .springEnergyUnits = "relative spring units",
            .coordinatePartialDerivativeUnits = "relative spring units / angstrom",
            .referenceDistanceSourceCounts = std::move(sortedSourceCounts),
        }};
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

std::filesystem::path bondedDistanceOutputJsonPath(const std::filesystem::path& outputDirectory,
                                                   const std::filesystem::path& sourceFile,
                                                   const std::string_view distanceMethod)
{
    return outputDirectory / (sourceFile.stem().string() + "." + std::string(distanceMethod) +
                              ".bonded_distance_analysis.json");
}

std::filesystem::path bondAngleOutputJsonPath(const std::filesystem::path& outputDirectory,
                                              const std::filesystem::path& sourceFile,
                                              const std::string_view distanceMethod)
{
    return outputDirectory / (sourceFile.stem().string() + "." + std::string(distanceMethod) +
                              ".bond_angle_analysis.json");
}

std::filesystem::path
springBondPotentialOutputJsonPath(const std::filesystem::path& outputDirectory,
                                  const std::filesystem::path& sourceFile,
                                  const std::string_view distanceMethod)
{
    return outputDirectory / (sourceFile.stem().string() + "." + std::string(distanceMethod) +
                              ".spring_bond_potential_analysis.json");
}

std::filesystem::path bioactivityFilteredCsvPath(const std::filesystem::path& outputDirectory,
                                                 const std::filesystem::path& sourceFile)
{
    return outputDirectory / (sourceFile.stem().string() + ".ic50_pic50.csv");
}

std::filesystem::path bioactivitySummaryJsonPath(const std::filesystem::path& outputDirectory,
                                                 const std::filesystem::path& sourceFile)
{
    return outputDirectory / (sourceFile.stem().string() + ".ic50_pic50.summary.json");
}

std::filesystem::path bioactivityPlotSvgPath(const std::filesystem::path& outputDirectory,
                                             const std::filesystem::path& sourceFile)
{
    return outputDirectory / (sourceFile.stem().string() + ".ic50_pic50.svg");
}

std::filesystem::path posteriorBioactivityCsvPath(const std::filesystem::path& outputDirectory,
                                                  const std::filesystem::path& sourceFile)
{
    return outputDirectory /
           (sourceFile.stem().string() + ".activity_posterior_binary_evidence.csv");
}

std::filesystem::path
posteriorBioactivitySummaryJsonPath(const std::filesystem::path& outputDirectory,
                                    const std::filesystem::path& sourceFile)
{
    return outputDirectory / (sourceFile.stem().string() + ".activity_posterior.summary.json");
}

std::filesystem::path
binomialActivityDistributionCsvPath(const std::filesystem::path& outputDirectory,
                                    const std::filesystem::path& sourceFile)
{
    return outputDirectory / (sourceFile.stem().string() + ".activity_binomial_pmf.csv");
}

std::filesystem::path
binomialActivityDistributionSummaryJsonPath(const std::filesystem::path& outputDirectory,
                                            const std::filesystem::path& sourceFile)
{
    return outputDirectory / (sourceFile.stem().string() + ".activity_binomial.summary.json");
}

std::filesystem::path chiSquareActivityAidTypeCsvPath(const std::filesystem::path& outputDirectory,
                                                      const std::filesystem::path& sourceFile)
{
    return outputDirectory /
           (sourceFile.stem().string() + ".activity_aid_type_chi_square_contingency.csv");
}

std::filesystem::path
chiSquareActivityAidTypeSummaryJsonPath(const std::filesystem::path& outputDirectory,
                                        const std::filesystem::path& sourceFile)
{
    return outputDirectory /
           (sourceFile.stem().string() + ".activity_aid_type_chi_square.summary.json");
}

std::filesystem::path hillDoseResponseCsvPath(const std::filesystem::path& outputDirectory,
                                              const std::filesystem::path& sourceFile)
{
    return outputDirectory / (sourceFile.stem().string() + ".hill_dose_response.csv");
}

std::filesystem::path hillDoseResponseSummaryJsonPath(const std::filesystem::path& outputDirectory,
                                                      const std::filesystem::path& sourceFile)
{
    return outputDirectory / (sourceFile.stem().string() + ".hill_dose_response.summary.json");
}

std::filesystem::path hillDoseResponsePlotSvgPath(const std::filesystem::path& outputDirectory,
                                                  const std::filesystem::path& sourceFile)
{
    return outputDirectory / (sourceFile.stem().string() + ".hill_dose_response.svg");
}

std::filesystem::path activityValueStatisticsCsvPath(const std::filesystem::path& outputDirectory,
                                                     const std::filesystem::path& sourceFile)
{
    return outputDirectory / (sourceFile.stem().string() + ".activity_value_statistics.csv");
}

std::filesystem::path
activityValueStatisticsSummaryJsonPath(const std::filesystem::path& outputDirectory,
                                       const std::filesystem::path& sourceFile)
{
    return outputDirectory / (sourceFile.stem().string() + ".activity_value_statistics.summary.json");
}

std::filesystem::path
activityValueStatisticsPlotSvgPath(const std::filesystem::path& outputDirectory,
                                   const std::filesystem::path& sourceFile)
{
    return outputDirectory / (sourceFile.stem().string() + ".activity_value_statistics.svg");
}

std::filesystem::path gradientDescentCsvPath(const std::filesystem::path& outputDirectory,
                                             const std::filesystem::path& sourceFile)
{
    return outputDirectory /
           (sourceFile.stem().string() + ".mass_to_atomic_number_gradient_descent.csv");
}

std::filesystem::path gradientDescentSummaryJsonPath(const std::filesystem::path& outputDirectory,
                                                     const std::filesystem::path& sourceFile)
{
    return outputDirectory /
           (sourceFile.stem().string() + ".mass_to_atomic_number_gradient_descent.summary.json");
}

std::filesystem::path gradientDescentLossPlotSvgPath(const std::filesystem::path& outputDirectory,
                                                     const std::filesystem::path& sourceFile)
{
    return outputDirectory /
           (sourceFile.stem().string() + ".mass_to_atomic_number_gradient_descent.loss.svg");
}

std::filesystem::path gradientDescentFitPlotSvgPath(const std::filesystem::path& outputDirectory,
                                                    const std::filesystem::path& sourceFile)
{
    return outputDirectory /
           (sourceFile.stem().string() + ".mass_to_atomic_number_gradient_descent.fit.svg");
}

std::filesystem::path atomElementEntropyCsvPath(const std::filesystem::path& outputDirectory,
                                                const std::filesystem::path& sourceFile)
{
    return outputDirectory /
           (sourceFile.stem().string() + ".atom_element_entropy_proportions.csv");
}

std::filesystem::path atomElementEntropySummaryJsonPath(const std::filesystem::path& outputDirectory,
                                                        const std::filesystem::path& sourceFile)
{
    return outputDirectory /
           (sourceFile.stem().string() + ".atom_element_entropy.summary.json");
}

std::filesystem::path atomElementEntropyPlotSvgPath(const std::filesystem::path& outputDirectory,
                                                    const std::filesystem::path& sourceFile)
{
    return outputDirectory / (sourceFile.stem().string() + ".atom_element_entropy.svg");
}
} // namespace pubchem
