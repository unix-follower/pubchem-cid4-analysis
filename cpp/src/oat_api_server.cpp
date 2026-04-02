#include "cid4_http.hpp"

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
    const std::shared_ptr<oatpp::web::protocol::http::outgoing::Response>& response)
{
    response->putHeader(oatpp::web::protocol::http::Header::CONTENT_TYPE, "application/json");
    response->putHeader(oatpp::web::protocol::http::Header::CORS_ORIGIN, "*");
    response->putHeader(oatpp::web::protocol::http::Header::CORS_METHODS, "GET, OPTIONS");
    response->putHeader(oatpp::web::protocol::http::Header::CORS_HEADERS, "Content-Type");
}

#include OATPP_CODEGEN_BEGIN(ApiController)

class OatApiController : public oatpp::web::server::api::ApiController {
  public:
    OatApiController(const std::shared_ptr<ObjectMapper>& objectMapper,
                     std::filesystem::path dataDir)
        : oatpp::web::server::api::ApiController(objectMapper), dataDir_(std::move(dataDir))
    {}

    static std::shared_ptr<OatApiController>
    createShared(const std::shared_ptr<ObjectMapper>& objectMapper,
                 const std::filesystem::path& dataDir)
    {
        return std::make_shared<OatApiController>(objectMapper, dataDir);
    }

    ADD_CORS(getHealth, "*", "GET, OPTIONS", "Content-Type")
    ENDPOINT("GET", "/api/health", getHealth, REQUEST(std::shared_ptr<IncomingRequest>, request))
    {
        const auto mode = request->getQueryParameter("mode");
        if (mode && mode == "error") {
            return jsonResponse(
                Status::CODE_503,
                pubchem::cid4http::healthPayload("oatpp", "Transport error from Oat++"));
        }

        return jsonResponse(
            Status::CODE_200,
            pubchem::cid4http::healthPayload("oatpp", "Oat++ transport is healthy"));
    }

    ADD_CORS(getConformer, "*", "GET, OPTIONS", "Content-Type")
    ENDPOINT("GET", "/api/cid4/conformer/{index}", getConformer, PATH(Int32, index))
    {
        const auto conformerIndex = static_cast<int>(*index);
        try {
            return jsonResponse(Status::CODE_200,
                                pubchem::cid4http::loadJsonPayload(
                                    pubchem::cid4http::conformerPath(dataDir_, conformerIndex)));
        }
        catch (const std::out_of_range&) {
            return jsonResponse(
                Status::CODE_404,
                nlohmann::json{{"message", "Unknown conformer " + std::to_string(conformerIndex)}});
        }
        catch (const std::exception& error) {
            return jsonResponse(Status::CODE_404, nlohmann::json{{"message", error.what()}});
        }
    }

    ADD_CORS(getStructure2d, "*", "GET, OPTIONS", "Content-Type")
    ENDPOINT("GET", "/api/cid4/structure/2d", getStructure2d)
    {
        try {
            return jsonResponse(
                Status::CODE_200,
                pubchem::cid4http::loadJsonPayload(pubchem::cid4http::structure2dPath(dataDir_)));
        }
        catch (const std::exception& error) {
            return jsonResponse(Status::CODE_404, nlohmann::json{{"message", error.what()}});
        }
    }

    ADD_CORS(getCompound, "*", "GET, OPTIONS", "Content-Type")
    ENDPOINT("GET", "/api/cid4/compound", getCompound)
    {
        try {
            return jsonResponse(
                Status::CODE_200,
                pubchem::cid4http::loadJsonPayload(pubchem::cid4http::compoundPath(dataDir_)));
        }
        catch (const std::exception& error) {
            return jsonResponse(Status::CODE_404, nlohmann::json{{"message", error.what()}});
        }
    }

    ADD_CORS(getPathway, "*", "GET, OPTIONS", "Content-Type")
    ENDPOINT("GET", "/api/algorithms/pathway", getPathway)
    {
        return jsonResponse(Status::CODE_200, pubchem::cid4http::pathwayFixture());
    }

    ADD_CORS(getBioactivity, "*", "GET, OPTIONS", "Content-Type")
    ENDPOINT("GET", "/api/algorithms/bioactivity", getBioactivity)
    {
        return jsonResponse(Status::CODE_200, pubchem::cid4http::bioactivityFixture());
    }

    ADD_CORS(getTaxonomy, "*", "GET, OPTIONS", "Content-Type")
    ENDPOINT("GET", "/api/algorithms/taxonomy", getTaxonomy)
    {
        return jsonResponse(Status::CODE_200, pubchem::cid4http::taxonomyFixture());
    }

  private:
    std::shared_ptr<OutgoingResponse> jsonResponse(const Status& status,
                                                   const nlohmann::json& payload)
    {
        return jsonResponse(status, payload.dump());
    }

    std::shared_ptr<OutgoingResponse> jsonResponse(const Status& status, const std::string& payload)
    {
        auto response = createResponse(status, oatpp::String(payload.c_str(), payload.size()));
        applyJsonHeaders(response);
        return response;
    }

    std::filesystem::path dataDir_;
};

#include OATPP_CODEGEN_END(ApiController)

} // namespace

int main(int argc, char** argv)
{
    oatpp::base::Environment::init();

    try {
        const auto dataDir = pubchem::cid4http::resolveDataDir();
        auto config =
            pubchem::cid4http::resolveServerConfig(dataDir, {"OATPP_HOST"}, {"OATPP_PORT"});

        if (const auto cliHost = hostOverride(argc, argv); !cliHost.empty()) {
            config.host = cliHost;
        }
        if (const auto cliPort = portOverride(argc, argv); cliPort.has_value()) {
            config.port = *cliPort;
        }

        auto router = oatpp::web::server::HttpRouter::createShared();
        auto objectMapper = std::make_shared<oatpp::parser::json::mapping::ObjectMapper>();
        router->addController(OatApiController::createShared(objectMapper, dataDir));

        auto connectionHandler = oatpp::web::server::HttpConnectionHandler::createShared(router);
        auto connectionProvider = oatpp::openssl::server::ConnectionProvider::createShared(
            buildTlsConfig(config), {config.host.c_str(), config.port});
        auto server = oatpp::network::Server::createShared(connectionProvider, connectionHandler);

        std::cout << "Oat++ API server listening on https://" << config.host << ':' << config.port
                  << '\n';
        server->run();
        connectionHandler->stop();
        connectionProvider->stop();
    }
    catch (const std::exception& error) {
        std::cerr << "Failed to start Oat++ API server: " << error.what() << '\n';
        oatpp::base::Environment::destroy();
        return EXIT_FAILURE;
    }

    oatpp::base::Environment::destroy();
    return EXIT_SUCCESS;
}
