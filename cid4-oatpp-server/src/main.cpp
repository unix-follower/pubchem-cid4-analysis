#include "cid4_http.hpp"
#include "observability.hpp"

#include "oatpp-openssl/Config.hpp"
#include "oatpp-openssl/configurer/CertificateChainFile.hpp"
#include "oatpp-openssl/configurer/ContextConfigurer.hpp"
#include "oatpp-openssl/configurer/PrivateKeyFile.hpp"
#include "oatpp-openssl/server/ConnectionProvider.hpp"
#include "oatpp/core/base/Environment.hpp"
#include "oatpp/core/macro/codegen.hpp"
#include "oatpp/network/Server.hpp"
#include "oatpp/network/tcp/server/ConnectionProvider.hpp"
#include "oatpp/parser/json/mapping/ObjectMapper.hpp"
#include "oatpp/web/protocol/http/Http.hpp"
#include "oatpp/web/protocol/http/incoming/Request.hpp"
#include "oatpp/web/server/HttpConnectionHandler.hpp"
#include "oatpp/web/server/HttpRouter.hpp"
#include "oatpp/web/server/api/ApiController.hpp"

#include <openssl/ssl.h>

#include <algorithm>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <exception>
#include <filesystem>
#include <iostream>
#include <memory>
#include <optional>
#include <string>
#include <string_view>
#include <utility>

namespace {

class PasswordConfigurer : public oatpp::openssl::configurer::ContextConfigurer {
  public:
    explicit PasswordConfigurer(std::string password) : password_(std::move(password)) {}

    void configure(SSL_CTX* ctx) override
    {
        SSL_CTX_set_default_passwd_cb_userdata(ctx, this);
        SSL_CTX_set_default_passwd_cb(ctx, &PasswordConfigurer::passwordCallback);
    }

  private:
    static int passwordCallback(char* buffer, int size, int, void* userdata)
    {
        const auto* self = static_cast<PasswordConfigurer*>(userdata);
        if (size <= 0 || self == nullptr) {
            return 0;
        }

        const auto copyLength =
            std::min<std::size_t>(self->password_.size(), static_cast<std::size_t>(size - 1));
        std::memcpy(buffer, self->password_.data(), copyLength);
        buffer[copyLength] = '\0';
        return static_cast<int>(copyLength);
    }

    std::string password_;
};

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

std::shared_ptr<oatpp::openssl::Config>
buildTlsConfig(const pubchem::cid4http::ServerConfig& config)
{
    auto tlsConfig = oatpp::openssl::Config::createShared();
    if (config.keyPassword.has_value()) {
        tlsConfig->addContextConfigurer(std::make_shared<PasswordConfigurer>(*config.keyPassword));
    }
    tlsConfig->addContextConfigurer(
        std::make_shared<oatpp::openssl::configurer::CertificateChainFile>(
            config.certFile.string().c_str()));
    tlsConfig->addContextConfigurer(std::make_shared<oatpp::openssl::configurer::PrivateKeyFile>(
        config.keyFile.string().c_str()));
    return tlsConfig;
}

void applyJsonHeaders(
    const std::shared_ptr<oatpp::web::protocol::http::outgoing::Response>& response,
    const pubchem::cid4observability::RequestScope* requestScope = nullptr)
{
    response->putHeader(oatpp::web::protocol::http::Header::CONTENT_TYPE, "application/json");
    response->putHeader(oatpp::web::protocol::http::Header::CORS_ORIGIN, "*");
    response->putHeader(oatpp::web::protocol::http::Header::CORS_METHODS, "GET, OPTIONS");
    response->putHeader(oatpp::web::protocol::http::Header::CORS_HEADERS, "Content-Type");

    if (requestScope != nullptr) {
        response->putHeader("X-Request-Id", requestScope->requestId().c_str());
        if (!requestScope->traceId().empty()) {
            response->putHeader("X-Trace-Id", requestScope->traceId().c_str());
        }
        if (!requestScope->spanId().empty()) {
            response->putHeader("X-Span-Id", requestScope->spanId().c_str());
        }
        response->putHeader("traceparent", requestScope->traceparent().c_str());
    }
}

std::optional<std::string>
requestIdHeader(const std::shared_ptr<oatpp::web::protocol::http::incoming::Request>& request)
{
    const auto header = request->getHeader("X-Request-Id");
    if (!header || header->empty()) {
        return std::nullopt;
    }

    return std::string(header->c_str(), header->size());
}

#include OATPP_CODEGEN_BEGIN(ApiController)

class OatApiController : public oatpp::web::server::api::ApiController {
  public:
    OatApiController(const std::shared_ptr<ObjectMapper>& objectMapper,
                     std::filesystem::path dataDir,
                     std::shared_ptr<pubchem::cid4observability::Runtime> observability)
        : oatpp::web::server::api::ApiController(objectMapper),
          dataDir_(std::move(dataDir)),
          observability_(std::move(observability))
    {}

    static std::shared_ptr<OatApiController>
    createShared(const std::shared_ptr<ObjectMapper>& objectMapper,
                 const std::filesystem::path& dataDir,
                 const std::shared_ptr<pubchem::cid4observability::Runtime>& observability)
    {
        return std::make_shared<OatApiController>(objectMapper, dataDir, observability);
    }

    ADD_CORS(getHealth, "*", "GET, OPTIONS", "Content-Type")
    ENDPOINT("GET", "/api/health", getHealth, REQUEST(std::shared_ptr<IncomingRequest>, request))
    {
        pubchem::cid4observability::RequestScope scope(
            observability_, "GET", "/api/health", "/api/health", requestIdHeader(request));
        const auto mode = request->getQueryParameter("mode");
        if (mode && mode == "error") {
            auto response = jsonResponse(
                Status::CODE_503,
                pubchem::cid4http::healthPayload("oatpp", "Transport error from Oat++"),
                &scope);
            scope.finish(503);
            return response;
        }

        auto response =
            jsonResponse(Status::CODE_200,
                         pubchem::cid4http::healthPayload("oatpp", "Oat++ transport is healthy"),
                         &scope);
        scope.finish(200);
        return response;
    }

    ADD_CORS(getConformer, "*", "GET, OPTIONS", "Content-Type")
    ENDPOINT("GET", "/api/cid4/conformer/{index}", getConformer, PATH(Int32, index))
    {
        pubchem::cid4observability::RequestScope scope(observability_,
                                                       "GET",
                                                       "/api/cid4/conformer/{index}",
                                                       "/api/cid4/conformer/{index}",
                                                       std::nullopt);
        const auto conformerIndex = static_cast<int>(*index);
        try {
            auto response =
                jsonResponse(Status::CODE_200,
                             pubchem::cid4http::loadJsonPayload(
                                 pubchem::cid4http::conformerPath(dataDir_, conformerIndex)),
                             &scope);
            scope.finish(200);
            return response;
        }
        catch (const std::out_of_range&) {
            auto response = jsonResponse(
                Status::CODE_404,
                nlohmann::json{{"message", "Unknown conformer " + std::to_string(conformerIndex)}},
                &scope);
            scope.finish(404);
            return response;
        }
        catch (const std::exception& error) {
            auto response =
                jsonResponse(Status::CODE_404, nlohmann::json{{"message", error.what()}}, &scope);
            scope.finish(404);
            return response;
        }
    }

    ADD_CORS(getStructure2d, "*", "GET, OPTIONS", "Content-Type")
    ENDPOINT("GET", "/api/cid4/structure/2d", getStructure2d)
    {
        pubchem::cid4observability::RequestScope scope(
            observability_, "GET", "/api/cid4/structure/2d", "/api/cid4/structure/2d");
        try {
            auto response = jsonResponse(
                Status::CODE_200,
                pubchem::cid4http::loadJsonPayload(pubchem::cid4http::structure2dPath(dataDir_)),
                &scope);
            scope.finish(200);
            return response;
        }
        catch (const std::exception& error) {
            auto response =
                jsonResponse(Status::CODE_404, nlohmann::json{{"message", error.what()}}, &scope);
            scope.finish(404);
            return response;
        }
    }

    ADD_CORS(getCompound, "*", "GET, OPTIONS", "Content-Type")
    ENDPOINT("GET", "/api/cid4/compound", getCompound)
    {
        pubchem::cid4observability::RequestScope scope(
            observability_, "GET", "/api/cid4/compound", "/api/cid4/compound");
        try {
            auto response = jsonResponse(
                Status::CODE_200,
                pubchem::cid4http::loadJsonPayload(pubchem::cid4http::compoundPath(dataDir_)),
                &scope);
            scope.finish(200);
            return response;
        }
        catch (const std::exception& error) {
            auto response =
                jsonResponse(Status::CODE_404, nlohmann::json{{"message", error.what()}}, &scope);
            scope.finish(404);
            return response;
        }
    }

    ADD_CORS(getPathway, "*", "GET, OPTIONS", "Content-Type")
    ENDPOINT("GET", "/api/algorithms/pathway", getPathway)
    {
        pubchem::cid4observability::RequestScope scope(
            observability_, "GET", "/api/algorithms/pathway", "/api/algorithms/pathway");
        auto response = jsonResponse(Status::CODE_200, pubchem::cid4http::pathwayFixture(), &scope);
        scope.finish(200);
        return response;
    }

    ADD_CORS(getBioactivity, "*", "GET, OPTIONS", "Content-Type")
    ENDPOINT("GET", "/api/algorithms/bioactivity", getBioactivity)
    {
        pubchem::cid4observability::RequestScope scope(
            observability_, "GET", "/api/algorithms/bioactivity", "/api/algorithms/bioactivity");
        auto response =
            jsonResponse(Status::CODE_200, pubchem::cid4http::bioactivityFixture(), &scope);
        scope.finish(200);
        return response;
    }

    ADD_CORS(getTaxonomy, "*", "GET, OPTIONS", "Content-Type")
    ENDPOINT("GET", "/api/algorithms/taxonomy", getTaxonomy)
    {
        pubchem::cid4observability::RequestScope scope(
            observability_, "GET", "/api/algorithms/taxonomy", "/api/algorithms/taxonomy");
        auto response =
            jsonResponse(Status::CODE_200, pubchem::cid4http::taxonomyFixture(), &scope);
        scope.finish(200);
        return response;
    }

  private:
    std::shared_ptr<OutgoingResponse>
    jsonResponse(const Status& status,
                 const nlohmann::json& payload,
                 const pubchem::cid4observability::RequestScope* requestScope = nullptr)
    {
        return jsonResponse(status, payload.dump(), requestScope);
    }

    std::shared_ptr<OutgoingResponse>
    jsonResponse(const Status& status,
                 const std::string& payload,
                 const pubchem::cid4observability::RequestScope* requestScope = nullptr)
    {
        auto response = createResponse(status, oatpp::String(payload.c_str(), payload.size()));
        applyJsonHeaders(response, requestScope);
        return response;
    }

    std::filesystem::path dataDir_;
    std::shared_ptr<pubchem::cid4observability::Runtime> observability_;
};

#include OATPP_CODEGEN_END(ApiController)

} // namespace

int main(int argc, char** argv)
{
    oatpp::base::Environment::init();
    std::shared_ptr<pubchem::cid4observability::Runtime> observability;

    try {
        const auto dataDir = pubchem::cid4http::resolveDataDir();
        auto config =
            pubchem::cid4http::resolveServerConfig(dataDir, {"OATPP_HOST"}, {"OATPP_PORT"});
        const auto observabilityConfig =
            pubchem::cid4observability::resolveObservabilityConfig("OATPP", "pubchem-cid4-oatpp");

        if (const auto cliHost = hostOverride(argc, argv); !cliHost.empty()) {
            config.host = cliHost;
        }
        if (const auto cliPort = portOverride(argc, argv); cliPort.has_value()) {
            config.port = *cliPort;
        }

        observability = pubchem::cid4observability::initialize(observabilityConfig);

        auto router = oatpp::web::server::HttpRouter::createShared();
        auto objectMapper = std::make_shared<oatpp::parser::json::mapping::ObjectMapper>();
        router->addController(OatApiController::createShared(objectMapper, dataDir, observability));

        auto connectionHandler = oatpp::web::server::HttpConnectionHandler::createShared(router);
        auto connectionProvider = oatpp::openssl::server::ConnectionProvider::createShared(
            buildTlsConfig(config), {config.host.c_str(), config.port});
        auto server = oatpp::network::Server::createShared(connectionProvider, connectionHandler);

        if (observability) {
            observability->logStartup(config.host, config.port);
        }
        server->run();
        connectionHandler->stop();
        connectionProvider->stop();
        pubchem::cid4observability::shutdown(observability);
    }
    catch (const std::exception& error) {
        if (observability) {
            observability->logStartupFailure(error.what());
            pubchem::cid4observability::shutdown(observability);
        }
        else {
            std::cerr << "Failed to start Oat++ API server: " << error.what() << '\n';
        }
        oatpp::base::Environment::destroy();
        return EXIT_FAILURE;
    }

    oatpp::base::Environment::destroy();
    return EXIT_SUCCESS;
}
