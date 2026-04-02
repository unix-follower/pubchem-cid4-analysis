#include "cid4_http.hpp"

#include <array>
#include <chrono>
#include <cstdlib>
#include <fstream>
#include <iomanip>
#include <sstream>
#include <stdexcept>

namespace pubchem::cid4http {
namespace {

constexpr std::array<const char*, 3> kRequiredDataFiles = {
    "COMPOUND_CID_4.json",
    "Structure2D_COMPOUND_CID_4.json",
    "Conformer3D_COMPOUND_CID_4(1).json",
};

std::optional<std::string> firstEnvValue(std::initializer_list<const char*> names)
{
    for (const char* name : names) {
        if (const char* value = std::getenv(name); value != nullptr && value[0] != '\0') {
            return std::string(value);
        }
    }

    return std::nullopt;
}

std::optional<std::string> firstEnvValue(const std::vector<const char*>& names)
{
    for (const char* name : names) {
        if (const char* value = std::getenv(name); value != nullptr && value[0] != '\0') {
            return std::string(value);
        }
    }

    return std::nullopt;
}

std::optional<std::uint16_t> firstPortValue(std::initializer_list<const char*> names)
{
    for (const char* name : names) {
        const auto value = firstEnvValue({name});
        if (!value.has_value()) {
            continue;
        }

        try {
            const auto parsed = std::stoul(*value);
            if (parsed > 0 && parsed <= 65535) {
                return static_cast<std::uint16_t>(parsed);
            }
        }
        catch (const std::exception&) {
        }
    }

    return std::nullopt;
}

std::optional<std::uint16_t> firstPortValue(const std::vector<const char*>& names)
{
    for (const char* name : names) {
        const auto value = firstEnvValue({name});
        if (!value.has_value()) {
            continue;
        }

        try {
            const auto parsed = std::stoul(*value);
            if (parsed > 0 && parsed <= 65535) {
                return static_cast<std::uint16_t>(parsed);
            }
        }
        catch (const std::exception&) {
        }
    }

    return std::nullopt;
}

bool hasRequiredFiles(const std::filesystem::path& directory)
{
    return std::filesystem::is_directory(directory) &&
           std::ranges::all_of(kRequiredDataFiles, [&directory](const char* fileName) {
               return std::filesystem::is_regular_file(directory / fileName);
           });
}

std::filesystem::path resolveDefaultDataDirCandidate()
{
#ifdef PUBCHEM_DEFAULT_DATA_DIR
    return std::filesystem::path(PUBCHEM_DEFAULT_DATA_DIR);
#else
    return std::filesystem::current_path() / "data";
#endif
}

ServerConfig resolveServerConfigFromCryptoSummary(const std::filesystem::path& dataDir,
                                                  const std::string& host,
                                                  std::uint16_t port)
{
    const auto summaryPath = dataDir / "out" / "crypto" / "cid4_crypto.summary.json";
    const auto summaryText = loadJsonPayload(summaryPath);
    const auto summary = nlohmann::json::parse(summaryText);

    const auto& pemPaths = summary.at("x509_and_pkcs12").at("pem_paths");
    const auto certFile =
        std::filesystem::path(pemPaths.at("certificate").get<std::string>()).lexically_normal();
    const auto keyFile =
        std::filesystem::path(pemPaths.at("private_key").get<std::string>()).lexically_normal();

    ServerConfig config{
        .host = host,
        .port = port,
        .dataDir = dataDir,
        .certFile = certFile,
        .keyFile = keyFile,
    };

    if (summary.contains("demo_password") && summary.at("demo_password").is_string()) {
        config.keyPassword = summary.at("demo_password").get<std::string>();
    }

    return config;
}

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
    std::vector<std::filesystem::path> candidates;
    if (const auto explicitDataDir = firstEnvValue({"DATA_DIR"}); explicitDataDir.has_value()) {
        candidates.emplace_back(*explicitDataDir);
    }

    candidates.push_back(resolveDefaultDataDirCandidate());
    candidates.push_back(std::filesystem::current_path() / "data");
    candidates.push_back(std::filesystem::current_path() / "../data");

    for (auto& candidate : candidates) {
        candidate = candidate.lexically_normal();
        if (hasRequiredFiles(candidate)) {
            return candidate;
        }
    }

    std::ostringstream error;
    error << "Unable to resolve the CID 4 data directory. Checked:";
    for (const auto& candidate : candidates) {
        error << ' ' << candidate.string();
    }

    throw std::runtime_error(error.str());
}

ServerConfig resolveServerConfig(const std::filesystem::path& dataDir)
{
    return resolveServerConfig(dataDir, {}, {});
}

ServerConfig resolveServerConfig(const std::filesystem::path& dataDir,
                                 std::initializer_list<const char*> preferredHostEnvNames,
                                 std::initializer_list<const char*> preferredPortEnvNames)
{
    std::vector<const char*> hostEnvNames(preferredHostEnvNames.begin(),
                                          preferredHostEnvNames.end());
    hostEnvNames.push_back("SERVER_HOST");

    std::vector<const char*> portEnvNames(preferredPortEnvNames.begin(),
                                          preferredPortEnvNames.end());
    portEnvNames.push_back("SERVER_PORT");
    portEnvNames.push_back("PORT");

    const auto host = firstEnvValue(hostEnvNames).value_or("0.0.0.0");
    const auto port = firstPortValue(portEnvNames).value_or(8443);

    const auto certFile = firstEnvValue({"TLS_CERT_FILE"});
    const auto keyFile = firstEnvValue({"TLS_KEY_FILE"});
    const auto keyPassword = firstEnvValue({"TLS_KEY_PASSWORD"});

    ServerConfig config{};
    if (certFile.has_value() || keyFile.has_value()) {
        if (!certFile.has_value() || !keyFile.has_value()) {
            throw std::runtime_error("Set both TLS_CERT_FILE and TLS_KEY_FILE, or neither to use "
                                     "the crypto summary fallback.");
        }

        config = ServerConfig{
            .host = host,
            .port = port,
            .dataDir = dataDir,
            .certFile = std::filesystem::path(*certFile).lexically_normal(),
            .keyFile = std::filesystem::path(*keyFile).lexically_normal(),
            .keyPassword = keyPassword,
        };
    }
    else {
        config = resolveServerConfigFromCryptoSummary(dataDir, host, port);
    }

    validateTlsFiles(config);
    return config;
}

bool isSupportedConformerIndex(int index)
{
    return index >= 1 && index <= 6;
}

std::filesystem::path conformerPath(const std::filesystem::path& dataDir, int index)
{
    if (!isSupportedConformerIndex(index)) {
        throw std::out_of_range("Unknown conformer " + std::to_string(index));
    }

    return dataDir / ("Conformer3D_COMPOUND_CID_4(" + std::to_string(index) + ").json");
}

std::filesystem::path structure2dPath(const std::filesystem::path& dataDir)
{
    return dataDir / "Structure2D_COMPOUND_CID_4.json";
}

std::filesystem::path compoundPath(const std::filesystem::path& dataDir)
{
    return dataDir / "COMPOUND_CID_4.json";
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
