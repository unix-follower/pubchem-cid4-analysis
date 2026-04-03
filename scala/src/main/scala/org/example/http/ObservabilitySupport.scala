package org.example.http

import ch.qos.logback.classic.Level
import ch.qos.logback.classic.Logger
import com.sun.net.httpserver.HttpExchange
import com.sun.net.httpserver.HttpHandler
import com.sun.net.httpserver.HttpServer
import org.slf4j.LoggerFactory

import java.net.InetSocketAddress
import java.nio.charset.StandardCharsets
import java.util.Locale
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors
import java.util.concurrent.ThreadLocalRandom
import java.util.concurrent.atomic.DoubleAdder
import java.util.concurrent.atomic.LongAdder
import scala.jdk.CollectionConverters.*

final case class ObservabilityConfig(
    enabled: Boolean = true,
    loggingEnabled: Boolean = true,
    metricsEnabled: Boolean = true,
    tracingEnabled: Boolean = true,
    serviceName: String = "pubchem-cid4-tomcat",
    logLevel: String = "info",
    metricsHost: String = "0.0.0.0",
    metricsPort: Int = 9464
)

final case class CompletedRequest(
    method: String,
    route: String,
    target: String,
    statusCode: Int,
    durationMs: Double,
    requestId: String,
    traceId: String,
    spanId: String
)

object ObservabilitySupport:
  private val histogramBuckets = Vector(1.0, 5.0, 10.0, 25.0, 50.0, 100.0, 250.0, 500.0, 1000.0, 2500.0, 5000.0)

  def resolveObservabilityConfig(
      servicePrefix: String,
      defaultServiceName: String,
      env: Map[String, String] = sys.env
  ): ObservabilityConfig =
    val normalizedPrefix = servicePrefix.trim.toUpperCase(Locale.ROOT)

    def prefixed(name: String): String =
      if normalizedPrefix.isEmpty then name else s"${normalizedPrefix}_$name"

    def envValue(names: Seq[String]): Option[String] =
      names.iterator.flatMap(name => env.get(name).map(_.trim).filter(_.nonEmpty)).toSeq.headOption

    def parseBoolean(value: String, fallback: Boolean): Boolean =
      value.trim.toLowerCase(Locale.ROOT) match
        case "1" | "true" | "on" | "yes"  => true
        case "0" | "false" | "off" | "no" => false
        case _                            => fallback

    def parsePort(value: String): Option[Int] =
      value.toIntOption.filter(port => port > 0 && port <= 65535)

    val enabled = envValue(Seq(prefixed("OBSERVABILITY_ENABLED"), "OBSERVABILITY_ENABLED"))
      .map(parseBoolean(_, fallback = true))
      .getOrElse(true)
    val loggingEnabled = envValue(Seq(prefixed("LOGGING_ENABLED"), "OBSERVABILITY_LOGGING_ENABLED"))
      .map(parseBoolean(_, fallback = true))
      .getOrElse(true)
    val metricsEnabled = envValue(Seq(prefixed("METRICS_ENABLED"), "OBSERVABILITY_METRICS_ENABLED"))
      .map(parseBoolean(_, fallback = true))
      .getOrElse(true)
    val tracingEnabled = envValue(Seq(prefixed("TRACING_ENABLED"), "OBSERVABILITY_TRACING_ENABLED"))
      .map(parseBoolean(_, fallback = true))
      .getOrElse(true)
    val serviceName = envValue(Seq(prefixed("SERVICE_NAME"), "OTEL_SERVICE_NAME")).getOrElse(defaultServiceName)
    val logLevel = envValue(Seq(prefixed("LOG_LEVEL"), "OBSERVABILITY_LOG_LEVEL", "LOG_LEVEL"))
      .map(_.toLowerCase(Locale.ROOT))
      .getOrElse("info")
    val metricsHost = envValue(Seq(prefixed("METRICS_HOST"), "OBSERVABILITY_METRICS_HOST")).getOrElse("0.0.0.0")
    val metricsPort = envValue(Seq(prefixed("METRICS_PORT"), "OBSERVABILITY_METRICS_PORT"))
      .flatMap(parsePort)
      .getOrElse(9464)

    ObservabilityConfig(
      enabled = enabled,
      loggingEnabled = loggingEnabled,
      metricsEnabled = metricsEnabled,
      tracingEnabled = tracingEnabled,
      serviceName = serviceName,
      logLevel = logLevel,
      metricsHost = metricsHost,
      metricsPort = metricsPort
    )

  def initialize(config: ObservabilityConfig): Runtime = Runtime(config)

  final class Runtime private[http] (val config: ObservabilityConfig):
    private val logger = LoggerFactory.getLogger(config.serviceName).asInstanceOf[Logger]
    private val metrics = MetricsRegistry(config.serviceName)
    private var metricsServer: Option[HttpServer] = None
    private var metricsExecutor: Option[ExecutorService] = None
    @volatile private var stopped = false

    configureLogger()

    if config.enabled && config.metricsEnabled then
      metrics.markProcessUp()
      metricsServer = Some(startMetricsServer())

    if config.enabled && config.tracingEnabled && config.loggingEnabled then
      logger.info("event=tracing_enabled service={} strategy=request-scope", config.serviceName)

    def logStartup(host: String, port: Int): Unit =
      if config.loggingEnabled then
        logger.info(
          "event=server_started service={} listen_host={} listen_port={} metrics_enabled={} metrics_host={} metrics_port={} tracing_enabled={}",
          config.serviceName,
          host,
          Int.box(port),
          Boolean.box(config.enabled && config.metricsEnabled),
          config.metricsHost,
          Int.box(config.metricsPort),
          Boolean.box(config.enabled && config.tracingEnabled)
        )

    def logStartupFailure(message: String): Unit =
      if config.loggingEnabled then
        logger.error("event=server_start_failed service={} message={}", config.serviceName, message)

    def recordRequest(request: CompletedRequest): Unit =
      if config.loggingEnabled then
        logger.info(
          "event=request_completed service={} method={} route={} target={} status={} duration_ms={} request_id={} trace_id={} span_id={}",
          config.serviceName,
          request.method,
          request.route,
          request.target,
          Int.box(request.statusCode),
          Double.box(request.durationMs),
          request.requestId,
          request.traceId,
          request.spanId
        )

      if config.enabled && config.metricsEnabled then metrics.recordRequest(request)

    def shutdown(): Unit = synchronized {
      if !stopped then
        stopped = true
        metrics.markProcessDown()
        metricsServer.foreach(_.stop(0))
        metricsServer = None
        metricsExecutor.foreach(_.shutdownNow())
        metricsExecutor = None
    }

    private def configureLogger(): Unit =
      if config.loggingEnabled then logger.setLevel(Level.toLevel(config.logLevel.toUpperCase(Locale.ROOT), Level.INFO))

    private def startMetricsServer(): HttpServer =
      val server = HttpServer.create(InetSocketAddress(config.metricsHost, config.metricsPort), 0)
      val executor = Executors.newSingleThreadExecutor()
      server.createContext(
        "/metrics",
        new HttpHandler:
          override def handle(exchange: HttpExchange): Unit =
            val method = Option(exchange.getRequestMethod).getOrElse("GET")
            if method != "GET" then
              val payload = "Method not allowed".getBytes(StandardCharsets.UTF_8)
              exchange.getResponseHeaders.add("Allow", "GET")
              exchange.sendResponseHeaders(405, payload.length.toLong)
              val output = exchange.getResponseBody
              try output.write(payload)
              finally output.close()
            else
              val payload = metrics.renderPrometheus().getBytes(StandardCharsets.UTF_8)
              exchange.getResponseHeaders.set("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
              exchange.sendResponseHeaders(200, payload.length.toLong)
              val output = exchange.getResponseBody
              try output.write(payload)
              finally output.close()
      )
      metricsExecutor = Some(executor)
      server.setExecutor(executor)
      server.start()
      server

  object Runtime:
    def apply(config: ObservabilityConfig): Runtime = new Runtime(config)

  final class RequestScope(
      runtime: Runtime,
      val method: String,
      val route: String,
      val target: String,
      incomingRequestId: Option[String] = None
  ):
    private val startNanos = System.nanoTime()
    private val requestIdValue = incomingRequestId.getOrElse(generateHexId(16))
    private val traceIdValue = generateHexId(16)
    private val spanIdValue = generateHexId(8)
    private var finished = false

    def requestId: String = requestIdValue
    def traceId: String = traceIdValue
    def spanId: String = spanIdValue
    def traceparent: String = s"00-$traceIdValue-$spanIdValue-01"

    def responseHeaders: Map[String, String] =
      Map(
        "X-Request-Id" -> requestIdValue,
        "X-Trace-Id" -> traceIdValue,
        "X-Span-Id" -> spanIdValue,
        "traceparent" -> traceparent
      )

    def finish(statusCode: Int): Unit =
      if !finished then
        finished = true
        val durationMs = (System.nanoTime() - startNanos).toDouble / 1000000.0
        runtime.recordRequest(
          CompletedRequest(
            method = method,
            route = route,
            target = target,
            statusCode = statusCode,
            durationMs = durationMs,
            requestId = requestIdValue,
            traceId = traceIdValue,
            spanId = spanIdValue
          )
        )

  object RequestScope:
    def apply(
        runtime: Runtime,
        method: String,
        route: String,
        target: String,
        incomingRequestId: Option[String] = None
    ): RequestScope = new RequestScope(runtime, method, route, target, incomingRequestId)

  private final case class CounterKey(method: String, route: String, status: Int, statusClass: String)
  private final case class HistogramKey(method: String, route: String)

  private final class HistogramState(bucketBounds: Vector[Double]):
    val count = LongAdder()
    val sum = DoubleAdder()
    val buckets = bucketBounds.map(_ => LongAdder())
    val infBucket = LongAdder()

    def observe(valueMs: Double): Unit =
      count.increment()
      sum.add(valueMs)
      bucketBounds.zip(buckets).foreach { case (bound, bucket) =>
        if valueMs <= bound then bucket.increment()
      }
      infBucket.increment()

  private final class MetricsRegistry(serviceName: String):
    private val requestCounters = ConcurrentHashMap[CounterKey, LongAdder]()
    private val errorCounters = ConcurrentHashMap[CounterKey, LongAdder]()
    private val durationHistograms = ConcurrentHashMap[HistogramKey, HistogramState]()
    private val processUp = DoubleAdder()

    def markProcessUp(): Unit =
      resetProcessGauge(1.0)

    def markProcessDown(): Unit =
      resetProcessGauge(0.0)

    def recordRequest(request: CompletedRequest): Unit =
      val key = CounterKey(request.method, request.route, request.statusCode, statusClass(request.statusCode))
      requestCounters.computeIfAbsent(key, _ => LongAdder()).increment()

      val histogramKey = HistogramKey(request.method, request.route)
      durationHistograms.computeIfAbsent(
        histogramKey,
        _ => HistogramState(histogramBuckets)
      ).observe(request.durationMs)

      if request.statusCode >= 400 then
        errorCounters.computeIfAbsent(key, _ => LongAdder()).increment()

    def renderPrometheus(): String =
      val builder = new StringBuilder
      builder.append("# HELP cid4_http_requests_total Total number of completed HTTP requests\n")
      builder.append("# TYPE cid4_http_requests_total counter\n")
      requestCounters.asScala.toSeq.sortBy(entry => (entry._1.route, entry._1.method, entry._1.status)).foreach {
        case (key, counter) =>
          builder.append(metricLine(
            "cid4_http_requests_total",
            Map(
              "service" -> serviceName,
              "method" -> key.method,
              "route" -> key.route,
              "status" -> key.status.toString,
              "status_class" -> key.statusClass
            ),
            counter.sum().toDouble
          ))
      }

      builder.append(
        "# HELP cid4_http_request_errors_total Total number of completed HTTP requests with status >= 400\n"
      )
      builder.append("# TYPE cid4_http_request_errors_total counter\n")
      errorCounters.asScala.toSeq.sortBy(entry => (entry._1.route, entry._1.method, entry._1.status)).foreach {
        case (key, counter) =>
          builder.append(metricLine(
            "cid4_http_request_errors_total",
            Map(
              "service" -> serviceName,
              "method" -> key.method,
              "route" -> key.route,
              "status" -> key.status.toString,
              "status_class" -> key.statusClass
            ),
            counter.sum().toDouble
          ))
      }

      builder.append("# HELP cid4_http_request_duration_milliseconds HTTP request duration in milliseconds\n")
      builder.append("# TYPE cid4_http_request_duration_milliseconds histogram\n")
      durationHistograms.asScala.toSeq.sortBy(entry => (entry._1.route, entry._1.method)).foreach {
        case (key, histogram) =>
          val commonLabels = Map("service" -> serviceName, "method" -> key.method, "route" -> key.route)
          var cumulative = 0L
          histogramBuckets.zip(histogram.buckets).foreach { case (bound, bucket) =>
            cumulative = bucket.sum()
            builder.append(metricLine(
              "cid4_http_request_duration_milliseconds_bucket",
              commonLabels + ("le" -> formatDouble(bound)),
              cumulative.toDouble
            ))
          }
          builder.append(metricLine(
            "cid4_http_request_duration_milliseconds_bucket",
            commonLabels + ("le" -> "+Inf"),
            histogram.infBucket.sum().toDouble
          ))
          builder.append(metricLine("cid4_http_request_duration_milliseconds_sum", commonLabels, histogram.sum.sum()))
          builder.append(metricLine(
            "cid4_http_request_duration_milliseconds_count",
            commonLabels,
            histogram.count.sum().toDouble
          ))
      }

      builder.append("# HELP cid4_process_up Process liveness gauge\n")
      builder.append("# TYPE cid4_process_up gauge\n")
      builder.append(metricLine("cid4_process_up", Map("service" -> serviceName), processUp.sum()))
      builder.toString

    private def resetProcessGauge(value: Double): Unit =
      processUp.reset()
      processUp.add(value)

  private def statusClass(statusCode: Int): String =
    if statusCode >= 500 then "5xx"
    else if statusCode >= 400 then "4xx"
    else if statusCode >= 300 then "3xx"
    else if statusCode >= 200 then "2xx"
    else "1xx"

  private def generateHexId(byteCount: Int): String =
    val random = ThreadLocalRandom.current()
    val builder = new StringBuilder(byteCount * 2)
    (0 until byteCount).foreach { _ =>
      val value = random.nextInt(256)
      builder.append(Character.forDigit((value >>> 4) & 0x0f, 16))
      builder.append(Character.forDigit(value & 0x0f, 16))
    }
    builder.toString

  private def escapeLabelValue(value: String): String =
    value
      .replace("\\", "\\\\")
      .replace("\n", "\\n")
      .replace("\"", "\\\"")

  private def metricLine(name: String, labels: Map[String, String], value: Double): String =
    val encodedLabels = labels.toSeq.sortBy(_._1).map { case (key, labelValue) =>
      s"$key=\"${escapeLabelValue(labelValue)}\""
    }.mkString(",")
    s"$name{$encodedLabels} ${formatDouble(value)}\n"

  private def formatDouble(value: Double): String =
    if value.isWhole then value.toLong.toString else f"$value%.6f"
