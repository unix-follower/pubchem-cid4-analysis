#include "analysis.hpp"

#include <numeric>

namespace pubchem
{
double averageOrZero(const std::vector<double>& values)
{
    if (values.empty())
    {
        return 0.0;
    }

    const double total = std::accumulate(values.begin(), values.end(), 0.0);
    return total / static_cast<double>(values.size());
}

std::filesystem::path outputDirectoryFor(const std::filesystem::path& dataDirectory)
{
    return dataDirectory / "out";
}

std::filesystem::path outputJsonPath(const std::filesystem::path& outputDirectory, const std::filesystem::path& sourceFile)
{
    return outputDirectory / (sourceFile.filename().string() + ".json");
}
}
