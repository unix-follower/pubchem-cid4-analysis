#include "cid4_http.hpp"

#include <openssl/err.h>
#include <openssl/ssl.h>

#include <algorithm>
#include <arpa/inet.h>
#include <condition_variable>
#include <csignal>
#include <cstdlib>
#include <cstring>
#include <deque>
#include <exception>
#include <filesystem>
#include <functional>
#include <iostream>
#include <memory>
#include <mutex>
#include <netinet/in.h>
#include <optional>
#include <sstream>
#include <string>
#include <string_view>
#include <sys/socket.h>
#include <thread>
#include <unistd.h>
#include <utility>
#include <vector>

namespace {

volatile std::sig_atomic_t gStopRequested = 0;
int gListenSocket = -1;

enum class ExecutionMode {
    ThreadPerRequest,
    ThreadPool,
};

struct RuntimeConfig {
    ExecutionMode mode = ExecutionMode::ThreadPool;
    std::size_t workerCount = 0;
};

using SslContextHandle = std::unique_ptr<SSL_CTX, decltype(&SSL_CTX_free)>;
using SslHandle = std::unique_ptr<SSL, decltype(&SSL_free)>;

void signalHandler(int)
{
    gStopRequested = 1;
    if (gListenSocket >= 0) {
        ::close(gListenSocket);
        gListenSocket = -1;
    }
}

void installSignalHandlers()
{
    std::signal(SIGINT, signalHandler);
    std::signal(SIGTERM, signalHandler);
    std::signal(SIGPIPE, SIG_IGN);
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
        rawMode = firstEnvValue({"CPP_PLAIN_MODE", "CPP_MODE"});
    }

    std::optional<std::string> rawThreads;
    if (const auto cliThreads = threadsOverride(argc, argv); cliThreads.has_value()) {
        rawThreads = std::to_string(*cliThreads);
    }
    else {
        rawThreads = firstEnvValue({"CPP_PLAIN_THREADS", "CPP_THREADS"});
    }

    RuntimeConfig config;
    if (rawMode.has_value()) {
        config.mode = parseMode(*rawMode);
    }
    config.workerCount = resolveWorkerCount(rawThreads);
    return config;
}

int passwordCallback(char* buffer, int size, int, void* userdata)
{
    const auto* password = static_cast<const std::string*>(userdata);
    if (password == nullptr || size <= 0) {
        return 0;
    }

    const auto copyLength =
        std::min<std::size_t>(password->size(), static_cast<std::size_t>(size - 1));
    std::memcpy(buffer, password->data(), copyLength);
    buffer[copyLength] = '\0';
    return static_cast<int>(copyLength);
}

SslContextHandle buildSslContext(const pubchem::cid4http::ServerConfig& config)
{
    SSL_load_error_strings();
    OPENSSL_init_ssl(0, nullptr);

    SslContextHandle context(SSL_CTX_new(TLS_server_method()), &SSL_CTX_free);
    if (!context) {
        throw std::runtime_error("Unable to create SSL context: " + currentOpenSslError());
    }

    SSL_CTX_set_min_proto_version(context.get(), TLS1_2_VERSION);
    SSL_CTX_set_options(context.get(), SSL_OP_NO_SSLv2 | SSL_OP_NO_SSLv3);

    if (config.keyPassword.has_value()) {
        SSL_CTX_set_default_passwd_cb_userdata(context.get(),
                                               const_cast<std::string*>(&*config.keyPassword));
        SSL_CTX_set_default_passwd_cb(context.get(), passwordCallback);
    }

    if (SSL_CTX_use_certificate_chain_file(context.get(), config.certFile.c_str()) != 1) {
        throw std::runtime_error("Unable to load TLS certificate chain: " + currentOpenSslError());
    }

    if (SSL_CTX_use_PrivateKey_file(context.get(), config.keyFile.c_str(), SSL_FILETYPE_PEM) != 1) {
        throw std::runtime_error("Unable to load TLS private key: " + currentOpenSslError());
    }

    if (SSL_CTX_check_private_key(context.get()) != 1) {
        throw std::runtime_error("TLS private key does not match certificate: " +
                                 currentOpenSslError());
    }

    return context;
}

int createListenSocket(const std::string& host, std::uint16_t port)
{
    const int socketFd = ::socket(AF_INET, SOCK_STREAM, 0);
    if (socketFd < 0) {
        throw std::runtime_error("Unable to create listen socket");
    }

    const int reuse = 1;
    setsockopt(socketFd, SOL_SOCKET, SO_REUSEADDR, &reuse, sizeof(reuse));

    sockaddr_in address{};
    address.sin_family = AF_INET;
    address.sin_port = htons(port);
    if (host == "0.0.0.0") {
        address.sin_addr.s_addr = INADDR_ANY;
    }
    else if (inet_pton(AF_INET, host.c_str(), &address.sin_addr) != 1) {
        ::close(socketFd);
        throw std::runtime_error("Only IPv4 addresses are supported by plain_openssl_api_server: " +
                                 host);
    }

    if (bind(socketFd, reinterpret_cast<sockaddr*>(&address), sizeof(address)) != 0) {
        ::close(socketFd);
        throw std::runtime_error("Unable to bind listen socket to " + host + ':' +
                                 std::to_string(port));
    }

    if (listen(socketFd, SOMAXCONN) != 0) {
        ::close(socketFd);
        throw std::runtime_error("Unable to listen on socket");
    }

    return socketFd;
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

bool writeAll(SSL* ssl, std::string_view payload)
{
    std::size_t written = 0;
    while (written < payload.size()) {
        const auto rc =
            SSL_write(ssl, payload.data() + written, static_cast<int>(payload.size() - written));
        if (rc <= 0) {
            return false;
        }
        written += static_cast<std::size_t>(rc);
    }

    return true;
}

std::optional<std::string> readRequest(SSL* ssl)
{
    std::string request;
    request.reserve(4096);
    char buffer[2048]{};

    while (request.find("\r\n\r\n") == std::string::npos) {
        const auto rc = SSL_read(ssl, buffer, sizeof(buffer));
        if (rc <= 0) {
            return std::nullopt;
        }

        request.append(buffer, static_cast<std::size_t>(rc));
        if (request.size() > 16384) {
            return std::nullopt;
        }
    }

    return request;
}

pubchem::cid4http::ApiResponse malformedRequest()
{
    return pubchem::cid4http::ApiResponse{
        .statusCode = 400,
        .body = R"({"message":"Malformed HTTP request"})",
    };
}

void handleClient(int clientSocket,
                  SSL_CTX* sslContext,
                  const std::filesystem::path& dataDir,
                  std::string_view sourceLabel,
                  std::string_view transportName)
{
    SslHandle ssl(SSL_new(sslContext), &SSL_free);
    if (!ssl) {
        ::close(clientSocket);
        return;
    }

    SSL_set_fd(ssl.get(), clientSocket);
    if (SSL_accept(ssl.get()) <= 0) {
        SSL_shutdown(ssl.get());
        ::close(clientSocket);
        return;
    }

    const auto request = readRequest(ssl.get());
    pubchem::cid4http::ApiResponse response{};

    if (!request.has_value()) {
        response = malformedRequest();
    }
    else {
        std::istringstream input(*request);
        std::string method;
        std::string target;
        std::string httpVersion;
        if (!(input >> method >> target >> httpVersion)) {
            response = malformedRequest();
        }
        else {
            try {
                response = pubchem::cid4http::routeApiRequest(
                    method, target, dataDir, sourceLabel, transportName);
            }
            catch (const std::exception& error) {
                response = pubchem::cid4http::ApiResponse{
                    .statusCode = 500,
                    .body = nlohmann::json{{"message", error.what()}}.dump(),
                };
            }
        }
    }

    const auto payload = renderHttpResponse(response);
    writeAll(ssl.get(), payload);
    SSL_shutdown(ssl.get());
    ::close(clientSocket);
}

class ConnectionQueue {
  public:
    void push(int clientSocket)
    {
        std::lock_guard lock(mutex_);
        queue_.push_back(clientSocket);
        condition_.notify_one();
    }

    std::optional<int> pop()
    {
        std::unique_lock lock(mutex_);
        condition_.wait(lock, [this] { return stop_ || !queue_.empty(); });
        if (queue_.empty()) {
            return std::nullopt;
        }

        const auto clientSocket = queue_.front();
        queue_.pop_front();
        return clientSocket;
    }

    void stop()
    {
        std::lock_guard lock(mutex_);
        stop_ = true;
        condition_.notify_all();
    }

  private:
    std::mutex mutex_;
    std::condition_variable condition_;
    std::deque<int> queue_;
    bool stop_ = false;
};

class ThreadPool {
  public:
    ThreadPool(std::size_t workerCount,
               SSL_CTX* sslContext,
               std::filesystem::path dataDir,
               std::string sourceLabel,
               std::string transportName)
        : sslContext_(sslContext),
          dataDir_(std::move(dataDir)),
          sourceLabel_(std::move(sourceLabel)),
          transportName_(std::move(transportName))
    {
        workers_.reserve(workerCount);
        for (std::size_t index = 0; index < workerCount; ++index) {
            workers_.emplace_back([this] {
                while (true) {
                    const auto clientSocket = queue_.pop();
                    if (!clientSocket.has_value()) {
                        break;
                    }
                    handleClient(
                        *clientSocket, sslContext_, dataDir_, sourceLabel_, transportName_);
                }
            });
        }
    }

    ~ThreadPool()
    {
        stop();
        for (auto& worker : workers_) {
            if (worker.joinable()) {
                worker.join();
            }
        }
    }

    void enqueue(int clientSocket)
    {
        queue_.push(clientSocket);
    }

    void stop()
    {
        queue_.stop();
    }

  private:
    SSL_CTX* sslContext_;
    std::filesystem::path dataDir_;
    std::string sourceLabel_;
    std::string transportName_;
    ConnectionQueue queue_;
    std::vector<std::thread> workers_;
};

} // namespace

int main(int argc, char** argv)
{
    installSignalHandlers();

    try {
        const auto dataDir = pubchem::cid4http::resolveDataDir();
        auto config = pubchem::cid4http::resolveServerConfig(
            dataDir, {"CPP_PLAIN_HOST", "CPP_HOST"}, {"CPP_PLAIN_PORT", "CPP_PORT"});
        const auto runtimeConfig = resolveRuntimeConfig(argc, argv);

        if (const auto cliHost = hostOverride(argc, argv); !cliHost.empty()) {
            config.host = cliHost;
        }
        if (const auto cliPort = portOverride(argc, argv); cliPort.has_value()) {
            config.port = *cliPort;
        }

        auto sslContext = buildSslContext(config);
        const int listenSocket = createListenSocket(config.host, config.port);
        gListenSocket = listenSocket;

        std::cout << "Plain OpenSSL API server listening on https://" << config.host << ':'
                  << config.port << " using " << modeLabel(runtimeConfig.mode);
        if (runtimeConfig.mode == ExecutionMode::ThreadPool) {
            std::cout << " with " << runtimeConfig.workerCount << " workers";
        }
        std::cout << '\n';

        if (runtimeConfig.mode == ExecutionMode::ThreadPool) {
            ThreadPool threadPool(
                runtimeConfig.workerCount, sslContext.get(), dataDir, "cpp-plain", "Plain OpenSSL");

            while (!gStopRequested) {
                const int clientSocket = accept(listenSocket, nullptr, nullptr);
                if (clientSocket < 0) {
                    if (gStopRequested) {
                        break;
                    }
                    continue;
                }
                threadPool.enqueue(clientSocket);
            }

            threadPool.stop();
        }
        else {
            std::vector<std::thread> requestThreads;
            while (!gStopRequested) {
                const int clientSocket = accept(listenSocket, nullptr, nullptr);
                if (clientSocket < 0) {
                    if (gStopRequested) {
                        break;
                    }
                    continue;
                }

                requestThreads.emplace_back([clientSocket, ctx = sslContext.get(), dataDir] {
                    handleClient(clientSocket, ctx, dataDir, "cpp-plain", "Plain OpenSSL");
                });
            }

            for (auto& requestThread : requestThreads) {
                if (requestThread.joinable()) {
                    requestThread.join();
                }
            }
        }

        if (gListenSocket >= 0) {
            ::close(gListenSocket);
            gListenSocket = -1;
        }
    }
    catch (const std::exception& error) {
        std::cerr << "Failed to start plain OpenSSL API server: " << error.what() << '\n';
        return EXIT_FAILURE;
    }

    return EXIT_SUCCESS;
}
