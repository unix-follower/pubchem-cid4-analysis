#pragma once

#include <cstdint>
#include <filesystem>
#include <optional>
#include <string>
#include <string_view>

#include <nlohmann/json.hpp>

namespace pubchem::cid4http {

struct ServerConfig {
    std::string host;
    std::uint16_t port;
    std::filesystem::path dataDir;
    std::filesystem::path certFile;
    std::filesystem::path keyFile;
    std::optional<std::string> keyPassword;
};

struct ApiResponse {
    int statusCode;
    std::string body;
    std::string contentType = "application/json";
};

std::filesystem::path resolveDataDir();
ServerConfig resolveServerConfig(const std::filesystem::path& dataDir,
                                 std::initializer_list<const char*> preferredHostEnvNames,
                                 std::initializer_list<const char*> preferredPortEnvNames);
ServerConfig resolveServerConfig(const std::filesystem::path& dataDir);

bool isSupportedConformerIndex(int index);
std::filesystem::path conformerPath(const std::filesystem::path& dataDir, int index);
std::filesystem::path structure2dPath(const std::filesystem::path& dataDir);
std::filesystem::path compoundPath(const std::filesystem::path& dataDir);

std::string loadJsonPayload(const std::filesystem::path& path);
std::string isoTimestampUtc();
ApiResponse routeApiRequest(std::string_view method,
                            std::string_view target,
                            const std::filesystem::path& dataDir,
                            std::string_view sourceLabel,
                            std::string_view transportName);

nlohmann::json healthPayload(std::string_view source, std::string_view message);
nlohmann::json pathwayFixture();
nlohmann::json bioactivityFixture();
nlohmann::json taxonomyFixture();

} // namespace pubchem::cid4http
