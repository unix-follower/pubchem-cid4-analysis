#include "cid4_scene.hpp"

#include <cstdlib>
#include <filesystem>
#include <format>
#include <iostream>
#include <stdexcept>
#include <string>
#include <string_view>
#include <vector>

#include <vulkan/vulkan.h>

namespace {
std::filesystem::path resolveDataDir()
{
    const auto* const dataDir = "DATA_DIR";
    if (const char* value = std::getenv(dataDir); value != nullptr && *value != '\0') {
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
    constexpr VkApplicationInfo applicationInfo{
        .sType = VK_STRUCTURE_TYPE_APPLICATION_INFO,
        .pNext = nullptr,
        .pApplicationName = "pubchem-cid4-vulkan-app",
        .applicationVersion = VK_MAKE_API_VERSION(0, 0, 1, 0),
        .pEngineName = "pubchem-cid4",
        .engineVersion = VK_MAKE_API_VERSION(0, 0, 1, 0),
        .apiVersion = VK_API_VERSION_1_0,
    };

    std::vector extensions = {VK_KHR_PORTABILITY_ENUMERATION_EXTENSION_NAME};

    const VkInstanceCreateInfo createInfo{
        .sType = VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO,
        .pNext = nullptr,
        .flags = VK_INSTANCE_CREATE_ENUMERATE_PORTABILITY_BIT_KHR,
        .pApplicationInfo = &applicationInfo,
        .enabledLayerCount = 0,
        .ppEnabledLayerNames = nullptr,
        .enabledExtensionCount = static_cast<uint32_t>(extensions.size()),
        .ppEnabledExtensionNames = extensions.data(),
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
} // namespace

int main()
{
    try {
        const std::filesystem::path jsonPath =
            resolveDataDir() / "Conformer3D_COMPOUND_CID_4(1).json";

        const pubchem::SceneData scene = pubchem::loadSceneData(jsonPath);
        printSceneSummary(scene);

        probeVulkanRuntime();
        return 0;
    }
    catch (const std::exception& error) {
        std::cerr << "app error: " << error.what() << "\n";
        return 1;
    }
}
