package org.example.http

import jakarta.servlet.http.HttpServlet
import jakarta.servlet.http.HttpServletRequest
import jakarta.servlet.http.HttpServletResponse

import java.nio.charset.StandardCharsets
import java.nio.file.Files
import java.nio.file.Path

final class ApiServlet(dataDir: Path) extends HttpServlet:
  override def doOptions(request: HttpServletRequest, response: HttpServletResponse): Unit =
    applyCorsHeaders(response)
    response.setStatus(HttpServletResponse.SC_NO_CONTENT)

  override def doGet(request: HttpServletRequest, response: HttpServletResponse): Unit =
    applyCorsHeaders(response)
    val result = ApiRoutes.route(
      method = "GET",
      rawPath = Option(request.getPathInfo).getOrElse("/"),
      query = ApiRoutes.queryMap(request.getParameterMap),
      dataDir = dataDir,
      sourceLabel = "scala-tomcat"
    )
    writeRouteResult(response, result)

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

  private def applyCorsHeaders(response: HttpServletResponse): Unit =
    ApiRoutes.corsHeaders.foreach((name, value) => response.setHeader(name, value))
