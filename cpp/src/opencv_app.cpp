#include "cid4_opencv.hpp"

#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <ranges>
#include <stdexcept>
#include <string>
#include <string_view>
#include <vector>

#if PUBCHEM_OPENCV_RUNTIME_AVAILABLE
#include <opencv2/core.hpp>
#include <opencv2/imgcodecs.hpp>
#include <opencv2/imgproc.hpp>
#endif

namespace {
struct OpenCvAppOptions {
    std::string task = "segment-2d";
    std::filesystem::path imageFile = "1-Amino-2-propanol.png";
    std::filesystem::path jsonFile = "Structure2D_COMPOUND_CID_4.json";
    std::filesystem::path outputDir = "out/opencv";
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
    output << "Usage: opencv_app [--task <segment-2d|compare-conformers|overlay-structure>]"
           << " [--image <file>] [--json <file>] [--output-dir <dir>]\n";
}

OpenCvAppOptions parseArguments(int argc, char* argv[])
{
    OpenCvAppOptions options;

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

        if (argument == "--task") {
            options.task = readValue("--task");
            continue;
        }

        if (argument == "--image") {
            options.imageFile = readValue("--image");
            continue;
        }

        if (argument == "--json") {
            options.jsonFile = readValue("--json");
            continue;
        }

        if (argument == "--output-dir") {
            options.outputDir = readValue("--output-dir");
            continue;
        }

        throw std::invalid_argument("Unknown argument: " + argument);
    }

    return options;
}

void writeJson(const std::filesystem::path& outputPath, const nlohmann::json& payload)
{
    std::ofstream output(outputPath);
    if (!output) {
        throw std::runtime_error("Unable to write output file: " + outputPath.string());
    }

    output << payload.dump(2) << '\n';
}

#if PUBCHEM_OPENCV_RUNTIME_AVAILABLE
cv::Scalar colorForElement(const std::string& elementSymbol)
{
    if (elementSymbol == "O") {
        return cv::Scalar(48, 48, 220);
    }

    if (elementSymbol == "N") {
        return cv::Scalar(220, 96, 48);
    }

    if (elementSymbol == "C") {
        return cv::Scalar(80, 80, 80);
    }

    return cv::Scalar(180, 180, 180);
}

void runSegment2d(const std::filesystem::path& imagePath, const std::filesystem::path& outputDir)
{
    const cv::Mat source = cv::imread(imagePath.string(), cv::IMREAD_COLOR);
    if (source.empty()) {
        throw std::runtime_error("Unable to read image: " + imagePath.string());
    }

    cv::Mat grayscale;
    cv::cvtColor(source, grayscale, cv::COLOR_BGR2GRAY);

    cv::Mat thresholded;
    cv::threshold(grayscale, thresholded, 0, 255, cv::THRESH_BINARY_INV | cv::THRESH_OTSU);

    cv::Mat opened;
    const cv::Mat kernel = cv::getStructuringElement(cv::MORPH_RECT, cv::Size(3, 3));
    cv::morphologyEx(thresholded, opened, cv::MORPH_OPEN, kernel);

    std::vector<std::vector<cv::Point>> contours;
    cv::findContours(opened.clone(), contours, cv::RETR_EXTERNAL, cv::CHAIN_APPROX_SIMPLE);
    if (contours.empty()) {
        throw std::runtime_error("No contours detected in 2D structure image");
    }

    const auto largestContour = std::ranges::max_element(
        contours, {}, [](const auto& contour) { return cv::contourArea(contour); });
    const cv::Rect boundingBox = cv::boundingRect(*largestContour);
    const cv::Mat cropped = source(boundingBox).clone();

    cv::imwrite((outputDir / "segment-2d-threshold.png").string(), thresholded);
    cv::imwrite((outputDir / "segment-2d-opened.png").string(), opened);
    cv::imwrite((outputDir / "segment-2d-cropped.png").string(), cropped);

    writeJson(outputDir / "segment-2d-summary.json",
              {
                  {"sourceImage", imagePath.filename().string()},
                  {"contourCount", contours.size()},
                  {"boundingBox",
                   {{"x", boundingBox.x},
                    {"y", boundingBox.y},
                    {"width", boundingBox.width},
                    {"height", boundingBox.height}}},
                  {"outputImages",
                   {"segment-2d-threshold.png", "segment-2d-opened.png", "segment-2d-cropped.png"}},
              });
}

void runCompareConformers(const std::filesystem::path& dataDir,
                          const std::filesystem::path& outputDir)
{
    const std::vector<std::filesystem::path> paths = pubchem::defaultConformerImagePaths(dataDir);
    if (paths.empty()) {
        throw std::runtime_error("No conformer images were configured");
    }

    std::vector<cv::Mat> images;
    images.reserve(paths.size());
    for (const auto& path : paths) {
        cv::Mat image = cv::imread(path.string(), cv::IMREAD_COLOR);
        if (image.empty()) {
            throw std::runtime_error("Unable to read conformer image: " + path.string());
        }

        images.push_back(std::move(image));
    }

    const cv::Size referenceSize = images.front().size();
    std::vector<pubchem::ConformerImagePairScore> pairScores;
    pubchem::ConformerImagePairScore strongestDifference{};
    cv::Mat strongestDiff;

    for (std::size_t leftIndex = 0; leftIndex < images.size(); ++leftIndex) {
        cv::Mat leftResized;
        cv::resize(images[leftIndex], leftResized, referenceSize);
        for (std::size_t rightIndex = leftIndex + 1; rightIndex < images.size(); ++rightIndex) {
            cv::Mat rightResized;
            cv::resize(images[rightIndex], rightResized, referenceSize);

            cv::Mat diff;
            cv::absdiff(leftResized, rightResized, diff);
            const cv::Scalar meanDiff = cv::mean(diff);
            const double score = (meanDiff[0] + meanDiff[1] + meanDiff[2]) / 3.0;

            pairScores.push_back(pubchem::ConformerImagePairScore{
                .leftImage = paths[leftIndex].filename().string(),
                .rightImage = paths[rightIndex].filename().string(),
                .meanAbsoluteDifference = score,
            });

            if (strongestDiff.empty() || score > strongestDifference.meanAbsoluteDifference) {
                strongestDifference = pairScores.back();
                strongestDiff = diff;
            }
        }
    }

    std::ranges::sort(pairScores, {}, &pubchem::ConformerImagePairScore::meanAbsoluteDifference);
    std::ranges::reverse(pairScores);

    if (!strongestDiff.empty()) {
        cv::imwrite((outputDir / "compare-conformers-strongest-diff.png").string(), strongestDiff);
    }

    nlohmann::json summary = pubchem::toJson(pairScores);
    if (!pairScores.empty()) {
        summary["mostDifferentPair"] = {
            {"leftImage", pairScores.front().leftImage},
            {"rightImage", pairScores.front().rightImage},
            {"meanAbsoluteDifference", pairScores.front().meanAbsoluteDifference},
        };
    }
    writeJson(outputDir / "compare-conformers-summary.json", summary);
}

void runOverlayStructure(const std::filesystem::path& jsonPath,
                         const std::filesystem::path& imagePath,
                         const std::filesystem::path& outputDir)
{
    const pubchem::SceneData scene = pubchem::loadSceneData(jsonPath);
    const cv::Mat background = cv::imread(imagePath.string(), cv::IMREAD_COLOR);
    if (background.empty()) {
        throw std::runtime_error("Unable to read image: " + imagePath.string());
    }

    cv::Mat annotated = background.clone();
    const pubchem::OverlayLayout layout =
        pubchem::buildOverlayLayout(scene, background.cols, background.rows, 24);

    for (const pubchem::OverlayBondSegment& bond : layout.bonds) {
        cv::line(annotated,
                 cv::Point(static_cast<int>(std::lround(bond.start[0])),
                           static_cast<int>(std::lround(bond.start[1]))),
                 cv::Point(static_cast<int>(std::lround(bond.end[0])),
                           static_cast<int>(std::lround(bond.end[1]))),
                 cv::Scalar(40, 160, 40),
                 std::max(1, bond.order + 1),
                 cv::LINE_AA);
    }

    for (const pubchem::OverlayAtomPoint& atom : layout.atoms) {
        const cv::Point center(static_cast<int>(std::lround(atom.position[0])),
                               static_cast<int>(std::lround(atom.position[1])));
        cv::circle(
            annotated, center, 8, colorForElement(atom.elementSymbol), cv::FILLED, cv::LINE_AA);
        cv::putText(annotated,
                    atom.elementSymbol,
                    center + cv::Point(10, -10),
                    cv::FONT_HERSHEY_SIMPLEX,
                    0.45,
                    cv::Scalar(24, 24, 24),
                    1,
                    cv::LINE_AA);
    }

    cv::imwrite((outputDir / "overlay-structure.png").string(), annotated);
    writeJson(outputDir / "overlay-structure-summary.json",
              {
                  {"sourceImage", imagePath.filename().string()},
                  {"sourceJson", jsonPath.filename().string()},
                  {"layout", pubchem::toJson(layout)},
                  {"outputImage", "overlay-structure.png"},
              });
}
#endif
} // namespace

int main(int argc, char* argv[])
{
    try {
        const OpenCvAppOptions options = parseArguments(argc, argv);
        const std::filesystem::path dataDir = resolveDataDir();
        const std::filesystem::path outputDir = dataDir / options.outputDir;
        std::filesystem::create_directories(outputDir);

#if PUBCHEM_OPENCV_RUNTIME_AVAILABLE
        if (options.task == "segment-2d") {
            runSegment2d(dataDir / options.imageFile, outputDir);
        }
        else if (options.task == "compare-conformers") {
            runCompareConformers(dataDir, outputDir);
        }
        else if (options.task == "overlay-structure") {
            runOverlayStructure(dataDir / options.jsonFile, dataDir / options.imageFile, outputDir);
        }
        else {
            throw std::invalid_argument("Unknown task: " + options.task);
        }

        std::cout << "OpenCV task completed: " << options.task << "\n";
        std::cout << "Outputs written to: " << outputDir << "\n";
        return 0;
#else
        const pubchem::SceneData scene = pubchem::loadSceneData(dataDir / options.jsonFile);
        std::cout << "OpenCV was not detected at configure time. Building in stub mode only.\n";
        std::cout << "Requested task: " << options.task << "\n";
        std::cout << "Validated scene source: " << scene.sourceFile << " with "
                  << scene.atoms.size() << " atoms and " << scene.bonds.size() << " bonds.\n";
        std::cout << "Enable the vcpkg manifest feature 'opencv-app' and reconfigure CMake to turn "
                     "on image workflows.\n";
        return 0;
#endif
    }
    catch (const std::exception& error) {
        std::cerr << "opencv_app error: " << error.what() << "\n";
        return 1;
    }
}
