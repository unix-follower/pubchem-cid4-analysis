#include "cid4_http.hpp"
#include "app_utils.hpp"

#include <algorithm>
#include <array>
#include <chrono>
#include <cstdlib>
#include <fstream>
#include <iomanip>
#include <limits>
#include <sstream>
#include <stdexcept>

namespace pubchem::cid4http {
namespace {
std::string_view requestPath(std::string_view target)
{
    const auto queryOffset = target.find('?');
    if (queryOffset == std::string_view::npos) {
        return target;
    }

    return target.substr(0, queryOffset);
}

std::optional<std::string_view> queryValue(std::string_view target, std::string_view key)
{
    const auto queryOffset = target.find('?');
    if (queryOffset == std::string_view::npos || queryOffset + 1 >= target.size()) {
        return std::nullopt;
    }

    auto query = target.substr(queryOffset + 1);
    while (!query.empty()) {
        const auto separator = query.find('&');
        const auto part = separator == std::string_view::npos ? query : query.substr(0, separator);
        const auto equals = part.find('=');
        const auto candidateKey = equals == std::string_view::npos ? part : part.substr(0, equals);
        if (candidateKey == key) {
            if (equals == std::string_view::npos || equals + 1 >= part.size()) {
                return std::string_view{};
            }

            return part.substr(equals + 1);
        }

        if (separator == std::string_view::npos) {
            break;
        }
        query.remove_prefix(separator + 1);
    }

    return std::nullopt;
}

ApiResponse jsonResponse(int statusCode, const nlohmann::json& payload)
{
    return ApiResponse{.statusCode = statusCode, .body = payload.dump()};
}

ApiResponse textResponse(int statusCode, std::string payload, std::string contentType)
{
    return ApiResponse{
        .statusCode = statusCode,
        .body = std::move(payload),
        .contentType = std::move(contentType),
    };
}

std::optional<int> parseConformerIndex(std::string_view value)
{
    if (value.empty()) {
        return std::nullopt;
    }

    try {
        std::size_t consumed = 0;
        const auto parsed = std::stoi(std::string(value), &consumed);
        if (consumed != value.size()) {
            return std::nullopt;
        }

        return parsed;
    }
    catch (const std::exception&) {
        return std::nullopt;
    }
}

// ServerConfig resolveServerConfigFromCryptoSummary(const std::filesystem::path& dataDir,
//                                                   const std::string& host,
//                                                   std::uint16_t port)
// {
//     const auto summaryPath = dataDir / "out" / "crypto" / "cid4_crypto.summary.json";
//     const auto summaryText = loadJsonPayload(summaryPath);
//     const auto summary = nlohmann::json::parse(summaryText);

//     const auto& pemPaths = summary.at("x509_and_pkcs12").at("pem_paths");
//     const auto certFile =
//         std::filesystem::path(pemPaths.at("certificate").get<std::string>()).lexically_normal();
//     const auto keyFile =
//         std::filesystem::path(pemPaths.at("private_key").get<std::string>()).lexically_normal();

//     ServerConfig config{
//         .host = host,
//         .port = port,
//         .dataDir = dataDir,
//         .certFile = certFile,
//         .keyFile = keyFile,
//     };

//     if (summary.contains("demo_password") && summary.at("demo_password").is_string()) {
//         config.keyPassword = summary.at("demo_password").get<std::string>();
//     }

//     return config;
// }

void validateTlsFiles(const ServerConfig& config)
{
    if (!std::filesystem::is_regular_file(config.certFile)) {
        throw std::runtime_error("TLS certificate file does not exist: " +
                                 config.certFile.string());
    }

    if (!std::filesystem::is_regular_file(config.keyFile)) {
        throw std::runtime_error("TLS private key file does not exist: " + config.keyFile.string());
    }
}

} // namespace

std::filesystem::path resolveDataDir()
{
    if (const auto value = app::utils::env::getEnvValue("DATA_DIR"); value.has_value()) {
        return std::string(value.value());
    }

    throw std::runtime_error("DATA_DIR env variable is not set");
}

ServerConfig resolveServerConfig(const std::filesystem::path& dataDir)
{
    const auto host = app::utils::env::getEnvValue("SERVER_HOST").value_or("0.0.0.0");
    const auto port = app::utils::net::getServerPort();

    const auto certFile = app::utils::env::getEnvValue("TLS_CERT_FILE");
    const auto keyFile = app::utils::env::getEnvValue("TLS_KEY_FILE");
    const auto keyPassword = app::utils::env::getEnvValue("TLS_KEY_PASSWORD");

    ServerConfig config{
        .host = host,
        .port = port,
        .dataDir = dataDir,
    };
    if (certFile.has_value() && keyFile.has_value()) {
        config.certFile = std::filesystem::path(*certFile).lexically_normal();
        config.keyFile = std::filesystem::path(*keyFile).lexically_normal();
        config.keyPassword = keyPassword;
        config.tlsEnabled = true;
        validateTlsFiles(config);
    }

    return config;
}

bool isSupportedConformerIndex(int index)
{
    return index >= 1 && index <= 6;
}

std::string loadJsonPayload(const std::filesystem::path& path)
{
    std::ifstream input(path);
    if (!input) {
        throw std::runtime_error("Missing JSON payload " + path.filename().string());
    }

    std::ostringstream buffer;
    buffer << input.rdbuf();
    return buffer.str();
}

std::string isoTimestampUtc()
{
    const auto now = std::chrono::system_clock::now();
    const auto time = std::chrono::system_clock::to_time_t(now);
    std::tm utcTime{};
    gmtime_r(&time, &utcTime);

    const auto fractional = std::chrono::duration_cast<std::chrono::milliseconds>(
        now.time_since_epoch() % std::chrono::seconds(1));

    std::ostringstream output;
    output << std::put_time(&utcTime, "%Y-%m-%dT%H:%M:%S") << '.' << std::setw(3)
           << std::setfill('0') << fractional.count() << 'Z';
    return output.str();
}

nlohmann::json healthPayload(std::string_view source, std::string_view message)
{
    return {
        {"message", std::string(message)},
        {"source", std::string(source)},
        {"timestamp", isoTimestampUtc()},
    };
}

nlohmann::json pathwayFixture()
{
    return {
        {"graph",
         {
             {"id", "glutathione-metabolism-iii"},
             {"title", "Glutathione Metabolism III"},
             {"directed", true},
             {"nodes",
              {{{"id", "step-1"}, {"label", "Import precursor"}},
               {{"id", "step-2"}, {"label", "Activate cysteine"}},
               {{"id", "step-3"}, {"label", "Ligate glutamate"}},
               {{"id", "step-4"}, {"label", "Add glycine"}},
               {{"id", "step-5"}, {"label", "Reduce intermediate"}},
               {{"id", "step-6"}, {"label", "Export product"}}}},
             {"edges",
              {{{"id", "step-1-2"}, {"source", "step-1"}, {"target", "step-2"}},
               {{"id", "step-2-3"}, {"source", "step-2"}, {"target", "step-3"}},
               {{"id", "step-3-4"}, {"source", "step-3"}, {"target", "step-4"}},
               {{"id", "step-3-5"}, {"source", "step-3"}, {"target", "step-5"}},
               {{"id", "step-4-6"}, {"source", "step-4"}, {"target", "step-6"}},
               {{"id", "step-5-6"}, {"source", "step-5"}, {"target", "step-6"}}}},
         }},
    };
}

nlohmann::json bioactivityFixture()
{
    return {
        {"records",
         {{{"aid", 743069}, {"assay", "Tox21 ER-alpha agonist"}, {"activityValue", 355.1}},
          {{"aid", 743070}, {"assay", "Tox21 ER-alpha antagonist"}, {"activityValue", 18.2}},
          {{"aid", 651820}, {"assay", "NCI growth inhibition"}, {"activityValue", 92.4}},
          {{"aid", 540317}, {"assay", "Cell viability counter-screen"}, {"activityValue", 112.7}},
          {{"aid", 504332}, {"assay", "ChEMBL potency panel"}, {"activityValue", 8.6}},
          {{"aid", 720699}, {"assay", "Nuclear receptor confirmation"}, {"activityValue", 61.9}},
          {{"aid", 743053}, {"assay", "Tox21 luciferase artifact"}, {"activityValue", 140.4}},
          {{"aid", 743122}, {"assay", "Dose-response validation"}, {"activityValue", 28.8}},
          {{"aid", 1259368}, {"assay", "Secondary pharmacology"}, {"activityValue", 4.2}},
          {{"aid", 1345073}, {"assay", "Metabolism pathway screen"}, {"activityValue", 205.5}}}},
    };
}

nlohmann::json taxonomyFixture()
{
    return {
        {"organisms",
         {{{"taxonomyId", 9913}, {"sourceOrganism", "Bos taurus"}},
          {{"taxonomyId", 9913}, {"sourceOrganism", "Bos taurus"}},
          {{"taxonomyId", 9823}, {"sourceOrganism", "Sus scrofa"}},
          {{"taxonomyId", 9031}, {"sourceOrganism", "Gallus gallus"}},
          {{"taxonomyId", 9031}, {"sourceOrganism", "Gallus gallus"}},
          {{"taxonomyId", 9103}, {"sourceOrganism", "Meleagris gallopavo"}},
          {{"taxonomyId", 9986}, {"sourceOrganism", "Oryctolagus cuniculus"}},
          {{"taxonomyId", 9685}, {"sourceOrganism", "Felis catus"}}}},
    };
}

} // namespace pubchem::cid4http
