#include "observability.hpp"

#include <prometheus/counter.h>
#include <prometheus/exposer.h>
#include <prometheus/gauge.h>
#include <prometheus/histogram.h>
#include <prometheus/registry.h>

#include <spdlog/sinks/stdout_color_sinks.h>
#include <spdlog/spdlog.h>

#include <array>
#include <cctype>
#include <chrono>
#include <cstdlib>
#include <exception>
#include <format>
#include <initializer_list>
#include <mutex>
#include <random>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

namespace pubchem::cid4observability {
namespace cid4observability_detail {

std::optional<std::string> envValue(const std::string& name)
{
    if (name.empty()) {
        return std::nullopt;
    }

    if (const char* value = std::getenv(name.c_str()); value != nullptr && value[0] != '\0') {
        return std::string(value);
    }

    return std::nullopt;
}

std::optional<std::string> firstEnvValue(std::initializer_list<std::string> names)
{
    for (const auto& name : names) {
        if (const auto value = envValue(name); value.has_value()) {
            return value;
        }
    }

    return std::nullopt;
}

bool parseBool(std::string_view value, bool fallback)
{
    if (value == "1" || value == "true" || value == "TRUE" || value == "on" || value == "ON" ||
        value == "yes" || value == "YES") {
        return true;
    }

    if (value == "0" || value == "false" || value == "FALSE" || value == "off" || value == "OFF" ||
        value == "no" || value == "NO") {
        return false;
    }

    return fallback;
}

std::optional<std::uint16_t> parsePort(const std::optional<std::string>& value)
{
    if (!value.has_value()) {
        return std::nullopt;
    }

    try {
        const auto parsed = std::stoul(*value);
        if (parsed > 0 && parsed <= 65535) {
            return static_cast<std::uint16_t>(parsed);
        }
    }
    catch (const std::invalid_argument&) {
        return std::nullopt;
    }
    catch (const std::out_of_range&) {
        return std::nullopt;
    }

    return std::nullopt;
}

std::string prefixedName(std::string_view prefix, std::string_view name)
{
    if (prefix.empty()) {
        return std::string(name);
    }

    return std::string(prefix) + "_" + std::string(name);
}

std::string normalizeLevel(std::string level)
{
    for (char& ch : level) {
        ch = static_cast<char>(std::tolower(static_cast<unsigned char>(ch)));
    }

    return level;
}

spdlog::level::level_enum toLogLevel(const std::string& level)
{
    return spdlog::level::from_str(level);
}

std::string generateHexId(std::size_t bytes)
{
    static thread_local std::mt19937_64 generator(std::random_device{}());
    static constexpr char kHex[] = "0123456789abcdef";

    std::string value(bytes * 2, '0');
    for (std::size_t index = 0; index < bytes; ++index) {
        const auto randomValue = static_cast<unsigned long long>(generator());
        value[index * 2] = kHex[(randomValue >> 4U) & 0x0fU];
        value[(index * 2) + 1] = kHex[randomValue & 0x0fU];
    }

    return value;
}

std::string statusClass(int statusCode)
{
    if (statusCode >= 500) {
        return "5xx";
    }
    if (statusCode >= 400) {
        return "4xx";
    }
    if (statusCode >= 300) {
        return "3xx";
    }
    if (statusCode >= 200) {
        return "2xx";
    }
    return "1xx";
}

std::string metricKey(std::string_view method, std::string_view route, std::string_view suffix)
{
    return std::string(method) + "|" + std::string(route) + "|" + std::string(suffix);
}

} // namespace cid4observability_detail

ObservabilityConfig resolveObservabilityConfig(std::string_view servicePrefix,
                                               std::string_view defaultServiceName)
{
    ObservabilityConfig config;
    config.serviceName = std::string(defaultServiceName);

    if (const auto value = cid4observability_detail::firstEnvValue(
            {cid4observability_detail::prefixedName(servicePrefix, "OBSERVABILITY_ENABLED"),
             "OBSERVABILITY_ENABLED"});
        value.has_value()) {
        config.enabled = cid4observability_detail::parseBool(*value, config.enabled);
    }

    if (const auto value = cid4observability_detail::firstEnvValue(
            {cid4observability_detail::prefixedName(servicePrefix, "LOGGING_ENABLED"),
             "OBSERVABILITY_LOGGING_ENABLED"});
        value.has_value()) {
        config.loggingEnabled = cid4observability_detail::parseBool(*value, config.loggingEnabled);
    }

    if (const auto value = cid4observability_detail::firstEnvValue(
            {cid4observability_detail::prefixedName(servicePrefix, "METRICS_ENABLED"),
             "OBSERVABILITY_METRICS_ENABLED"});
        value.has_value()) {
        config.metricsEnabled = cid4observability_detail::parseBool(*value, config.metricsEnabled);
    }

    if (const auto value = cid4observability_detail::firstEnvValue(
            {cid4observability_detail::prefixedName(servicePrefix, "TRACING_ENABLED"),
             "OBSERVABILITY_TRACING_ENABLED"});
        value.has_value()) {
        config.tracingEnabled = cid4observability_detail::parseBool(*value, config.tracingEnabled);
    }

    if (const auto value = cid4observability_detail::firstEnvValue(
            {cid4observability_detail::prefixedName(servicePrefix, "SERVICE_NAME"),
             "OTEL_SERVICE_NAME"});
        value.has_value()) {
        config.serviceName = *value;
    }

    if (const auto value = cid4observability_detail::firstEnvValue(
            {cid4observability_detail::prefixedName(servicePrefix, "LOG_LEVEL"),
             "OBSERVABILITY_LOG_LEVEL",
             "LOG_LEVEL"});
        value.has_value()) {
        config.logLevel = cid4observability_detail::normalizeLevel(*value);
    }

    if (const auto value = cid4observability_detail::firstEnvValue(
            {cid4observability_detail::prefixedName(servicePrefix, "METRICS_HOST"),
             "OBSERVABILITY_METRICS_HOST"});
        value.has_value()) {
        config.metricsHost = *value;
    }

    if (const auto value =
            cid4observability_detail::parsePort(cid4observability_detail::firstEnvValue(
                {cid4observability_detail::prefixedName(servicePrefix, "METRICS_PORT"),
                 "OBSERVABILITY_METRICS_PORT"}));
        value.has_value()) {
        config.metricsPort = *value;
    }

    return config;
}

Runtime::Runtime(ObservabilityConfig config) : config_(std::move(config))
{
    initializeLogging();

    if (!config_.enabled) {
        return;
    }

    if (config_.metricsEnabled) {
        initializeMetrics();
    }

    if (config_.tracingEnabled) {
        initializeTracing();
    }
}

Runtime::~Runtime()
{
    flushAndShutdown();
}

void Runtime::initializeLogging()
{
    if (!config_.loggingEnabled) {
        return;
    }

    logger_ = spdlog::get(config_.serviceName);
    if (!logger_) {
        logger_ = spdlog::stdout_color_mt(config_.serviceName);
    }

    logger_->set_pattern("[%Y-%m-%dT%H:%M:%S.%e] [%^%l%$] %v");
    logger_->set_level(cid4observability_detail::toLogLevel(config_.logLevel));
    logger_->flush_on(spdlog::level::info);
}

void Runtime::initializeMetrics()
{
    registry_ = std::make_shared<prometheus::Registry>();
    exposer_ = std::make_shared<prometheus::Exposer>(config_.metricsHost + ":" +
                                                     std::to_string(config_.metricsPort));
    exposer_->RegisterCollectable(registry_);

    requestCounterFamily_ = &prometheus::BuildCounter()
                                 .Name("cid4_http_requests_total")
                                 .Help("Total number of completed HTTP requests")
                                 .Register(*registry_);
    requestErrorCounterFamily_ =
        &prometheus::BuildCounter()
             .Name("cid4_http_request_errors_total")
             .Help("Total number of completed HTTP requests with status >= 400")
             .Register(*registry_);
    requestDurationFamily_ = &prometheus::BuildHistogram()
                                  .Name("cid4_http_request_duration_milliseconds")
                                  .Help("HTTP request duration in milliseconds")
                                  .Register(*registry_);
    processUpFamily_ = &prometheus::BuildGauge()
                            .Name("cid4_process_up")
                            .Help("Process liveness gauge")
                            .Register(*registry_);

    processUpGauge_ = &processUpFamily_->Add({{"service", config_.serviceName}});
    processUpGauge_->Set(1.0);
}

void Runtime::initializeTracing()
{
    if (logger_) {
        logger_->info("event=tracing_enabled service={} strategy=request-scope",
                      config_.serviceName);
    }
}

void Runtime::logStartup(std::string_view host, std::uint16_t port) const
{
    if (!logger_) {
        return;
    }

    logger_->info("event=server_started service={} listen_host={} listen_port={} "
                  "metrics_enabled={} metrics_host={} metrics_port={} tracing_enabled={}",
                  config_.serviceName,
                  host,
                  port,
                  config_.enabled && config_.metricsEnabled,
                  config_.metricsHost,
                  config_.metricsPort,
                  config_.enabled && config_.tracingEnabled);
}

void Runtime::logStartupFailure(std::string_view message) const
{
    if (logger_) {
        logger_->error(
            "event=server_start_failed service={} message={}", config_.serviceName, message);
    }
}

void Runtime::flushAndShutdown()
{
    if (shutdown_) {
        return;
    }
    shutdown_ = true;

    if (processUpGauge_ != nullptr) {
        processUpGauge_->Set(0.0);
    }

    exposer_.reset();
    registry_.reset();

    if (logger_) {
        logger_->flush();
    }
}

bool Runtime::enabled() const
{
    return config_.enabled;
}

const ObservabilityConfig& Runtime::config() const
{
    return config_;
}

void Runtime::recordRequest(const CompletedRequest& request) const
{
    if (logger_) {
        logger_->info("event=request_completed service={} method={} route={} target={} status={} "
                      "duration_ms={} request_id={} trace_id={} span_id={}",
                      config_.serviceName,
                      request.method,
                      request.route,
                      request.target,
                      request.statusCode,
                      request.durationMs,
                      request.requestId,
                      request.traceId,
                      request.spanId);
    }

    if (!config_.enabled || !config_.metricsEnabled || registry_ == nullptr ||
        requestCounterFamily_ == nullptr || requestDurationFamily_ == nullptr) {
        return;
    }

    std::scoped_lock lock(metricsMutex_);

    const auto counterKey = cid4observability_detail::metricKey(
        request.method, request.route, std::to_string(request.statusCode));
    auto counterIt = requestCounters_.find(counterKey);
    if (counterIt == requestCounters_.end()) {
        counterIt = requestCounters_
                        .emplace(counterKey,
                                 &requestCounterFamily_->Add(
                                     {{"service", config_.serviceName},
                                      {"method", std::string(request.method)},
                                      {"route", std::string(request.route)},
                                      {"status", std::to_string(request.statusCode)},
                                      {"status_class",
                                       cid4observability_detail::statusClass(request.statusCode)}}))
                        .first;
    }
    counterIt->second->Increment();

    const auto histogramKey =
        cid4observability_detail::metricKey(request.method, request.route, "duration");
    auto histogramIt = requestDurationHistograms_.find(histogramKey);
    if (histogramIt == requestDurationHistograms_.end()) {
        histogramIt = requestDurationHistograms_
                          .emplace(histogramKey,
                                   &requestDurationFamily_->Add(
                                       {{"service", config_.serviceName},
                                        {"method", std::string(request.method)},
                                        {"route", std::string(request.route)}},
                                       prometheus::Histogram::BucketBoundaries{1.0,
                                                                               5.0,
                                                                               10.0,
                                                                               25.0,
                                                                               50.0,
                                                                               100.0,
                                                                               250.0,
                                                                               500.0,
                                                                               1000.0,
                                                                               2500.0,
                                                                               5000.0}))
                          .first;
    }
    histogramIt->second->Observe(request.durationMs);

    if (request.statusCode >= 400 && requestErrorCounterFamily_ != nullptr) {
        const auto errorKey = cid4observability_detail::metricKey(
            request.method, request.route, std::format("error-{}", request.statusCode));
        auto errorIt = requestErrorCounters_.find(errorKey);
        if (errorIt == requestErrorCounters_.end()) {
            errorIt =
                requestErrorCounters_
                    .emplace(errorKey,
                             &requestErrorCounterFamily_->Add(
                                 {{"service", config_.serviceName},
                                  {"method", std::string(request.method)},
                                  {"route", std::string(request.route)},
                                  {"status", std::to_string(request.statusCode)},
                                  {"status_class",
                                   cid4observability_detail::statusClass(request.statusCode)}}))
                    .first;
        }
        errorIt->second->Increment();
    }
}

std::shared_ptr<Runtime> initialize(const ObservabilityConfig& config)
{
    return std::make_shared<Runtime>(config);
}

void shutdown(const std::shared_ptr<Runtime>& runtime)
{
    if (runtime) {
        runtime->flushAndShutdown();
    }
}

RequestScope::RequestScope(std::shared_ptr<Runtime> runtime,
                           std::string method,
                           std::string route,
                           std::string target,
                           std::optional<std::string> incomingRequestId)
    : runtime_(std::move(runtime)),
      method_(std::move(method)),
      route_(std::move(route)),
      target_(std::move(target)),
      requestId_(incomingRequestId.value_or(cid4observability_detail::generateHexId(16))),
      startTime_(std::chrono::steady_clock::now())
{
    traceId_ = cid4observability_detail::generateHexId(16);
    spanId_ = cid4observability_detail::generateHexId(8);
}

RequestScope::~RequestScope()
{
    finish(500);
}

void RequestScope::finish(int statusCode)
{
    if (finished_) {
        return;
    }
    finished_ = true;

    const auto duration =
        std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - startTime_);

    if (runtime_) {
        runtime_->recordRequest(CompletedRequest{.method = method_,
                                                 .route = route_,
                                                 .target = target_,
                                                 .statusCode = statusCode,
                                                 .durationMs = duration.count(),
                                                 .requestId = requestId_,
                                                 .traceId = traceId_,
                                                 .spanId = spanId_});
    }
}

const std::string& RequestScope::requestId() const
{
    return requestId_;
}

const std::string& RequestScope::traceId() const
{
    return traceId_;
}

const std::string& RequestScope::spanId() const
{
    return spanId_;
}

std::string RequestScope::traceparent() const
{
    return std::format("00-{}-{}-01", traceId_, spanId_);
}

} // namespace pubchem::cid4observability