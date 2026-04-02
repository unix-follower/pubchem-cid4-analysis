package org.example.http

import com.sun.net.httpserver.Headers
import com.sun.net.httpserver.HttpExchange
import com.sun.net.httpserver.HttpHandler
import com.sun.net.httpserver.HttpsConfigurator
import com.sun.net.httpserver.HttpsParameters
import com.sun.net.httpserver.HttpsServer
import org.slf4j.LoggerFactory

import java.io.IOException
import java.net.InetSocketAddress
import java.net.URI
import java.net.URLDecoder
import java.nio.ByteBuffer
import java.nio.channels.AsynchronousFileChannel
import java.nio.channels.CompletionHandler
import java.nio.charset.StandardCharsets
import java.nio.file.Files
import java.nio.file.NoSuchFileException
import java.nio.file.Path
import java.nio.file.StandardOpenOption
import java.util.concurrent.CompletableFuture
import java.util.concurrent.CountDownLatch
import java.util.concurrent.Executors
import javax.net.ssl.SSLContext

object JdkConcurrentServer:
  private val logger = LoggerFactory.getLogger(this.getClass)
  private val HybridAsyncThresholdBytes = 64 * 1024L

  enum IoMode:
    case Blocking
    case NonBlocking
    case Hybrid

  def startAndAwait(): Unit =
    val dataDir = ApiConfig.resolveDataDir()
    val tlsConfig = ApiConfig.loadTlsConfig(
      dataDir,
      hostEnvNames = Seq("JDK_HOST", "VTHREAD_HOST", "SERVER_HOST"),
      portEnvNames = Seq("JDK_PORT", "VTHREAD_PORT", "SERVER_PORT", "PORT")
    )
    val ioMode = resolveIoMode()
    val sslContext = buildSslContext(tlsConfig)
    val executor = Executors.newVirtualThreadPerTaskExecutor()
    val server = HttpsServer.create(InetSocketAddress(tlsConfig.host, tlsConfig.port), 0)
    val shutdownLatch = CountDownLatch(1)

    server.setHttpsConfigurator(new Configurator(sslContext))
    server.createContext("/api", new ApiHandler(dataDir, ioMode))
    server.setExecutor(executor)

    Runtime.getRuntime.addShutdownHook(Thread.ofPlatform().unstarted { () =>
      logger.info("Stopping CID4 JDK HTTPS API")
      server.stop(0)
      executor.shutdown()
      shutdownLatch.countDown()
    })

    logger.info(
      s"Starting CID4 JDK HTTPS API on https://${tlsConfig.host}:${tlsConfig.port} using ${tlsConfig.keystoreType} keystore ${tlsConfig.keystorePath} with ${ioMode.toString.toLowerCase} I/O"
    )
    server.start()
    logger.info("CID4 JDK HTTPS API is ready")
    shutdownLatch.await()

  private final case class ResponsePayload(statusCode: Int, body: Array[Byte], contentType: String)

  private final class Configurator(sslContext: SSLContext) extends HttpsConfigurator(sslContext):
    override def configure(parameters: HttpsParameters): Unit =
      val engine = getSSLContext.createSSLEngine()
      parameters.setNeedClientAuth(false)
      parameters.setProtocols(Array("TLSv1.2", "TLSv1.3"))
      parameters.setCipherSuites(engine.getEnabledCipherSuites)
      parameters.setSSLParameters(getSSLContext.getDefaultSSLParameters)

  private final class ApiHandler(dataDir: Path, ioMode: IoMode) extends HttpHandler:
    override def handle(exchange: HttpExchange): Unit =
      try
        val result = ApiRoutes.route(
          method = exchange.getRequestMethod,
          rawPath = exchange.getRequestURI.getPath,
          query = decodeQuery(exchange.getRequestURI),
          dataDir = dataDir,
          sourceLabel = "scala-jdk"
        )

        resolveResponse(result, ioMode).whenComplete((payload, error) =>
          if error != null then
            logger.error("JDK API request failed", error)
            writeResponse(
              exchange,
              ResponsePayload(
                500,
                JsonSupport.toJsonBytes(Map("message" -> Option(error.getMessage).getOrElse("Internal server error"))),
                "application/json"
              )
            )
          else writeResponse(exchange, payload)
        )
      catch
        case error: Throwable =>
          logger.error("JDK API request failed before dispatch", error)
          writeResponse(
            exchange,
            ResponsePayload(
              500,
              JsonSupport.toJsonBytes(Map("message" -> Option(error.getMessage).getOrElse("Internal server error"))),
              "application/json"
            )
          )

  private def resolveResponse(result: ApiRoutes.RouteResult, ioMode: IoMode): CompletableFuture[ResponsePayload] =
    result match
      case ApiRoutes.JsonResult(statusCode, payload) =>
        CompletableFuture.completedFuture(
          ResponsePayload(statusCode, JsonSupport.toJsonBytes(payload), "application/json")
        )
      case ApiRoutes.EmptyResult(statusCode) =>
        CompletableFuture.completedFuture(ResponsePayload(statusCode, Array.emptyByteArray, "text/plain"))
      case ApiRoutes.FileResult(statusCode, path) =>
        resolveFileResponse(statusCode, path, ioMode)

  private def resolveFileResponse(
      statusCode: Int,
      path: Path,
      ioMode: IoMode
  ): CompletableFuture[ResponsePayload] =
    ioMode match
      case IoMode.Blocking =>
        CompletableFuture.completedFuture(readFileBlocking(statusCode, path))
      case IoMode.NonBlocking =>
        readFileNonBlocking(statusCode, path)
      case IoMode.Hybrid =>
        if Files.size(path) >= HybridAsyncThresholdBytes then readFileNonBlocking(statusCode, path)
        else CompletableFuture.completedFuture(readFileBlocking(statusCode, path))

  private def readFileBlocking(statusCode: Int, path: Path): ResponsePayload =
    try ResponsePayload(statusCode, Files.readAllBytes(path), "application/json")
    catch
      case _: NoSuchFileException => missingFilePayload(path)
      case error: Throwable       => failurePayload(error)

  private def readFileNonBlocking(statusCode: Int, path: Path): CompletableFuture[ResponsePayload] =
    readAllBytesAsync(path).handle((body, error) =>
      if error == null then ResponsePayload(statusCode, body, "application/json")
      else
        unwrap(error) match
          case _: NoSuchFileException => missingFilePayload(path)
          case other                  => failurePayload(other)
    )

  private def readAllBytesAsync(path: Path): CompletableFuture[Array[Byte]] =
    val future = CompletableFuture[Array[Byte]]()

    try
      val channel = AsynchronousFileChannel.open(path, StandardOpenOption.READ)
      val fileSize = channel.size()
      if fileSize > Int.MaxValue then
        channel.close()
        future.completeExceptionally(
          IllegalStateException(s"JSON payload too large to buffer in memory: ${path.getFileName}")
        )
      else
        val buffer = ByteBuffer.allocate(fileSize.toInt)
        readChunk(channel, buffer, 0L, future)
    catch
      case error: Throwable => future.completeExceptionally(error)

    future

  private def readChunk(
      channel: AsynchronousFileChannel,
      buffer: ByteBuffer,
      position: Long,
      future: CompletableFuture[Array[Byte]]
  ): Unit =
    channel.read(
      buffer,
      position,
      (),
      new CompletionHandler[Integer, Unit]:
        override def completed(bytesRead: Integer, attachment: Unit): Unit =
          if bytesRead == -1 || !buffer.hasRemaining then
            buffer.flip()
            val bytes = Array.ofDim[Byte](buffer.remaining())
            buffer.get(bytes)
            channel.close()
            future.complete(bytes)
          else readChunk(channel, buffer, position + bytesRead.longValue(), future)

        override def failed(error: Throwable, attachment: Unit): Unit =
          channel.close()
          future.completeExceptionally(error)
    )

  private def writeResponse(exchange: HttpExchange, payload: ResponsePayload): Unit =
    try
      val headers = exchange.getResponseHeaders
      applyCorsHeaders(headers)
      headers.set("Content-Type", payload.contentType)

      val contentLength = if payload.statusCode == 204 then -1L else payload.body.length.toLong
      exchange.sendResponseHeaders(payload.statusCode, contentLength)

      if payload.statusCode != 204 && payload.body.nonEmpty then
        val output = exchange.getResponseBody
        try output.write(payload.body)
        finally output.close()
      else exchange.close()
    catch
      case error: IOException if isClientDisconnect(error) =>
        logger.info(s"Client disconnected before response completed: ${error.getMessage}")
        exchange.close()
      case error: Throwable =>
        logger.error("Failed to write JDK API response", error)
        exchange.close()

  private def applyCorsHeaders(headers: Headers): Unit =
    ApiRoutes.corsHeaders.foreach((name, value) => headers.set(name, value))

  private def decodeQuery(uri: URI): Map[String, String] =
    Option(uri.getRawQuery).toSeq
      .flatMap(_.split("&").toSeq)
      .filter(_.nonEmpty)
      .map { pair =>
        val parts = pair.split("=", 2)
        val key = URLDecoder.decode(parts(0), StandardCharsets.UTF_8)
        val value =
          if parts.length > 1 then URLDecoder.decode(parts(1), StandardCharsets.UTF_8)
          else ""
        key -> value
      }
      .toMap

  private def buildSslContext(tlsConfig: TlsConfig): SSLContext =
    val sslContext = SSLContext.getInstance("TLS")
    sslContext.init(ApiConfig.buildKeyManagerFactory(tlsConfig).getKeyManagers, null, null)
    sslContext

  private def missingFilePayload(path: Path): ResponsePayload =
    ResponsePayload(
      404,
      JsonSupport.toJsonBytes(Map("message" -> s"Missing JSON payload ${path.getFileName}")),
      "application/json"
    )

  private def failurePayload(error: Throwable): ResponsePayload =
    ResponsePayload(
      500,
      JsonSupport.toJsonBytes(Map("message" -> Option(error.getMessage).getOrElse("Internal server error"))),
      "application/json"
    )

  private def unwrap(error: Throwable): Throwable =
    Option(error.getCause).getOrElse(error)

  private def isClientDisconnect(error: Throwable): Boolean =
    Iterator.iterate(Option(error))(_.flatMap(next => Option(next.getCause)))
      .takeWhile(_.isDefined)
      .flatten
      .exists { current =>
        val message = Option(current.getMessage).map(_.toLowerCase).getOrElse("")
        message.contains("broken pipe") ||
        message.contains("connection reset") ||
        message.contains("insufficient bytes written")
      }

  private def resolveIoMode(): IoMode =
    val rawValue = Seq("JDK_IO_MODE", "VTHREAD_IO_MODE", "IO_MODE")
      .iterator
      .flatMap(name => Option(System.getenv(name)).filter(_.nonEmpty))
      .toSeq
      .headOption
      .map(_.trim.toLowerCase)

    rawValue match
      case Some("blocking")     => IoMode.Blocking
      case Some("nonblocking")  => IoMode.NonBlocking
      case Some("non-blocking") => IoMode.NonBlocking
      case _                    => IoMode.Hybrid
