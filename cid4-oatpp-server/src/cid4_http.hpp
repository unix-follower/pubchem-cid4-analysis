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
    bool tlsEnabled = false;
};

struct ApiResponse {
    int statusCode;
    std::string body;
    std::string contentType = "application/json";
};

std::filesystem::path resolveDataDir();
ServerConfig resolveServerConfig(const std::filesystem::path& dataDir);

bool isSupportedConformerIndex(int index);

std::string loadJsonPayload(const std::filesystem::path& path);
std::string isoTimestampUtc();
nlohmann::json healthPayload(std::string_view source, std::string_view message);
nlohmann::json pathwayFixture();
nlohmann::json bioactivityFixture();
nlohmann::json taxonomyFixture();

} // namespace pubchem::cid4http
