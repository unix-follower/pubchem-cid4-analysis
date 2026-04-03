#include "cid4_http.hpp"
#include "cid4_observability.hpp"

#include <crow.h>

#include <asio/ssl/context.hpp>

#include <cstdlib>
#include <exception>
#include <iostream>
#include <optional>

namespace {

void applyJsonHeaders(crow::response& response,
                      const pubchem::cid4observability::RequestScope* requestScope = nullptr)
{
    response.set_header("Content-Type", "application/json");
    response.set_header("Access-Control-Allow-Origin", "*");
    response.set_header("Access-Control-Allow-Methods", "GET, OPTIONS");
    response.set_header("Access-Control-Allow-Headers", "Content-Type");

    if (requestScope != nullptr) {
        response.set_header("X-Request-Id", requestScope->requestId());
        if (!requestScope->traceId().empty()) {
            response.set_header("X-Trace-Id", requestScope->traceId());
        }
        if (!requestScope->spanId().empty()) {
            response.set_header("X-Span-Id", requestScope->spanId());
        }
        response.set_header("traceparent", requestScope->traceparent());
    }
}

crow::response jsonResponse(int statusCode,
                            const std::string& payload,
                            const pubchem::cid4observability::RequestScope* requestScope = nullptr)
{
    crow::response response(statusCode);
    applyJsonHeaders(response, requestScope);
    response.write(payload);
    return response;
}

crow::response jsonResponse(int statusCode,
                            const nlohmann::json& payload,
                            const pubchem::cid4observability::RequestScope* requestScope = nullptr)
{
    crow::response response(statusCode);
    applyJsonHeaders(response, requestScope);
    response.write(payload.dump());
    return response;
}

std::optional<std::string> requestIdHeader(const crow::request& request)
{
    const auto value = request.get_header_value("X-Request-Id");
    if (value.empty()) {
        return std::nullopt;
    }

    return value;
}

asio::ssl::context buildSslContext(const pubchem::cid4http::ServerConfig& config)
{
    asio::ssl::context context(asio::ssl::context::tls_server);
    context.set_options(asio::ssl::context::default_workarounds | asio::ssl::context::no_sslv2 |
                        asio::ssl::context::no_sslv3 | asio::ssl::context::single_dh_use);

    if (config.keyPassword.has_value()) {
        const auto password = *config.keyPassword;
        context.set_password_callback(
            [password](std::size_t, asio::ssl::context_base::password_purpose) {
                return password;
            });
    }

    context.use_certificate_chain_file(config.certFile.string());
    context.use_private_key_file(config.keyFile.string(), asio::ssl::context::pem);
    return context;
}

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

} // namespace

int main(int argc, char** argv)
{
    std::shared_ptr<pubchem::cid4observability::Runtime> observability;

    try {
        crow::SimpleApp app;
        const auto dataDir = pubchem::cid4http::resolveDataDir();
        auto config = pubchem::cid4http::resolveServerConfig(dataDir, {"CROW_HOST"}, {"CROW_PORT"});
        const auto observabilityConfig =
            pubchem::cid4observability::resolveObservabilityConfig("CROW", "pubchem-cid4-crow");

        if (const auto cliHost = hostOverride(argc, argv); !cliHost.empty()) {
            config.host = cliHost;
        }
        if (const auto cliPort = portOverride(argc, argv); cliPort.has_value()) {
            config.port = *cliPort;
        }

        observability = pubchem::cid4observability::initialize(observabilityConfig);

        CROW_ROUTE(app, "/api/health")
        ([observability](const crow::request& req) {
            pubchem::cid4observability::RequestScope scope(
                observability, "GET", "/api/health", "/api/health", requestIdHeader(req));
            const char* mode = req.url_params.get("mode");
            if (mode != nullptr && std::string_view(mode) == "error") {
                auto response = jsonResponse(
                    503,
                    pubchem::cid4http::healthPayload("crow", "Transport error from Crow"),
                    &scope);
                scope.finish(503);
                return response;
            }

            auto response = jsonResponse(
                200, pubchem::cid4http::healthPayload("crow", "Crow transport is healthy"), &scope);
            scope.finish(200);
            return response;
        });

        CROW_ROUTE(app, "/api/cid4/conformer/<int>")
        ([dataDir, observability](const crow::request& req, int index) {
            pubchem::cid4observability::RequestScope scope(
                observability, "GET", "/api/cid4/conformer/{index}", req.url, requestIdHeader(req));
            try {
                auto response = jsonResponse(200,
                                             pubchem::cid4http::loadJsonPayload(
                                                 pubchem::cid4http::conformerPath(dataDir, index)),
                                             &scope);
                scope.finish(200);
                return response;
            }
            catch (const std::out_of_range&) {
                auto response = jsonResponse(
                    404,
                    nlohmann::json{{"message", "Unknown conformer " + std::to_string(index)}},
                    &scope);
                scope.finish(404);
                return response;
            }
            catch (const std::exception& error) {
                auto response =
                    jsonResponse(404, nlohmann::json{{"message", error.what()}}, &scope);
                scope.finish(404);
                return response;
            }
        });

        CROW_ROUTE(app, "/api/cid4/structure/2d")
        ([dataDir, observability](const crow::request& req) {
            pubchem::cid4observability::RequestScope scope(
                observability, "GET", "/api/cid4/structure/2d", req.url, requestIdHeader(req));
            try {
                auto response = jsonResponse(
                    200,
                    pubchem::cid4http::loadJsonPayload(pubchem::cid4http::structure2dPath(dataDir)),
                    &scope);
                scope.finish(200);
                return response;
            }
            catch (const std::exception& error) {
                auto response =
                    jsonResponse(404, nlohmann::json{{"message", error.what()}}, &scope);
                scope.finish(404);
                return response;
            }
        });

        CROW_ROUTE(app, "/api/cid4/compound")
        ([dataDir, observability](const crow::request& req) {
            pubchem::cid4observability::RequestScope scope(
                observability, "GET", "/api/cid4/compound", req.url, requestIdHeader(req));
            try {
                auto response = jsonResponse(
                    200,
                    pubchem::cid4http::loadJsonPayload(pubchem::cid4http::compoundPath(dataDir)),
                    &scope);
                scope.finish(200);
                return response;
            }
            catch (const std::exception& error) {
                auto response =
                    jsonResponse(404, nlohmann::json{{"message", error.what()}}, &scope);
                scope.finish(404);
                return response;
            }
        });

        CROW_ROUTE(app, "/api/algorithms/pathway")
        ([observability](const crow::request& req) {
            pubchem::cid4observability::RequestScope scope(
                observability, "GET", "/api/algorithms/pathway", req.url, requestIdHeader(req));
            auto response = jsonResponse(200, pubchem::cid4http::pathwayFixture(), &scope);
            scope.finish(200);
            return response;
        });

        CROW_ROUTE(app, "/api/algorithms/bioactivity")
        ([observability](const crow::request& req) {
            pubchem::cid4observability::RequestScope scope(
                observability, "GET", "/api/algorithms/bioactivity", req.url, requestIdHeader(req));
            auto response = jsonResponse(200, pubchem::cid4http::bioactivityFixture(), &scope);
            scope.finish(200);
            return response;
        });

        CROW_ROUTE(app, "/api/algorithms/taxonomy")
        ([observability](const crow::request& req) {
            pubchem::cid4observability::RequestScope scope(
                observability, "GET", "/api/algorithms/taxonomy", req.url, requestIdHeader(req));
            auto response = jsonResponse(200, pubchem::cid4http::taxonomyFixture(), &scope);
            scope.finish(200);
            return response;
        });

        auto sslContext = buildSslContext(config);
        if (observability) {
            observability->logStartup(config.host, config.port);
        }
        app.loglevel(crow::LogLevel::Info)
            .bindaddr(config.host)
            .port(config.port)
            .ssl(std::move(sslContext))
            .multithreaded()
            .run();
        pubchem::cid4observability::shutdown(observability);
    }
    catch (const std::exception& error) {
        if (observability) {
            observability->logStartupFailure(error.what());
            pubchem::cid4observability::shutdown(observability);
        }
        else {
            std::cerr << "Failed to start Crow API server: " << error.what() << '\n';
        }
        return EXIT_FAILURE;
    }

    return EXIT_SUCCESS;
}
