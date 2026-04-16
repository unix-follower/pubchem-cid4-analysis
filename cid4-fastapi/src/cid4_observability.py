from __future__ import annotations

import logging
import secrets
import threading
from dataclasses import dataclass
from time import perf_counter

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, start_http_server


@dataclass(frozen=True)
class ObservabilityConfig:
    enabled: bool = True
    logging_enabled: bool = True
    metrics_enabled: bool = True
    tracing_enabled: bool = True
    service_name: str = "pubchem-cid4-fastapi"
    log_level: str = "info"
    metrics_host: str = "0.0.0.0"
    metrics_port: int = 9464


@dataclass(frozen=True)
class CompletedRequest:
    method: str
    route: str
    target: str
    status_code: int
    duration_ms: float
    request_id: str
    trace_id: str
    span_id: str


def resolve_observability_config(
    service_prefix: str,
    default_service_name: str,
    environ: dict[str, str] | None = None,
) -> ObservabilityConfig:
    env = dict(environ) if environ is not None else __import__("os").environ
    normalized_prefix = service_prefix.strip().upper()

    def prefixed(name: str) -> str:
        return name if not normalized_prefix else f"{normalized_prefix}_{name}"

    def first_value(*names: str) -> str | None:
        for name in names:
            value = env.get(name)
            if value is not None:
                stripped = value.strip()
                if stripped:
                    return stripped
        return None

    def parse_bool(value: str, fallback: bool) -> bool:
        normalized = value.strip().lower()
        if normalized in {"1", "true", "on", "yes"}:
            return True
        if normalized in {"0", "false", "off", "no"}:
            return False
        return fallback

    def parse_port(value: str | None, fallback: int) -> int:
        if value is None:
            return fallback
        try:
            parsed = int(value)
        except ValueError:
            return fallback
        if 0 < parsed <= 65535:
            return parsed
        return fallback

    enabled_value = first_value(prefixed("OBSERVABILITY_ENABLED"), "OBSERVABILITY_ENABLED")
    logging_enabled_value = first_value(prefixed("LOGGING_ENABLED"), "OBSERVABILITY_LOGGING_ENABLED")
    metrics_enabled_value = first_value(prefixed("METRICS_ENABLED"), "OBSERVABILITY_METRICS_ENABLED")
    tracing_enabled_value = first_value(prefixed("TRACING_ENABLED"), "OBSERVABILITY_TRACING_ENABLED")
    service_name = first_value(prefixed("SERVICE_NAME"), "OTEL_SERVICE_NAME") or default_service_name
    log_level = (first_value(prefixed("LOG_LEVEL"), "OBSERVABILITY_LOG_LEVEL", "LOG_LEVEL") or "info").lower()
    metrics_host = first_value(prefixed("METRICS_HOST"), "OBSERVABILITY_METRICS_HOST") or "0.0.0.0"
    metrics_port = parse_port(
        first_value(prefixed("METRICS_PORT"), "OBSERVABILITY_METRICS_PORT"),
        9464,
    )

    return ObservabilityConfig(
        enabled=parse_bool(enabled_value, True) if enabled_value is not None else True,
        logging_enabled=(parse_bool(logging_enabled_value, True) if logging_enabled_value is not None else True),
        metrics_enabled=(parse_bool(metrics_enabled_value, True) if metrics_enabled_value is not None else True),
        tracing_enabled=(parse_bool(tracing_enabled_value, True) if tracing_enabled_value is not None else True),
        service_name=service_name,
        log_level=log_level,
        metrics_host=metrics_host,
        metrics_port=metrics_port,
    )


class Runtime:
    def __init__(self, config: ObservabilityConfig):
        self.config = config
        self._logger = logging.getLogger(config.service_name)
        self._metrics_server = None
        self._metrics_thread: threading.Thread | None = None
        self._shutdown = False

        if self.config.logging_enabled:
            level_name = self.config.log_level.upper()
            self._logger.setLevel(getattr(logging, level_name, logging.INFO))

        self._registry: CollectorRegistry | None = None
        self._request_counter = None
        self._error_counter = None
        self._duration_histogram = None
        self._process_up = None

        if self.config.enabled and self.config.metrics_enabled:
            self._initialize_metrics()

        if self.config.enabled and self.config.tracing_enabled and self.config.logging_enabled:
            self._logger.info(
                "event=tracing_enabled service=%s strategy=request-scope",
                self.config.service_name,
            )

    def _initialize_metrics(self) -> None:
        self._registry = CollectorRegistry()
        self._request_counter = Counter(
            "cid4_http_requests_total",
            "Total number of completed HTTP requests",
            ["service", "method", "route", "status", "status_class"],
            registry=self._registry,
        )
        self._error_counter = Counter(
            "cid4_http_request_errors_total",
            "Total number of completed HTTP requests with status >= 400",
            ["service", "method", "route", "status", "status_class"],
            registry=self._registry,
        )
        self._duration_histogram = Histogram(
            "cid4_http_request_duration_milliseconds",
            "HTTP request duration in milliseconds",
            ["service", "method", "route"],
            buckets=(1.0, 5.0, 10.0, 25.0, 50.0, 100.0, 250.0, 500.0, 1000.0, 2500.0, 5000.0),
            registry=self._registry,
        )
        self._process_up = Gauge(
            "cid4_process_up",
            "Process liveness gauge",
            ["service"],
            registry=self._registry,
        )
        self._process_up.labels(service=self.config.service_name).set(1.0)

        started = start_http_server(
            port=self.config.metrics_port,
            addr=self.config.metrics_host,
            registry=self._registry,
        )
        if isinstance(started, tuple):
            self._metrics_server, self._metrics_thread = started
        else:
            self._metrics_server = started

    def log_startup(self, host: str, port: int) -> None:
        if not self.config.logging_enabled:
            return
        self._logger.info(
            "event=server_started service=%s listen_host=%s listen_port=%s metrics_enabled=%s metrics_host=%s "
            "metrics_port=%s tracing_enabled=%s",
            self.config.service_name,
            host,
            port,
            self.config.enabled and self.config.metrics_enabled,
            self.config.metrics_host,
            self.config.metrics_port,
            self.config.enabled and self.config.tracing_enabled,
        )

    def log_startup_failure(self, message: str) -> None:
        if not self.config.logging_enabled:
            return
        self._logger.error(
            "event=server_start_failed service=%s message=%s",
            self.config.service_name,
            message,
        )

    def record_request(self, request: CompletedRequest) -> None:
        if self.config.logging_enabled:
            self._logger.info(
                "event=request_completed service=%s method=%s route=%s target=%s status=%s duration_ms=%.3f "
                "request_id=%s trace_id=%s span_id=%s",
                self.config.service_name,
                request.method,
                request.route,
                request.target,
                request.status_code,
                request.duration_ms,
                request.request_id,
                request.trace_id,
                request.span_id,
            )

        if not (self.config.enabled and self.config.metrics_enabled):
            return

        status = str(request.status_code)
        status_class = _status_class(request.status_code)
        self._request_counter.labels(
            service=self.config.service_name,
            method=request.method,
            route=request.route,
            status=status,
            status_class=status_class,
        ).inc()
        self._duration_histogram.labels(
            service=self.config.service_name,
            method=request.method,
            route=request.route,
        ).observe(request.duration_ms)
        if request.status_code >= 400:
            self._error_counter.labels(
                service=self.config.service_name,
                method=request.method,
                route=request.route,
                status=status,
                status_class=status_class,
            ).inc()

    def flush_and_shutdown(self) -> None:
        if self._shutdown:
            return
        self._shutdown = True

        if self._process_up is not None:
            self._process_up.labels(service=self.config.service_name).set(0.0)

        if self._metrics_server is not None:
            shutdown = getattr(self._metrics_server, "shutdown", None)
            if callable(shutdown):
                shutdown()
            server_close = getattr(self._metrics_server, "server_close", None)
            if callable(server_close):
                server_close()
            self._metrics_server = None

        if self._metrics_thread is not None and self._metrics_thread.is_alive():
            self._metrics_thread.join(timeout=1.0)
            self._metrics_thread = None


class RequestScope:
    def __init__(
        self,
        runtime: Runtime | None,
        method: str,
        route: str,
        target: str,
        incoming_request_id: str | None = None,
    ):
        self._runtime = runtime
        self._method = method
        self._route = route
        self._target = target
        self._request_id = incoming_request_id or _generate_hex_id(16)
        self._trace_id = _generate_hex_id(16)
        self._span_id = _generate_hex_id(8)
        self._start_time = perf_counter()
        self._finished = False

    @property
    def request_id(self) -> str:
        return self._request_id

    @property
    def trace_id(self) -> str:
        return self._trace_id

    @property
    def span_id(self) -> str:
        return self._span_id

    @property
    def response_headers(self) -> dict[str, str]:
        return {
            "X-Request-Id": self._request_id,
            "X-Trace-Id": self._trace_id,
            "X-Span-Id": self._span_id,
            "traceparent": self.traceparent(),
        }

    def traceparent(self) -> str:
        return f"00-{self._trace_id}-{self._span_id}-01"

    def finish(self, status_code: int) -> None:
        if self._finished:
            return
        self._finished = True
        duration_ms = (perf_counter() - self._start_time) * 1000.0
        if self._runtime is not None:
            self._runtime.record_request(
                CompletedRequest(
                    method=self._method,
                    route=self._route,
                    target=self._target,
                    status_code=status_code,
                    duration_ms=duration_ms,
                    request_id=self._request_id,
                    trace_id=self._trace_id,
                    span_id=self._span_id,
                )
            )


def initialize(config: ObservabilityConfig) -> Runtime:
    return Runtime(config)


def shutdown(runtime: Runtime | None) -> None:
    if runtime is not None:
        runtime.flush_and_shutdown()


def _generate_hex_id(byte_count: int) -> str:
    return secrets.token_hex(byte_count)


def _status_class(status_code: int) -> str:
    if status_code >= 500:
        return "5xx"
    if status_code >= 400:
        return "4xx"
    if status_code >= 300:
        return "3xx"
    if status_code >= 200:
        return "2xx"
    return "1xx"
