package org.example.http

import munit.FunSuite

class ObservabilitySuite extends FunSuite:
  test("observability config uses service-specific environment first") {
    val config = ObservabilitySupport.resolveObservabilityConfig(
      servicePrefix = "TOMCAT",
      defaultServiceName = "pubchem-cid4-tomcat",
      env = Map(
        "TOMCAT_OBSERVABILITY_ENABLED" -> "false",
        "OBSERVABILITY_ENABLED" -> "true",
        "TOMCAT_LOG_LEVEL" -> "debug",
        "LOG_LEVEL" -> "error"
      )
    )

    assertEquals(config.enabled, false)
    assertEquals(config.logLevel, "debug")
    assertEquals(config.serviceName, "pubchem-cid4-tomcat")
  }

  test("observability config parses metrics port and service name") {
    val config = ObservabilitySupport.resolveObservabilityConfig(
      servicePrefix = "TOMCAT",
      defaultServiceName = "pubchem-cid4-tomcat",
      env = Map(
        "OBSERVABILITY_METRICS_PORT" -> "9777",
        "OTEL_SERVICE_NAME" -> "cid4-tomcat-test",
        "OBSERVABILITY_TRACING_ENABLED" -> "false"
      )
    )

    assertEquals(config.metricsPort, 9777)
    assertEquals(config.serviceName, "cid4-tomcat-test")
    assertEquals(config.tracingEnabled, false)
  }

  test("request scope preserves incoming request id and emits trace headers") {
    val runtime = ObservabilitySupport.initialize(
      ObservabilityConfig(
        enabled = false,
        loggingEnabled = false,
        metricsEnabled = false,
        tracingEnabled = false,
        serviceName = "cid4-test"
      )
    )

    val scope = ObservabilitySupport.RequestScope(
      runtime = runtime,
      method = "GET",
      route = "/api/health",
      target = "/api/health",
      incomingRequestId = Some("request-123")
    )

    val headers = scope.responseHeaders
    assertEquals(headers("X-Request-Id"), "request-123")
    assert(headers("X-Trace-Id").nonEmpty)
    assert(headers("X-Span-Id").nonEmpty)
    assertEquals(headers("traceparent"), s"00-${scope.traceId}-${scope.spanId}-01")
    scope.finish(200)
    runtime.shutdown()
  }

  test("api routes expose normalized route labels for metrics") {
    assertEquals(ApiRoutes.normalizedRouteLabel("/health"), "/api/health")
    assertEquals(ApiRoutes.normalizedRouteLabel("/cid4/conformer/5"), "/api/cid4/conformer/{index}")
    assertEquals(ApiRoutes.normalizedRouteLabel("/api/algorithms/pathway"), "/api/algorithms/pathway")
  }
