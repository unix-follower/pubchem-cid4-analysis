#pragma once

#include <cstddef>
#include <filesystem>
#include <string>
#include <vector>

namespace pubchem
{
struct AtomRecord
{
    int index;
    int bondCount;
    int charge;
    int implicitHydrogenCount;
    int totalHydrogenCount;
    int atomicNumber;
    std::string symbol;
    int valency;
    bool isAromatic;
    double mass;
    std::string hybridization;
};

struct AnalysisResult
{
    std::string sourceFile;
    double averageMolecularWeight;
    double exactMolecularMass;
    std::size_t moleculeCount;
    std::vector<AtomRecord> atoms;
};

double averageOrZero(const std::vector<double>& values);
std::filesystem::path outputDirectoryFor(const std::filesystem::path& dataDirectory);
std::filesystem::path outputJsonPath(const std::filesystem::path& outputDirectory, const std::filesystem::path& sourceFile);
}
