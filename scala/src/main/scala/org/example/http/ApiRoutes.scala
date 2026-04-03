package org.example.http

import java.nio.file.Files
import java.nio.file.Path
import java.time.Instant
import scala.jdk.CollectionConverters.*
import scala.util.Try

object ApiRoutes:
  sealed trait RouteResult:
    def statusCode: Int

  final case class JsonResult(statusCode: Int, payload: Any) extends RouteResult
  final case class FileResult(statusCode: Int, path: Path) extends RouteResult
  final case class EmptyResult(statusCode: Int) extends RouteResult

  val corsHeaders: Map[String, String] = Map(
    "Access-Control-Allow-Origin" -> "*",
    "Access-Control-Allow-Methods" -> "GET, OPTIONS",
    "Access-Control-Allow-Headers" -> "Authorization, Content-Type"
  )

  def queryMap(parameterMap: java.util.Map[String, Array[String]]): Map[String, String] =
    parameterMap.asScala.iterator.collect {
      case (key, values) if values != null && values.nonEmpty => key -> values.head
    }.toMap

  def normalizedRouteLabel(rawPath: String): String =
    normalizedRouteLabelForPath(normalizePath(rawPath))

  def route(
      method: String,
      rawPath: String,
      query: Map[String, String],
      dataDir: Path,
      sourceLabel: String
  ): RouteResult =
    method match
      case "OPTIONS" => EmptyResult(204)
      case "GET"     => routeGet(normalizePath(rawPath), query, dataDir, sourceLabel)
      case _         => JsonResult(405, Map("message" -> s"Unsupported method $method"))

  def isPublicPath(rawPath: String): Boolean =
    normalizePath(rawPath) == "/health"

  private def routeGet(
      path: String,
      query: Map[String, String],
      dataDir: Path,
      sourceLabel: String
  ): RouteResult =
    path match
      case "/health" =>
        val timestamp = Instant.now().toString
        if query.get("mode").contains("error") then
          JsonResult(
            503,
            MockHealthResponse(
              message = s"Transport error from ${sourceLabel.replace('-', ' ')}",
              source = sourceLabel,
              timestamp = timestamp
            )
          )
        else
          JsonResult(
            200,
            MockHealthResponse(
              message = s"${sourceLabel.replace('-', ' ')} transport is healthy",
              source = sourceLabel,
              timestamp = timestamp
            )
          )
      case "/cid4/structure/2d"      => fileResult(dataDir.resolve("Structure2D_COMPOUND_CID_4.json"))
      case "/cid4/compound"          => fileResult(dataDir.resolve("COMPOUND_CID_4.json"))
      case "/algorithms/pathway"     => JsonResult(200, ApiFixtures.pathway)
      case "/algorithms/bioactivity" => JsonResult(200, ApiFixtures.bioactivity)
      case "/algorithms/taxonomy"    => JsonResult(200, ApiFixtures.taxonomy)
      case conformerPath if conformerPath.startsWith("/cid4/conformer/") =>
        handleConformer(conformerPath.stripPrefix("/cid4/conformer/"), dataDir)
      case _ => JsonResult(404, Map("message" -> s"Unknown route $path"))

  private def handleConformer(indexSegment: String, dataDir: Path): RouteResult =
    val maybeIndex = Try(indexSegment.toInt).toOption.filter(index => index >= 1 && index <= 6)
    maybeIndex match
      case Some(index) => fileResult(dataDir.resolve(s"Conformer3D_COMPOUND_CID_4($index).json"))
      case None        => JsonResult(404, Map("message" -> s"Unknown conformer $indexSegment"))

  private def fileResult(path: Path): RouteResult =
    if Files.isRegularFile(path) then FileResult(200, path)
    else JsonResult(404, Map("message" -> s"Missing JSON payload ${path.getFileName}"))

  private def normalizedRouteLabelForPath(path: String): String =
    path match
      case "/health"                                                     => "/api/health"
      case "/cid4/structure/2d"                                          => "/api/cid4/structure/2d"
      case "/cid4/compound"                                              => "/api/cid4/compound"
      case "/algorithms/pathway"                                         => "/api/algorithms/pathway"
      case "/algorithms/bioactivity"                                     => "/api/algorithms/bioactivity"
      case "/algorithms/taxonomy"                                        => "/api/algorithms/taxonomy"
      case conformerPath if conformerPath.startsWith("/cid4/conformer/") => "/api/cid4/conformer/{index}"
      case "/"                                                           => "/api/"
      case other                                                         => s"/api$other"

  private def normalizePath(rawPath: String): String =
    val withLeadingSlash =
      if rawPath == null || rawPath.isEmpty then "/"
      else if rawPath.startsWith("/") then rawPath
      else s"/$rawPath"

    if withLeadingSlash.startsWith("/api/") then withLeadingSlash.stripPrefix("/api")
    else if withLeadingSlash == "/api" then "/"
    else withLeadingSlash
