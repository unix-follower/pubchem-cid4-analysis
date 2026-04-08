#pragma once

#include <prometheus/counter.h>
#include <prometheus/exposer.h>
#include <prometheus/gauge.h>
#include <prometheus/histogram.h>
#include <prometheus/registry.h>

#include <spdlog/logger.h>

#include <chrono>
#include <cstdint>
#include <memory>
#include <mutex>
#include <optional>
#include <string>
#include <string_view>
#include <unordered_map>

namespace pubchem::cid4observability {

struct ObservabilityConfig {
    bool enabled = true;
    bool loggingEnabled = true;
    bool metricsEnabled = true;
    bool tracingEnabled = true;
    std::string serviceName = "pubchem-cid4-oatpp";
    std::string logLevel = "info";
    std::string metricsHost = "0.0.0.0";
    std::uint16_t metricsPort = 9464;
};

struct CompletedRequest {
    std::string_view method;
    std::string_view route;
    std::string_view target;
    int statusCode;
    double durationMs;
    std::string_view requestId;
    std::string_view traceId;
    std::string_view spanId;
};

class Runtime;

ObservabilityConfig resolveObservabilityConfig(std::string_view servicePrefix,
                                               std::string_view defaultServiceName);
std::shared_ptr<Runtime> initialize(const ObservabilityConfig& config);
void shutdown(const std::shared_ptr<Runtime>& runtime);

class RequestScope {
  public:
    RequestScope(std::shared_ptr<Runtime> runtime,
                 std::string method,
                 std::string route,
                 std::string target,
                 std::optional<std::string> incomingRequestId = std::nullopt);

    RequestScope(const RequestScope&) = delete;
    RequestScope& operator=(const RequestScope&) = delete;
    RequestScope(RequestScope&&) = delete;
    RequestScope& operator=(RequestScope&&) = delete;

    ~RequestScope();

    void finish(int statusCode);

    [[nodiscard]] const std::string& requestId() const;
    [[nodiscard]] const std::string& traceId() const;
    [[nodiscard]] const std::string& spanId() const;
    [[nodiscard]] std::string traceparent() const;

  private:
    std::shared_ptr<Runtime> runtime_;
    std::string method_;
    std::string route_;
    std::string target_;
    std::string requestId_;
    std::string traceId_;
    std::string spanId_;
    bool finished_ = false;
    std::chrono::steady_clock::time_point startTime_;
};

class Runtime {
  public:
    explicit Runtime(ObservabilityConfig config);
    ~Runtime();

    Runtime(const Runtime&) = delete;
    Runtime& operator=(const Runtime&) = delete;
    Runtime(Runtime&&) = delete;
    Runtime& operator=(Runtime&&) = delete;

    void logStartup(std::string_view host, std::uint16_t port) const;
    void logStartupFailure(std::string_view message) const;
    void flushAndShutdown();

    [[nodiscard]] bool enabled() const;
    [[nodiscard]] const ObservabilityConfig& config() const;

    void recordRequest(const CompletedRequest& request) const;

  private:
    ObservabilityConfig config_;
    std::shared_ptr<spdlog::logger> logger_;
    std::shared_ptr<prometheus::Exposer> exposer_;
    std::shared_ptr<prometheus::Registry> registry_;
    prometheus::Family<prometheus::Counter>* requestCounterFamily_ = nullptr;
    prometheus::Family<prometheus::Counter>* requestErrorCounterFamily_ = nullptr;
    prometheus::Family<prometheus::Histogram>* requestDurationFamily_ = nullptr;
    prometheus::Family<prometheus::Gauge>* processUpFamily_ = nullptr;
    mutable std::mutex metricsMutex_;
    mutable std::unordered_map<std::string, prometheus::Counter*> requestCounters_;
    mutable std::unordered_map<std::string, prometheus::Counter*> requestErrorCounters_;
    mutable std::unordered_map<std::string, prometheus::Histogram*> requestDurationHistograms_;
    prometheus::Gauge* processUpGauge_ = nullptr;
    bool shutdown_ = false;

    void initializeLogging();
    void initializeMetrics();
    void initializeTracing();
};

} // namespace pubchem::cid4observability
