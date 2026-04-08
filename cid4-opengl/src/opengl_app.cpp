#include "cid4_scene.hpp"

#include <cstdlib>
#include <filesystem>
#include <iostream>
#include <stdexcept>
#include <string>
#include <string_view>

#if PUBCHEM_OPENGL_RUNTIME_AVAILABLE
#define GLFW_INCLUDE_NONE
#include <GLFW/glfw3.h>

#if defined(__APPLE__)
#define GL_SILENCE_DEPRECATION
#include <OpenGL/gl3.h>
#else
#include <GL/gl.h>
#endif
#endif

namespace {
struct OpenGlAppOptions {
    std::filesystem::path jsonFile = "Conformer3D_COMPOUND_CID_4(1).json";
    bool skipRuntimeProbe = false;
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
    output << "Usage: opengl_app [--json <file>] [--skip-runtime-probe]\n";
}

OpenGlAppOptions parseArguments(int argc, char* argv[])
{
    OpenGlAppOptions options;

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
            options.jsonFile = readValue("--json");
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

void printSceneSummary(const pubchem::SceneData& scene)
{
    std::cout << "CID " << scene.compoundId << " scene loaded from " << scene.sourceFile << "\n";
    std::cout << "Atoms: " << scene.atoms.size() << ", Bonds: " << scene.bonds.size() << "\n";
    std::cout << "Coordinates: " << (scene.hasZCoordinates ? "3D" : "2D") << "\n";
    std::cout << "Bounds min: (" << scene.bounds.minimum[0] << ", " << scene.bounds.minimum[1]
              << ", " << scene.bounds.minimum[2] << ")\n";
    std::cout << "Bounds max: (" << scene.bounds.maximum[0] << ", " << scene.bounds.maximum[1]
              << ", " << scene.bounds.maximum[2] << ")\n";
}

#if PUBCHEM_OPENGL_RUNTIME_AVAILABLE
class GlfwGuard {
  public:
    GlfwGuard()
    {
        if (glfwInit() != GLFW_TRUE) {
            throw std::runtime_error("glfwInit failed. OpenGL runtime may be unavailable.");
        }
    }

    ~GlfwGuard()
    {
        glfwTerminate();
    }

    GlfwGuard(const GlfwGuard&) = delete;
    GlfwGuard& operator=(const GlfwGuard&) = delete;
};

void configureWindowHints()
{
    glfwWindowHint(GLFW_VISIBLE, GLFW_FALSE);
    glfwWindowHint(GLFW_CONTEXT_VERSION_MAJOR, 3);
    glfwWindowHint(GLFW_CONTEXT_VERSION_MINOR, 3);
    glfwWindowHint(GLFW_OPENGL_PROFILE, GLFW_OPENGL_CORE_PROFILE);
#if defined(__APPLE__)
    glfwWindowHint(GLFW_OPENGL_FORWARD_COMPAT, GLFW_TRUE);
#endif
}

std::string glString(GLenum name)
{
    const GLubyte* value = glGetString(name);
    if (value == nullptr) {
        return "unknown";
    }

    return reinterpret_cast<const char*>(value);
}

void probeOpenGlRuntime()
{
    GlfwGuard glfwGuard;
    configureWindowHints();

    GLFWwindow* window = glfwCreateWindow(640, 480, "pubchem-cid4-opengl-probe", nullptr, nullptr);
    if (window == nullptr) {
        throw std::runtime_error(
            "glfwCreateWindow failed. A usable OpenGL context is unavailable.");
    }

    glfwMakeContextCurrent(window);
    glViewport(0, 0, 640, 480);
    glClearColor(0.08F, 0.10F, 0.14F, 1.0F);
    glClear(GL_COLOR_BUFFER_BIT);
    glfwSwapBuffers(window);

    std::cout << "OpenGL runtime probe succeeded.\n";
    std::cout << "Vendor: " << glString(GL_VENDOR) << "\n";
    std::cout << "Renderer: " << glString(GL_RENDERER) << "\n";
    std::cout << "Version: " << glString(GL_VERSION) << "\n";

    glfwDestroyWindow(window);
}
#endif
} // namespace

int main(int argc, char* argv[])
{
    try {
        const OpenGlAppOptions options = parseArguments(argc, argv);
        const std::filesystem::path jsonPath = resolveDataDir() / options.jsonFile;

        const pubchem::SceneData scene = pubchem::loadSceneData(jsonPath);
        printSceneSummary(scene);

#if PUBCHEM_OPENGL_RUNTIME_AVAILABLE
        if (options.skipRuntimeProbe) {
            std::cout << "Skipping OpenGL runtime probe by request. Geometry bootstrap compiled "
                         "successfully.\n";
            return 0;
        }

        probeOpenGlRuntime();
        return 0;
#else
        std::cout << "OpenGL and GLFW were not both detected at configure time. "
                     "This build provides the geometry-loading bootstrap only.\n";
        std::cout
            << "Install GLFW development files and reconfigure CMake to enable runtime probing.\n";
        return 0;
#endif
    }
    catch (const std::exception& error) {
        std::cerr << "opengl_app error: " << error.what() << "\n";
        return 1;
    }
}
