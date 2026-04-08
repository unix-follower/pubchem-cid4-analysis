#include "cid4_http.hpp"

#include <boost/asio.hpp>
#include <boost/asio/ssl.hpp>

#include <algorithm>
#include <csignal>
#include <cstdlib>
#include <exception>
#include <filesystem>
#include <functional>
#include <iostream>
#include <memory>
#include <optional>
#include <sstream>
#include <string>
#include <string_view>
#include <thread>
#include <utility>
#include <vector>

namespace {

namespace asio = boost::asio;
namespace ssl = asio::ssl;
using tcp = asio::ip::tcp;

enum class ExecutionMode {
    ThreadPerRequest,
    ThreadPool,
};

struct RuntimeConfig {
    ExecutionMode mode = ExecutionMode::ThreadPool;
    std::size_t workerCount = 0;
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

std::optional<std::string> modeOverride(int argc, char** argv)
{
    for (int index = 1; index < argc; ++index) {
        if (std::string_view(argv[index]) == "--mode" && index + 1 < argc) {
            return std::string(argv[index + 1]);
        }
    }

    return std::nullopt;
}

std::optional<std::size_t> threadsOverride(int argc, char** argv)
{
    for (int index = 1; index < argc; ++index) {
        if (std::string_view(argv[index]) == "--threads" && index + 1 < argc) {
            try {
                const auto parsed = std::stoul(argv[index + 1]);
                if (parsed > 0) {
                    return static_cast<std::size_t>(parsed);
                }
            }
            catch (const std::exception&) {
                return std::nullopt;
            }
        }
    }

    return std::nullopt;
}

std::optional<std::string> firstEnvValue(std::initializer_list<const char*> names)
{
    for (const char* name : names) {
        if (const char* value = std::getenv(name); value != nullptr && value[0] != '\0') {
            return std::string(value);
        }
    }

    return std::nullopt;
}

ExecutionMode parseMode(std::string_view rawMode)
{
    if (rawMode == "thread-per-request" || rawMode == "thread_per_request" ||
        rawMode == "blocking") {
        return ExecutionMode::ThreadPerRequest;
    }

    if (rawMode == "thread-pool" || rawMode == "thread_pool" || rawMode == "nonblocking" ||
        rawMode == "non-blocking") {
        return ExecutionMode::ThreadPool;
    }

    throw std::runtime_error("Unsupported execution mode: " + std::string(rawMode));
}

std::string modeLabel(ExecutionMode mode)
{
    return mode == ExecutionMode::ThreadPerRequest ? "thread-per-request" : "thread-pool";
}

std::size_t resolveWorkerCount(const std::optional<std::string>& rawValue)
{
    if (!rawValue.has_value()) {
        const auto hardware = std::thread::hardware_concurrency();
        return hardware == 0 ? 4U : static_cast<std::size_t>(hardware);
    }

    try {
        const auto parsed = std::stoul(*rawValue);
        if (parsed == 0) {
            throw std::runtime_error("Worker count must be greater than zero");
        }
        return static_cast<std::size_t>(parsed);
    }
    catch (const std::exception&) {
        throw std::runtime_error("Invalid worker count: " + *rawValue);
    }
}

RuntimeConfig resolveRuntimeConfig(int argc, char** argv)
{
    auto rawMode = modeOverride(argc, argv);
    if (!rawMode.has_value()) {
        rawMode = firstEnvValue({"CPP_ASIO_MODE", "CPP_MODE"});
    }

    std::optional<std::string> rawThreads;
    if (const auto cliThreads = threadsOverride(argc, argv); cliThreads.has_value()) {
        rawThreads = std::to_string(*cliThreads);
    }
    else {
        rawThreads = firstEnvValue({"CPP_ASIO_THREADS", "CPP_THREADS"});
    }

    RuntimeConfig config;
    if (rawMode.has_value()) {
        config.mode = parseMode(*rawMode);
    }
    config.workerCount = resolveWorkerCount(rawThreads);
    return config;
}

std::string reasonPhrase(int statusCode)
{
    switch (statusCode) {
    case 200:
        return "OK";
    case 204:
        return "No Content";
    case 400:
        return "Bad Request";
    case 404:
        return "Not Found";
    case 405:
        return "Method Not Allowed";
    case 500:
        return "Internal Server Error";
    case 503:
        return "Service Unavailable";
    default:
        return "OK";
    }
}

std::string renderHttpResponse(const pubchem::cid4http::ApiResponse& response)
{
    std::ostringstream output;
    output << "HTTP/1.1 " << response.statusCode << ' ' << reasonPhrase(response.statusCode)
           << "\r\n";
    output << "Content-Type: " << response.contentType << "\r\n";
    output << "Access-Control-Allow-Origin: *\r\n";
    output << "Access-Control-Allow-Methods: GET, OPTIONS\r\n";
    output << "Access-Control-Allow-Headers: Content-Type\r\n";
    output << "Connection: close\r\n";
    if (response.statusCode == 405) {
        output << "Allow: GET, OPTIONS\r\n";
    }
    output << "Content-Length: " << response.body.size() << "\r\n\r\n";
    output << response.body;
    return output.str();
}

pubchem::cid4http::ApiResponse malformedRequest()
{
    return pubchem::cid4http::ApiResponse{
        .statusCode = 400,
        .body = R"({"message":"Malformed HTTP request"})",
    };
}

pubchem::cid4http::ApiResponse
routeOrFail(std::string_view method, std::string_view target, const std::filesystem::path& dataDir)
{
    try {
        return pubchem::cid4http::routeApiRequest(
            method, target, dataDir, "cpp-asio", "Boost.Asio");
    }
    catch (const std::exception& error) {
        return pubchem::cid4http::ApiResponse{
            .statusCode = 500,
            .body = nlohmann::json{{"message", error.what()}}.dump(),
        };
    }
}

pubchem::cid4http::ApiResponse buildResponseFromRequest(std::string_view request,
                                                        const std::filesystem::path& dataDir)
{
    std::istringstream input{std::string(request)};
    std::string method;
    std::string target;
    std::string httpVersion;
    if (!(input >> method >> target >> httpVersion)) {
        return malformedRequest();
    }

    return routeOrFail(method, target, dataDir);
}

void configureSslContext(ssl::context& context, const pubchem::cid4http::ServerConfig& config)
{
    context.set_options(ssl::context::default_workarounds | ssl::context::no_sslv2 |
                        ssl::context::no_sslv3 | ssl::context::single_dh_use);

    if (config.keyPassword.has_value()) {
        const auto password = *config.keyPassword;
        context.set_password_callback(
            [password](std::size_t, ssl::context::password_purpose) { return password; });
    }

    context.use_certificate_chain_file(config.certFile.string());
    context.use_private_key_file(config.keyFile.string(), ssl::context::pem);
}

tcp::endpoint resolveEndpoint(const std::string& host, std::uint16_t port)
{
    if (host == "0.0.0.0") {
        return tcp::endpoint(asio::ip::address_v4::any(), port);
    }

    return tcp::endpoint(asio::ip::make_address(host), port);
}

class AsyncSession : public std::enable_shared_from_this<AsyncSession> {
  public:
    AsyncSession(tcp::socket socket, ssl::context& sslContext, std::filesystem::path dataDir)
        : stream_(std::move(socket), sslContext), dataDir_(std::move(dataDir))
    {}

    void start()
    {
        auto self = shared_from_this();
        stream_.async_handshake(ssl::stream_base::server,
                                [self](const boost::system::error_code& error) {
                                    if (error) {
                                        self->shutdown();
                                        return;
                                    }

                                    self->readRequest();
                                });
    }

  private:
    void readRequest()
    {
        auto self = shared_from_this();
        asio::async_read_until(stream_,
                               asio::dynamic_buffer(request_),
                               "\r\n\r\n",
                               [self](const boost::system::error_code& error, std::size_t) {
                                   if (error) {
                                       self->shutdown();
                                       return;
                                   }

                                   if (self->request_.size() > 16384) {
                                       self->response_ = renderHttpResponse(malformedRequest());
                                   }
                                   else {
                                       self->response_ =
                                           renderHttpResponse(buildResponseFromRequest(
                                               self->request_, self->dataDir_));
                                   }
                                   self->writeResponse();
                               });
    }

    void writeResponse()
    {
        auto self = shared_from_this();
        asio::async_write(
            stream_,
            asio::buffer(response_),
            [self](const boost::system::error_code&, std::size_t) { self->shutdown(); });
    }

    void shutdown()
    {
        boost::system::error_code ignored;
        stream_.shutdown(ignored);
        stream_.lowest_layer().close(ignored);
    }

    ssl::stream<tcp::socket> stream_;
    std::filesystem::path dataDir_;
    std::string request_;
    std::string response_;
};

void handleSyncSession(tcp::socket socket,
                       ssl::context& sslContext,
                       const std::filesystem::path& dataDir)
{
    ssl::stream<tcp::socket> stream(std::move(socket), sslContext);
    boost::system::error_code error;
    stream.handshake(ssl::stream_base::server, error);
    if (error) {
        stream.lowest_layer().close(error);
        return;
    }

    std::string request;
    asio::read_until(stream, asio::dynamic_buffer(request), "\r\n\r\n", error);

    pubchem::cid4http::ApiResponse response = malformedRequest();
    if (!error) {
        if (request.size() > 16384) {
            response = malformedRequest();
        }
        else {
            response = buildResponseFromRequest(request, dataDir);
        }
    }

    const auto payload = renderHttpResponse(response);
    asio::write(stream, asio::buffer(payload), error);
    stream.shutdown(error);
    stream.lowest_layer().close(error);
}

void configureAcceptor(tcp::acceptor& acceptor, const tcp::endpoint& endpoint)
{
    acceptor.open(endpoint.protocol());
    acceptor.set_option(tcp::acceptor::reuse_address(true));
    acceptor.bind(endpoint);
    acceptor.listen(asio::socket_base::max_listen_connections);
}

} // namespace

int main(int argc, char** argv)
{
    std::signal(SIGPIPE, SIG_IGN);

    try {
        const auto dataDir = pubchem::cid4http::resolveDataDir();
        auto config = pubchem::cid4http::resolveServerConfig(
            dataDir, {"CPP_ASIO_HOST", "CPP_HOST"}, {"CPP_ASIO_PORT", "CPP_PORT"});
        const auto runtimeConfig = resolveRuntimeConfig(argc, argv);

        if (const auto cliHost = hostOverride(argc, argv); !cliHost.empty()) {
            config.host = cliHost;
        }
        if (const auto cliPort = portOverride(argc, argv); cliPort.has_value()) {
            config.port = *cliPort;
        }

        asio::io_context ioContext;
        ssl::context sslContext(ssl::context::tls_server);
        configureSslContext(sslContext, config);

        tcp::acceptor acceptor(ioContext);
        configureAcceptor(acceptor, resolveEndpoint(config.host, config.port));

        asio::signal_set signals(ioContext, SIGINT, SIGTERM);
        signals.async_wait([&](const boost::system::error_code&, int) {
            boost::system::error_code ignored;
            acceptor.close(ignored);
            ioContext.stop();
        });

        std::cout << "Boost.Asio API server listening on https://" << config.host << ':'
                  << config.port << " using " << modeLabel(runtimeConfig.mode);
        if (runtimeConfig.mode == ExecutionMode::ThreadPool) {
            std::cout << " with " << runtimeConfig.workerCount << " workers";
        }
        std::cout << '\n';

        if (runtimeConfig.mode == ExecutionMode::ThreadPool) {
            std::function<void()> acceptNext;
            acceptNext = [&] {
                acceptor.async_accept(
                    [&](const boost::system::error_code& error, tcp::socket socket) {
                        if (!error) {
                            std::make_shared<AsyncSession>(std::move(socket), sslContext, dataDir)
                                ->start();
                        }

                        if (error != asio::error::operation_aborted) {
                            acceptNext();
                        }
                    });
            };

            acceptNext();

            std::vector<std::thread> workers;
            workers.reserve(runtimeConfig.workerCount);
            for (std::size_t index = 0; index < runtimeConfig.workerCount; ++index) {
                workers.emplace_back([&] { ioContext.run(); });
            }

            for (auto& worker : workers) {
                if (worker.joinable()) {
                    worker.join();
                }
            }
        }
        else {
            std::vector<std::thread> requestThreads;
            std::function<void()> acceptNext;
            acceptNext = [&] {
                acceptor.async_accept(
                    [&](const boost::system::error_code& error, tcp::socket socket) {
                        if (!error) {
                            requestThreads.emplace_back(
                                [socket = std::move(socket), &sslContext, dataDir]() mutable {
                                    handleSyncSession(std::move(socket), sslContext, dataDir);
                                });
                        }

                        if (error != asio::error::operation_aborted) {
                            acceptNext();
                        }
                    });
            };

            acceptNext();
            ioContext.run();

            for (auto& requestThread : requestThreads) {
                if (requestThread.joinable()) {
                    requestThread.join();
                }
            }
        }
    }
    catch (const std::exception& error) {
        std::cerr << "Failed to start Boost.Asio API server: " << error.what() << '\n';
        return EXIT_FAILURE;
    }

    return EXIT_SUCCESS;
}
