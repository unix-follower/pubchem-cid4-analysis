#include "cid4_scene.hpp"

#include <cstdlib>
#include <filesystem>
#include <format>
#include <iostream>
#include <stdexcept>
#include <string>
#include <string_view>

#define GLFW_INCLUDE_NONE
#include <GLFW/glfw3.h>

#ifdef __APPLE__
#define GL_SILENCE_DEPRECATION
#include <OpenGL/gl3.h>
#else
#include <GL/gl.h>
#endif

namespace {
std::filesystem::path resolveDataDir()
{
    const auto* const dataDir = "DATA_DIR";
    if (const char* value = std::getenv("DATA_DIR"); value != nullptr && *value != '\0') {
        return {value};
    }

    throw std::runtime_error(std::format("The env variable {} is not set", dataDir));
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
#ifdef __APPLE__
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
} // namespace

int main()
{
    try {
        const std::filesystem::path jsonPath =
            resolveDataDir() / "Conformer3D_COMPOUND_CID_4(1).json";

        const pubchem::SceneData scene = pubchem::loadSceneData(jsonPath);
        printSceneSummary(scene);
        probeOpenGlRuntime();
        return 0;
    }
    catch (const std::exception& error) {
        std::cerr << "opengl_app error: " << error.what() << "\n";
        return 1;
    }
}
