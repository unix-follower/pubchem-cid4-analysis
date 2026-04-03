package org.example.http

import jakarta.servlet.http.HttpServlet
import jakarta.servlet.http.HttpServletRequest
import jakarta.servlet.http.HttpServletResponse

import java.nio.charset.StandardCharsets
import java.nio.file.Files
import java.nio.file.Path

final class ApiServlet(
    dataDir: Path,
    security: HttpSecurity,
    observability: ObservabilitySupport.Runtime
) extends HttpServlet:
  override def doOptions(request: HttpServletRequest, response: HttpServletResponse): Unit =
    security.applyResponseHeaders(request, response)
    val scope = new ObservabilitySupport.RequestScope(
      runtime = observability,
      method = "OPTIONS",
      route = ApiRoutes.normalizedRouteLabel(Option(request.getPathInfo).getOrElse("/")),
      target = requestTarget(request),
      incomingRequestId = requestIdHeader(request)
    )
    applyObservabilityHeaders(response, scope)
    var statusCode = HttpServletResponse.SC_NO_CONTENT
    try response.setStatus(statusCode)
    finally scope.finish(statusCode)

  override def doGet(request: HttpServletRequest, response: HttpServletResponse): Unit =
    security.applyResponseHeaders(request, response)
    val scope = new ObservabilitySupport.RequestScope(
      runtime = observability,
      method = "GET",
      route = ApiRoutes.normalizedRouteLabel(Option(request.getPathInfo).getOrElse("/")),
      target = requestTarget(request),
      incomingRequestId = requestIdHeader(request)
    )
    applyObservabilityHeaders(response, scope)

    var statusCode = HttpServletResponse.SC_INTERNAL_SERVER_ERROR
    try
      security.authorize(request) match
        case Left(failure) =>
          security.challenge(response, failure)
          statusCode = failure.statusCode
          writeJson(response, failure.statusCode, failure.payload)
        case Right(_) =>
          val result = ApiRoutes.route(
            method = "GET",
            rawPath = Option(request.getPathInfo).getOrElse("/"),
            query = ApiRoutes.queryMap(request.getParameterMap),
            dataDir = dataDir,
            sourceLabel = "scala-tomcat"
          )
          statusCode = result.statusCode
          writeRouteResult(response, result)
    finally scope.finish(statusCode)

  private def writeJsonFile(response: HttpServletResponse, path: Path): Unit =
    if !Files.isRegularFile(path) then
      writeJson(
        response,
        HttpServletResponse.SC_NOT_FOUND,
        Map("message" -> s"Missing JSON payload ${path.getFileName}")
      )
    else
      response.setStatus(HttpServletResponse.SC_OK)
      response.setCharacterEncoding(StandardCharsets.UTF_8.name())
      response.setContentType("application/json")
      response.getOutputStream.write(Files.readAllBytes(path))

  private def writeJson(response: HttpServletResponse, status: Int, payload: Any): Unit =
    response.setStatus(status)
    response.setCharacterEncoding(StandardCharsets.UTF_8.name())
    response.setContentType("application/json")
    JsonSupport.mapper.writeValue(response.getOutputStream, payload)

  private def writeRouteResult(response: HttpServletResponse, result: ApiRoutes.RouteResult): Unit =
    result match
      case ApiRoutes.JsonResult(statusCode, payload) =>
        writeJson(response, statusCode, payload)
      case ApiRoutes.FileResult(statusCode, path) =>
        response.setStatus(statusCode)
        response.setCharacterEncoding(StandardCharsets.UTF_8.name())
        response.setContentType("application/json")
        response.getOutputStream.write(Files.readAllBytes(path))
      case ApiRoutes.EmptyResult(statusCode) =>
        response.setStatus(statusCode)

  private def applyObservabilityHeaders(
      response: HttpServletResponse,
      scope: ObservabilitySupport.RequestScope
  ): Unit =
    scope.responseHeaders.foreach((name, value) => response.setHeader(name, value))

  private def requestIdHeader(request: HttpServletRequest): Option[String] =
    Option(request.getHeader("X-Request-Id")).map(_.trim).filter(_.nonEmpty)

  private def requestTarget(request: HttpServletRequest): String =
    val path = Option(request.getRequestURI).filter(_.nonEmpty).getOrElse("/api")
    Option(request.getQueryString).filter(_.nonEmpty).map(query => s"$path?$query").getOrElse(path)
