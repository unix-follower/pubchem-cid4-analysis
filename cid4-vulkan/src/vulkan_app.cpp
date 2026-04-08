#include "cid4_scene.hpp"

#include <cstdlib>
#include <filesystem>
#include <iostream>
#include <stdexcept>
#include <string>
#include <string_view>
#include <vector>

#if PUBCHEM_VULKAN_RUNTIME_AVAILABLE
#include <vulkan/vulkan.h>
#endif

namespace {
struct VulkanAppOptions {
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
    output << "Usage: vulkan_app [--json <file>] [--skip-runtime-probe]\n";
}

VulkanAppOptions parseArguments(int argc, char* argv[])
{
    VulkanAppOptions options;

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

#if PUBCHEM_VULKAN_RUNTIME_AVAILABLE
std::vector<std::string> enumeratePhysicalDeviceNames(VkInstance instance)
{
    uint32_t physicalDeviceCount = 0;
    const VkResult countResult =
        vkEnumeratePhysicalDevices(instance, &physicalDeviceCount, nullptr);
    if (countResult != VK_SUCCESS) {
        throw std::runtime_error("vkEnumeratePhysicalDevices failed while counting devices");
    }

    std::vector<VkPhysicalDevice> physicalDevices(physicalDeviceCount);
    const VkResult enumerateResult =
        vkEnumeratePhysicalDevices(instance, &physicalDeviceCount, physicalDevices.data());
    if (enumerateResult != VK_SUCCESS) {
        throw std::runtime_error("vkEnumeratePhysicalDevices failed while loading devices");
    }

    std::vector<std::string> deviceNames;
    deviceNames.reserve(physicalDevices.size());
    for (VkPhysicalDevice physicalDevice : physicalDevices) {
        VkPhysicalDeviceProperties properties{};
        vkGetPhysicalDeviceProperties(physicalDevice, &properties);
        deviceNames.emplace_back(properties.deviceName);
    }

    return deviceNames;
}

void probeVulkanRuntime()
{
    const VkApplicationInfo applicationInfo{
        .sType = VK_STRUCTURE_TYPE_APPLICATION_INFO,
        .pNext = nullptr,
        .pApplicationName = "pubchem-cid4-vulkan-app",
        .applicationVersion = VK_MAKE_API_VERSION(0, 0, 1, 0),
        .pEngineName = "pubchem-cid4",
        .engineVersion = VK_MAKE_API_VERSION(0, 0, 1, 0),
        .apiVersion = VK_API_VERSION_1_0,
    };

    const VkInstanceCreateInfo createInfo{
        .sType = VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO,
        .pNext = nullptr,
        .flags = 0,
        .pApplicationInfo = &applicationInfo,
        .enabledLayerCount = 0,
        .ppEnabledLayerNames = nullptr,
        .enabledExtensionCount = 0,
        .ppEnabledExtensionNames = nullptr,
    };

    VkInstance instance = VK_NULL_HANDLE;
    const VkResult createResult = vkCreateInstance(&createInfo, nullptr, &instance);
    if (createResult != VK_SUCCESS) {
        throw std::runtime_error("vkCreateInstance failed. Vulkan runtime may be unavailable.");
    }

    const std::vector<std::string> deviceNames = enumeratePhysicalDeviceNames(instance);
    std::cout << "Vulkan runtime probe succeeded. Physical devices: " << deviceNames.size() << "\n";
    for (const std::string& deviceName : deviceNames) {
        std::cout << "  - " << deviceName << "\n";
    }

    vkDestroyInstance(instance, nullptr);
}
#endif
} // namespace

int main(int argc, char* argv[])
{
    try {
        const VulkanAppOptions options = parseArguments(argc, argv);
        const std::filesystem::path jsonPath = resolveDataDir() / options.jsonFile;

        const pubchem::SceneData scene = pubchem::loadSceneData(jsonPath);
        printSceneSummary(scene);

#if PUBCHEM_VULKAN_RUNTIME_AVAILABLE
        if (options.skipRuntimeProbe) {
            std::cout << "Skipping Vulkan runtime probe by request. Geometry bootstrap compiled "
                         "successfully.\n";
            return 0;
        }

        probeVulkanRuntime();
        return 0;
#else
        std::cout << "Vulkan SDK or loader was not detected at configure time. "
                     "This build provides the geometry-loading bootstrap only.\n";
        std::cout << "Install a Vulkan SDK and reconfigure CMake to enable runtime probing.\n";
        return 0;
#endif
    }
    catch (const std::exception& error) {
        std::cerr << "vulkan_app error: " << error.what() << "\n";
        return 1;
    }
}
