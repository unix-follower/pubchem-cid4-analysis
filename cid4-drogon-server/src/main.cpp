#include "cid4_http.hpp"
#include "observability.hpp"

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

void applyCorsHeaders(const drogon::HttpResponsePtr& response,
                      const pubchem::cid4observability::RequestScope* requestScope = nullptr);

drogon::HttpResponsePtr jsonResponse(drogon::HttpStatusCode statusCode,
                                     const std::string& payload,
                                     const pubchem::cid4observability::RequestScope* requestScope);

drogon::HttpResponsePtr jsonResponse(drogon::HttpStatusCode statusCode,
                                     const nlohmann::json& payload,
                                     const pubchem::cid4observability::RequestScope* requestScope);

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
    return jsonResponse(statusCode, payload, nullptr);
}

drogon::HttpResponsePtr jsonResponse(drogon::HttpStatusCode statusCode,
                                     const std::string& payload,
                                     const pubchem::cid4observability::RequestScope* requestScope)
{
    auto response =
        drogon::HttpResponse::newHttpResponse(statusCode, drogon::ContentType::CT_APPLICATION_JSON);
    response->setBody(payload);
    applyCorsHeaders(response, requestScope);
    return response;
}

drogon::HttpResponsePtr jsonResponse(drogon::HttpStatusCode statusCode,
                                     const nlohmann::json& payload)
{
    return jsonResponse(statusCode, payload, nullptr);
}

drogon::HttpResponsePtr jsonResponse(drogon::HttpStatusCode statusCode,
                                     const nlohmann::json& payload,
                                     const pubchem::cid4observability::RequestScope* requestScope)
{
    return jsonResponse(statusCode, payload.dump(), requestScope);
}

void applyCorsHeaders(const drogon::HttpResponsePtr& response,
                      const pubchem::cid4observability::RequestScope* requestScope)
{
    response->addHeader("Access-Control-Allow-Origin", "*");
    response->addHeader("Access-Control-Allow-Methods", "GET, OPTIONS");
    response->addHeader("Access-Control-Allow-Headers", "Content-Type");

    if (requestScope != nullptr) {
        response->addHeader("X-Request-Id", requestScope->requestId());
        if (!requestScope->traceId().empty()) {
            response->addHeader("X-Trace-Id", requestScope->traceId());
        }
        if (!requestScope->spanId().empty()) {
            response->addHeader("X-Span-Id", requestScope->spanId());
        }
        response->addHeader("traceparent", requestScope->traceparent());
    }
}

std::optional<std::string> requestIdHeader(const drogon::HttpRequestPtr& request)
{
    const auto value = request->getHeader("X-Request-Id");
    if (value.empty()) {
        return std::nullopt;
    }

    return value;
}

std::string requestTarget(const drogon::HttpRequestPtr& request)
{
    const auto query = request->query();
    if (query.empty()) {
        return request->path();
    }

    return request->path() + "?" + query;
}

} // namespace

int main(int argc, char** argv)
{
    std::shared_ptr<pubchem::cid4observability::Runtime> observability;

    try {
        const auto dataDir = pubchem::cid4http::resolveDataDir();
        auto config =
            pubchem::cid4http::resolveServerConfig(dataDir, {"DROGON_HOST"}, {"DROGON_PORT"});
        const auto observabilityConfig =
            pubchem::cid4observability::resolveObservabilityConfig("DROGON", "pubchem-cid4-drogon");

        if (const auto cliHost = hostOverride(argc, argv); !cliHost.empty()) {
            config.host = cliHost;
        }
        if (const auto cliPort = portOverride(argc, argv); cliPort.has_value()) {
            config.port = *cliPort;
        }

        observability = pubchem::cid4observability::initialize(observabilityConfig);

        TemporaryKeyFile serverKey(config);

        drogon::app().registerPostHandlingAdvice(
            [](const drogon::HttpRequestPtr&, const drogon::HttpResponsePtr& response) {
                applyCorsHeaders(response);
            });

        drogon::app().registerHandler(
            "/api/health",
            [observability](const drogon::HttpRequestPtr& request,
                            std::function<void(const drogon::HttpResponsePtr&)>&& callback) {
                pubchem::cid4observability::RequestScope scope(observability,
                                                               "GET",
                                                               "/api/health",
                                                               requestTarget(request),
                                                               requestIdHeader(request));
                if (request->getParameter("mode") == "error") {
                    auto response = jsonResponse(
                        drogon::k503ServiceUnavailable,
                        pubchem::cid4http::healthPayload("drogon", "Transport error from Drogon"),
                        &scope);
                    scope.finish(503);
                    callback(response);
                    return;
                }

                auto response = jsonResponse(
                    drogon::k200OK,
                    pubchem::cid4http::healthPayload("drogon", "Drogon transport is healthy"),
                    &scope);
                scope.finish(200);
                callback(response);
            },
            {drogon::Get});

        drogon::app().registerHandler(
            "/api/cid4/conformer/{index}",
            [dataDir, observability](const drogon::HttpRequestPtr& request,
                                     std::function<void(const drogon::HttpResponsePtr&)>&& callback,
                                     std::string indexText) {
                pubchem::cid4observability::RequestScope scope(observability,
                                                               "GET",
                                                               "/api/cid4/conformer/{index}",
                                                               requestTarget(request),
                                                               requestIdHeader(request));
                try {
                    const auto index = std::stoi(indexText);
                    auto response =
                        jsonResponse(drogon::k200OK,
                                     pubchem::cid4http::loadJsonPayload(
                                         pubchem::cid4http::conformerPath(dataDir, index)),
                                     &scope);
                    scope.finish(200);
                    callback(response);
                    return;
                }
                catch (const std::out_of_range&) {
                    auto response =
                        jsonResponse(drogon::k404NotFound,
                                     nlohmann::json{{"message", "Unknown conformer " + indexText}},
                                     &scope);
                    scope.finish(404);
                    callback(response);
                    return;
                }
                catch (const std::exception& error) {
                    auto response = jsonResponse(
                        drogon::k404NotFound, nlohmann::json{{"message", error.what()}}, &scope);
                    scope.finish(404);
                    callback(response);
                }
            },
            {drogon::Get});

        drogon::app().registerHandler(
            "/api/cid4/structure/2d",
            [dataDir,
             observability](const drogon::HttpRequestPtr& request,
                            std::function<void(const drogon::HttpResponsePtr&)>&& callback) {
                pubchem::cid4observability::RequestScope scope(observability,
                                                               "GET",
                                                               "/api/cid4/structure/2d",
                                                               requestTarget(request),
                                                               requestIdHeader(request));
                try {
                    auto response = jsonResponse(drogon::k200OK,
                                                 pubchem::cid4http::loadJsonPayload(
                                                     pubchem::cid4http::structure2dPath(dataDir)),
                                                 &scope);
                    scope.finish(200);
                    callback(response);
                    return;
                }
                catch (const std::exception& error) {
                    auto response = jsonResponse(
                        drogon::k404NotFound, nlohmann::json{{"message", error.what()}}, &scope);
                    scope.finish(404);
                    callback(response);
                }
            },
            {drogon::Get});

        drogon::app().registerHandler(
            "/api/cid4/compound",
            [dataDir,
             observability](const drogon::HttpRequestPtr& request,
                            std::function<void(const drogon::HttpResponsePtr&)>&& callback) {
                pubchem::cid4observability::RequestScope scope(observability,
                                                               "GET",
                                                               "/api/cid4/compound",
                                                               requestTarget(request),
                                                               requestIdHeader(request));
                try {
                    auto response = jsonResponse(drogon::k200OK,
                                                 pubchem::cid4http::loadJsonPayload(
                                                     pubchem::cid4http::compoundPath(dataDir)),
                                                 &scope);
                    scope.finish(200);
                    callback(response);
                    return;
                }
                catch (const std::exception& error) {
                    auto response = jsonResponse(
                        drogon::k404NotFound, nlohmann::json{{"message", error.what()}}, &scope);
                    scope.finish(404);
                    callback(response);
                }
            },
            {drogon::Get});

        drogon::app().registerHandler(
            "/api/algorithms/pathway",
            [observability](const drogon::HttpRequestPtr& request,
                            std::function<void(const drogon::HttpResponsePtr&)>&& callback) {
                pubchem::cid4observability::RequestScope scope(observability,
                                                               "GET",
                                                               "/api/algorithms/pathway",
                                                               requestTarget(request),
                                                               requestIdHeader(request));
                auto response =
                    jsonResponse(drogon::k200OK, pubchem::cid4http::pathwayFixture(), &scope);
                scope.finish(200);
                callback(response);
            },
            {drogon::Get});

        drogon::app().registerHandler(
            "/api/algorithms/bioactivity",
            [observability](const drogon::HttpRequestPtr& request,
                            std::function<void(const drogon::HttpResponsePtr&)>&& callback) {
                pubchem::cid4observability::RequestScope scope(observability,
                                                               "GET",
                                                               "/api/algorithms/bioactivity",
                                                               requestTarget(request),
                                                               requestIdHeader(request));
                auto response =
                    jsonResponse(drogon::k200OK, pubchem::cid4http::bioactivityFixture(), &scope);
                scope.finish(200);
                callback(response);
            },
            {drogon::Get});

        drogon::app().registerHandler(
            "/api/algorithms/taxonomy",
            [observability](const drogon::HttpRequestPtr& request,
                            std::function<void(const drogon::HttpResponsePtr&)>&& callback) {
                pubchem::cid4observability::RequestScope scope(observability,
                                                               "GET",
                                                               "/api/algorithms/taxonomy",
                                                               requestTarget(request),
                                                               requestIdHeader(request));
                auto response =
                    jsonResponse(drogon::k200OK, pubchem::cid4http::taxonomyFixture(), &scope);
                scope.finish(200);
                callback(response);
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

        if (observability) {
            observability->logStartup(config.host, config.port);
        }
        drogon::app().run();
        pubchem::cid4observability::shutdown(observability);
    }
    catch (const std::exception& error) {
        if (observability) {
            observability->logStartupFailure(error.what());
            pubchem::cid4observability::shutdown(observability);
        }
        else {
            std::cerr << "Failed to start Drogon API server: " << error.what() << '\n';
        }
        return EXIT_FAILURE;
    }

    return EXIT_SUCCESS;
}
