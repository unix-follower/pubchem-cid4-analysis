#include "cid4_http.hpp"

#include <drogon/drogon.h>

#include <openssl/err.h>
#include <openssl/pem.h>

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <exception>
#include <filesystem>
#include <iostream>
#include <memory>
#include <optional>
#include <stdexcept>
#include <string>
#include <string_view>
#include <sys/stat.h>
#include <system_error>
#include <unistd.h>

namespace {

std::string hostOverride(int argc, char** argv)
{
    for (int index = 1; index < argc; ++index) {
        if (std::string_view(argv[index]) == "--host" && index + 1 < argc) {
            return argv[index + 1];
        }
    }

    return {};
}

std::optional<std::uint16_t> portOverride(int argc, char** argv)
{
    for (int index = 1; index < argc; ++index) {
        if (std::string_view(argv[index]) == "--port" && index + 1 < argc) {
            try {
                const auto parsed = std::stoul(argv[index + 1]);
                if (parsed > 0 && parsed <= 65535) {
                    return static_cast<std::uint16_t>(parsed);
                }
            }
            catch (const std::exception&) {
                return std::nullopt;
            }
        }
    }

    return std::nullopt;
}

std::string currentOpenSslError()
{
    const auto errorCode = ERR_get_error();
    if (errorCode == 0) {
        return "unknown OpenSSL error";
    }

    char buffer[256]{};
    ERR_error_string_n(errorCode, buffer, sizeof(buffer));
    return buffer;
}

class TemporaryKeyFile {
  public:
    explicit TemporaryKeyFile(const pubchem::cid4http::ServerConfig& config)
    {
        if (!config.keyPassword.has_value()) {
            path_ = config.keyFile;
            return;
        }

        path_ = decryptPrivateKey(config.keyFile, *config.keyPassword);
        ownsFile_ = true;
    }

    ~TemporaryKeyFile()
    {
        if (!ownsFile_) {
            return;
        }

        std::error_code error;
        std::filesystem::remove(path_, error);
    }

    const std::filesystem::path& path() const
    {
        return path_;
    }

  private:
    using FileHandle = std::unique_ptr<FILE, decltype(&std::fclose)>;
    using KeyHandle = std::unique_ptr<EVP_PKEY, decltype(&EVP_PKEY_free)>;

    static std::filesystem::path decryptPrivateKey(const std::filesystem::path& encryptedKeyPath,
                                                   const std::string& password)
    {
        FileHandle input(std::fopen(encryptedKeyPath.c_str(), "r"), &std::fclose);
        if (!input) {
            throw std::runtime_error("Unable to open TLS private key " + encryptedKeyPath.string());
        }

        ERR_clear_error();
        KeyHandle key(
            PEM_read_PrivateKey(input.get(), nullptr, nullptr, const_cast<char*>(password.c_str())),
            &EVP_PKEY_free);
        if (!key) {
            throw std::runtime_error("Unable to decrypt TLS private key " +
                                     encryptedKeyPath.string() + ": " + currentOpenSslError());
        }

        char fileTemplate[] = "/tmp/cid4-drogon-key-XXXXXX.pem";
        const int fileDescriptor = mkstemps(fileTemplate, 4);
        if (fileDescriptor == -1) {
            throw std::runtime_error("Unable to create temporary TLS key file");
        }

        if (fchmod(fileDescriptor, S_IRUSR | S_IWUSR) != 0) {
            close(fileDescriptor);
            std::remove(fileTemplate);
            throw std::runtime_error("Unable to secure temporary TLS key file permissions");
        }

        FileHandle output(fdopen(fileDescriptor, "w"), &std::fclose);
        if (!output) {
            close(fileDescriptor);
            std::remove(fileTemplate);
            throw std::runtime_error("Unable to open temporary TLS key file stream");
        }

        ERR_clear_error();
        if (PEM_write_PrivateKey(output.get(), key.get(), nullptr, nullptr, 0, nullptr, nullptr) !=
            1) {
            const auto error = currentOpenSslError();
            output.reset();
            std::remove(fileTemplate);
            throw std::runtime_error("Unable to write decrypted TLS private key: " + error);
        }

        return std::filesystem::path(fileTemplate);
    }

    std::filesystem::path path_;
    bool ownsFile_ = false;
};

drogon::HttpResponsePtr jsonResponse(drogon::HttpStatusCode statusCode, const std::string& payload)
{
    auto response =
        drogon::HttpResponse::newHttpResponse(statusCode, drogon::ContentType::CT_APPLICATION_JSON);
    response->setBody(payload);
    return response;
}

drogon::HttpResponsePtr jsonResponse(drogon::HttpStatusCode statusCode,
                                     const nlohmann::json& payload)
{
    return jsonResponse(statusCode, payload.dump());
}

void applyCorsHeaders(const drogon::HttpResponsePtr& response)
{
    response->addHeader("Access-Control-Allow-Origin", "*");
    response->addHeader("Access-Control-Allow-Methods", "GET, OPTIONS");
    response->addHeader("Access-Control-Allow-Headers", "Content-Type");
}

} // namespace

int main(int argc, char** argv)
{
    try {
        const auto dataDir = pubchem::cid4http::resolveDataDir();
        auto config =
            pubchem::cid4http::resolveServerConfig(dataDir, {"DROGON_HOST"}, {"DROGON_PORT"});

        if (const auto cliHost = hostOverride(argc, argv); !cliHost.empty()) {
            config.host = cliHost;
        }
        if (const auto cliPort = portOverride(argc, argv); cliPort.has_value()) {
            config.port = *cliPort;
        }

        TemporaryKeyFile serverKey(config);

        drogon::app().registerPostHandlingAdvice(
            [](const drogon::HttpRequestPtr&, const drogon::HttpResponsePtr& response) {
                applyCorsHeaders(response);
            });

        drogon::app().registerHandler(
            "/api/health",
            [](const drogon::HttpRequestPtr& request,
               std::function<void(const drogon::HttpResponsePtr&)>&& callback) {
                if (request->getParameter("mode") == "error") {
                    callback(jsonResponse(
                        drogon::k503ServiceUnavailable,
                        pubchem::cid4http::healthPayload("drogon", "Transport error from Drogon")));
                    return;
                }

                callback(jsonResponse(
                    drogon::k200OK,
                    pubchem::cid4http::healthPayload("drogon", "Drogon transport is healthy")));
            },
            {drogon::Get});

        drogon::app().registerHandler(
            "/api/cid4/conformer/{index}",
            [dataDir](const drogon::HttpRequestPtr&,
                      std::function<void(const drogon::HttpResponsePtr&)>&& callback,
                      std::string indexText) {
                try {
                    const auto index = std::stoi(indexText);
                    callback(jsonResponse(drogon::k200OK,
                                          pubchem::cid4http::loadJsonPayload(
                                              pubchem::cid4http::conformerPath(dataDir, index))));
                }
                catch (const std::out_of_range&) {
                    callback(jsonResponse(
                        drogon::k404NotFound,
                        nlohmann::json{{"message", "Unknown conformer " + indexText}}));
                }
                catch (const std::exception& error) {
                    callback(jsonResponse(drogon::k404NotFound,
                                          nlohmann::json{{"message", error.what()}}));
                }
            },
            {drogon::Get});

        drogon::app().registerHandler(
            "/api/cid4/structure/2d",
            [dataDir](const drogon::HttpRequestPtr&,
                      std::function<void(const drogon::HttpResponsePtr&)>&& callback) {
                try {
                    callback(jsonResponse(drogon::k200OK,
                                          pubchem::cid4http::loadJsonPayload(
                                              pubchem::cid4http::structure2dPath(dataDir))));
                }
                catch (const std::exception& error) {
                    callback(jsonResponse(drogon::k404NotFound,
                                          nlohmann::json{{"message", error.what()}}));
                }
            },
            {drogon::Get});

        drogon::app().registerHandler(
            "/api/cid4/compound",
            [dataDir](const drogon::HttpRequestPtr&,
                      std::function<void(const drogon::HttpResponsePtr&)>&& callback) {
                try {
                    callback(jsonResponse(drogon::k200OK,
                                          pubchem::cid4http::loadJsonPayload(
                                              pubchem::cid4http::compoundPath(dataDir))));
                }
                catch (const std::exception& error) {
                    callback(jsonResponse(drogon::k404NotFound,
                                          nlohmann::json{{"message", error.what()}}));
                }
            },
            {drogon::Get});

        drogon::app().registerHandler(
            "/api/algorithms/pathway",
            [](const drogon::HttpRequestPtr&,
               std::function<void(const drogon::HttpResponsePtr&)>&& callback) {
                callback(jsonResponse(drogon::k200OK, pubchem::cid4http::pathwayFixture()));
            },
            {drogon::Get});

        drogon::app().registerHandler(
            "/api/algorithms/bioactivity",
            [](const drogon::HttpRequestPtr&,
               std::function<void(const drogon::HttpResponsePtr&)>&& callback) {
                callback(jsonResponse(drogon::k200OK, pubchem::cid4http::bioactivityFixture()));
            },
            {drogon::Get});

        drogon::app().registerHandler(
            "/api/algorithms/taxonomy",
            [](const drogon::HttpRequestPtr&,
               std::function<void(const drogon::HttpResponsePtr&)>&& callback) {
                callback(jsonResponse(drogon::k200OK, pubchem::cid4http::taxonomyFixture()));
            },
            {drogon::Get});

        trantor::Logger::setLogLevel(trantor::Logger::kInfo);
        drogon::app().setThreadNum(0).addListener(config.host,
                                                  config.port,
                                                  true,
                                                  config.certFile.string(),
                                                  serverKey.path().string(),
                                                  false,
                                                  {});

        std::cout << "Drogon API server listening on https://" << config.host << ':' << config.port
                  << '\n';
        drogon::app().run();
    }
    catch (const std::exception& error) {
        std::cerr << "Failed to start Drogon API server: " << error.what() << '\n';
        return EXIT_FAILURE;
    }

    return EXIT_SUCCESS;
}
