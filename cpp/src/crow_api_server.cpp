#include "cid4_http.hpp"

#include <crow.h>

#include <asio/ssl/context.hpp>

#include <cstdlib>
#include <exception>
#include <iostream>

namespace {

crow::response jsonResponse(int statusCode, const nlohmann::json& payload)
{
    crow::response response(statusCode);
    response.set_header("Content-Type", "application/json");
    response.set_header("Access-Control-Allow-Origin", "*");
    response.set_header("Access-Control-Allow-Methods", "GET, OPTIONS");
    response.set_header("Access-Control-Allow-Headers", "Content-Type");
    response.write(payload.dump());
    return response;
}

crow::response jsonResponse(int statusCode, const std::string& payload)
{
    crow::response response(statusCode);
    response.set_header("Content-Type", "application/json");
    response.set_header("Access-Control-Allow-Origin", "*");
    response.set_header("Access-Control-Allow-Methods", "GET, OPTIONS");
    response.set_header("Access-Control-Allow-Headers", "Content-Type");
    response.write(payload);
    return response;
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
    try {
        crow::SimpleApp app;
        const auto dataDir = pubchem::cid4http::resolveDataDir();
        auto config = pubchem::cid4http::resolveServerConfig(dataDir);

        if (const auto cliHost = hostOverride(argc, argv); !cliHost.empty()) {
            config.host = cliHost;
        }
        if (const auto cliPort = portOverride(argc, argv); cliPort.has_value()) {
            config.port = *cliPort;
        }

        CROW_ROUTE(app, "/api/health")([](const crow::request& req) {
            const char* mode = req.url_params.get("mode");
            if (mode != nullptr && std::string_view(mode) == "error") {
                return jsonResponse(
                    503, pubchem::cid4http::healthPayload("crow", "Transport error from Crow"));
            }

            return jsonResponse(
                200, pubchem::cid4http::healthPayload("crow", "Crow transport is healthy"));
        });

        CROW_ROUTE(app, "/api/cid4/conformer/<int>")([dataDir](int index) {
            try {
                return jsonResponse(200,
                                    pubchem::cid4http::loadJsonPayload(
                                        pubchem::cid4http::conformerPath(dataDir, index)));
            }
            catch (const std::out_of_range&) {
                return jsonResponse(
                    404, nlohmann::json{{"message", "Unknown conformer " + std::to_string(index)}});
            }
            catch (const std::exception& error) {
                return jsonResponse(404, nlohmann::json{{"message", error.what()}});
            }
        });

        CROW_ROUTE(app, "/api/cid4/structure/2d")([dataDir] {
            try {
                return jsonResponse(200,
                                    pubchem::cid4http::loadJsonPayload(
                                        pubchem::cid4http::structure2dPath(dataDir)));
            }
            catch (const std::exception& error) {
                return jsonResponse(404, nlohmann::json{{"message", error.what()}});
            }
        });

        CROW_ROUTE(app, "/api/cid4/compound")([dataDir] {
            try {
                return jsonResponse(
                    200,
                    pubchem::cid4http::loadJsonPayload(pubchem::cid4http::compoundPath(dataDir)));
            }
            catch (const std::exception& error) {
                return jsonResponse(404, nlohmann::json{{"message", error.what()}});
            }
        });

        CROW_ROUTE(app, "/api/algorithms/pathway")(
            [] { return jsonResponse(200, pubchem::cid4http::pathwayFixture()); });

        CROW_ROUTE(app, "/api/algorithms/bioactivity")(
            [] { return jsonResponse(200, pubchem::cid4http::bioactivityFixture()); });

        CROW_ROUTE(app, "/api/algorithms/taxonomy")(
            [] { return jsonResponse(200, pubchem::cid4http::taxonomyFixture()); });

        auto sslContext = buildSslContext(config);
        std::cout << "Crow API server listening on https://" << config.host << ':' << config.port
                  << '\n';
        app.loglevel(crow::LogLevel::Info)
            .bindaddr(config.host)
            .port(config.port)
            .ssl(std::move(sslContext))
            .multithreaded()
            .run();
    }
    catch (const std::exception& error) {
        std::cerr << "Failed to start Crow API server: " << error.what() << '\n';
        return EXIT_FAILURE;
    }

    return EXIT_SUCCESS;
}
