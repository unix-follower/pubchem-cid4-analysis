package org.example.search.elasticsearch

import org.example.http.ApiConfig
import org.example.http.OutboundUrlValidator
import org.example.search.lucene.LuceneDocumentBatch
import org.example.search.lucene.LuceneSourceDocument
import org.slf4j.LoggerFactory
import tools.jackson.databind.JsonNode
import tools.jackson.databind.ObjectMapper
import tools.jackson.databind.json.JsonMapper
import tools.jackson.databind.node.ObjectNode
import tools.jackson.module.scala.DefaultScalaModule

import java.io.IOException
import java.net.URI
import java.net.http.HttpClient
import java.net.http.HttpRequest
import java.net.http.HttpResponse
import java.nio.charset.StandardCharsets
import java.nio.file.Files
import java.nio.file.Path
import java.time.Duration
import scala.jdk.CollectionConverters.*
import scala.util.Using

object ElasticsearchExportService:
  private val logger = LoggerFactory.getLogger(getClass)
  private val jsonMapper = JsonMapper.builder().addModule(DefaultScalaModule()).build()
  private val resourceFiles = Seq(
    "/elasticsearch/cid4/index-template.json",
    "/elasticsearch/cid4/settings.json",
    "/elasticsearch/cid4/synonyms.txt"
  )

  def exportDocuments(
      indexName: String,
      bulkPath: Path,
      configDirectory: Path,
      batches: Seq[LuceneDocumentBatch]
  ): ElasticsearchExportSummary =
    Files.createDirectories(bulkPath.getParent)
    writeBundledConfig(configDirectory)

    val countsByDocType = scala.collection.mutable.Map.empty[String, Int].withDefaultValue(0)
    val sourceFiles = scala.collection.mutable.LinkedHashSet.empty[String]
    var totalDocuments = 0

    Using.resource(Files.newBufferedWriter(bulkPath, StandardCharsets.UTF_8)) { writer =>
      batches.foreach { batch =>
        sourceFiles += batch.sourceFile
        batch.loader().foreach { sourceDocument =>
          val action = Map("index" -> Map("_index" -> indexName, "_id" -> sourceDocument.docId))
          writer.write(jsonMapper.writeValueAsString(action))
          writer.newLine()
          writer.write(jsonMapper.writeValueAsString(toElasticsearchDocument(sourceDocument)))
          writer.newLine()
          totalDocuments += 1
          countsByDocType.update(sourceDocument.docType, countsByDocType(sourceDocument.docType) + 1)
        }
        logger.info(s"Finished Elasticsearch export for ${batch.sourceFile}")
      }
    }

    ElasticsearchExportSummary(
      indexName = indexName,
      bulkPath = bulkPath.toAbsolutePath.toString,
      configDirectory = configDirectory.toAbsolutePath.toString,
      documentCount = totalDocuments,
      countsByDocType = countsByDocType.toSeq.sortBy(_._1).toMap,
      sourceFiles = sourceFiles.toSeq
    )

  def toElasticsearchDocument(sourceDocument: LuceneSourceDocument): Map[String, Any] =
    val fields = scala.collection.mutable.LinkedHashMap[String, Any](
      "id" -> sourceDocument.docId,
      "doc_type" -> sourceDocument.docType,
      "source_file" -> sourceDocument.sourceFile,
      "row_id" -> sourceDocument.sourceRowId,
      "raw_payload" -> sourceDocument.rawPayload
    )

    if sourceDocument.title.nonEmpty then
      fields.update("title", sourceDocument.title)

    val aggregateText =
      (Seq(sourceDocument.title) ++ sourceDocument.textFields.values.toSeq)
        .map(_.trim)
        .filter(_.nonEmpty)
        .distinct
        .mkString("\n\n")
    if aggregateText.nonEmpty then
      fields.update("text", aggregateText)

    sourceDocument.textFields.foreach { case (fieldName, value) =>
      val normalized = value.trim
      if normalized.nonEmpty then
        fields.update(fieldName, normalized)
    }

    sourceDocument.exactFields.foreach { case (fieldName, values) =>
      val normalizedValues = values.map(_.trim).filter(_.nonEmpty).distinct
      if normalizedValues.nonEmpty then
        if normalizedValues.size == 1 then fields.update(fieldName, normalizedValues.head)
        else fields.update(fieldName, normalizedValues)
    }

    sourceDocument.intFields.foreach { case (fieldName, value) =>
      fields.update(fieldName, value)
    }

    sourceDocument.floatFields.foreach { case (fieldName, value) =>
      fields.update(fieldName, value)
    }

    fields.toMap

  private def writeBundledConfig(configDirectory: Path): Unit =
    resourceFiles.foreach { resourcePath =>
      val fileName = resourcePath.split('/').last
      val targetPath = configDirectory.resolve(fileName)
      Files.createDirectories(targetPath.getParent)
      Using.resource(Option(getClass.getResourceAsStream(resourcePath)).getOrElse {
        throw new IOException(s"Missing bundled Elasticsearch resource: $resourcePath")
      }) { inputStream =>
        Files.copy(inputStream, targetPath, java.nio.file.StandardCopyOption.REPLACE_EXISTING)
      }
    }

object ElasticsearchRuntimeService:
  private val logger = LoggerFactory.getLogger(getClass)
  private val jsonMapper: ObjectMapper = JsonMapper.builder().addModule(DefaultScalaModule()).build()
  private val httpClient = HttpClient.newBuilder()
    .followRedirects(HttpClient.Redirect.NEVER)
    .connectTimeout(Duration.ofSeconds(10))
    .build()
  private val exactFieldNames = Seq(
    "pmid",
    "doi",
    "publicationnumber",
    "aid_type",
    "bioassay_aid",
    "taxonomy_id",
    "pathway_accession"
  )

  def postDocuments(
      elasticsearchUrl: String,
      indexName: String,
      configDirectory: Path,
      batches: Seq[LuceneDocumentBatch],
      batchSize: Int = 500
  ): ElasticsearchIngestSummary =
    val baseUrl = validatedBaseUrl(elasticsearchUrl)
    ensureIndexTemplate(baseUrl, indexName, configDirectory)
    val payloadBuilder = new StringBuilder()
    var bufferedCount = 0
    var postedDocuments = 0

    batches.foreach { batch =>
      batch.loader().foreach { sourceDocument =>
        appendBulkRecord(payloadBuilder, indexName, sourceDocument)
        bufferedCount += 1
        if bufferedCount >= batchSize then
          postBulkPayload(baseUrl, payloadBuilder.result())
          postedDocuments += bufferedCount
          payloadBuilder.clear()
          bufferedCount = 0
      }
    }

    if bufferedCount > 0 then
      postBulkPayload(baseUrl, payloadBuilder.result())
      postedDocuments += bufferedCount

    logger.info(s"Posted $postedDocuments document(s) to Elasticsearch index '$indexName'")
    ElasticsearchIngestSummary("posted", indexName, postedDocuments, batchSize)

  def runExampleQueries(elasticsearchUrl: String, indexName: String): Seq[ElasticsearchQueryExampleResult] =
    val baseUrl = validatedBaseUrl(elasticsearchUrl)
    queryExamples.map(example => executeExample(baseUrl, indexName, example))

  private def ensureIndexTemplate(elasticsearchUrl: String, indexName: String, configDirectory: Path): Unit =
    val templatePath = configDirectory.resolve("index-template.json")
    val templateNode = jsonMapper.readTree(Files.readString(templatePath))
    val templateName = s"${indexName}_template"
    val templateRequest = authorizedJsonRequest(
      URI.create(s"${stripTrailingSlash(elasticsearchUrl)}/_index_template/$templateName"),
      jsonMapper.writeValueAsString(templateNode),
      "PUT"
    )
    val templateResponse = httpClient.send(templateRequest, HttpResponse.BodyHandlers.ofString())
    require2xx(templateResponse, s"create Elasticsearch index template '$templateName'")

  private def executeExample(
      elasticsearchUrl: String,
      indexName: String,
      example: ElasticsearchQueryDefinition
  ): ElasticsearchQueryExampleResult =
    val requestBody = buildSearchRequest(example)
    val request = authorizedJsonRequest(
      URI.create(s"${stripTrailingSlash(elasticsearchUrl)}/$indexName/_search"),
      jsonMapper.writeValueAsString(requestBody),
      "POST"
    )
    val response = httpClient.send(request, HttpResponse.BodyHandlers.ofString())
    require2xx(response, s"run Elasticsearch example query '${example.name}'")

    val root = jsonMapper.readTree(response.body())
    val hitNodes = root.path("hits").path("hits")
    val hits =
      if hitNodes.isArray then hitNodes.iterator().asScala.toSeq.map(hitNode => toQueryHit(hitNode)) else Seq.empty

    val aggregations = example.aggregationFields.flatMap { fieldName =>
      val bucketsNode = root.path("aggregations").path(fieldName).path("buckets")
      val buckets =
        if bucketsNode.isArray then
          bucketsNode.iterator().asScala.toSeq.map { bucketNode =>
            ElasticsearchAggregationBucket(
              value = bucketNode.path("key_as_string").asText(bucketNode.path("key").asText("")),
              count = bucketNode.path("doc_count").asLong(0L)
            )
          }
        else Seq.empty
      if buckets.nonEmpty then Some(fieldName -> buckets) else None
    }.toMap

    ElasticsearchQueryExampleResult(
      name = example.name,
      description = example.description,
      status = "ok",
      query = example.query,
      filters = example.filters.view.mapValues(_.toSeq).toMap,
      totalHits = totalHits(root.path("hits").path("total")),
      aggregations = aggregations,
      hits = hits
    )

  private def buildSearchRequest(example: ElasticsearchQueryDefinition): ObjectNode =
    val root = jsonMapper.createObjectNode()
    root.put("size", example.rows)
    root.set("query", buildBoolQuery(example))
    val highlightFields = jsonMapper.createObjectNode()
    example.highlightFields.foreach(fieldName => highlightFields.set(fieldName, jsonMapper.createObjectNode()))
    if example.highlightFields.nonEmpty then
      val highlight = jsonMapper.createObjectNode()
      highlight.put("fragment_size", 180)
      highlight.put("number_of_fragments", 1)
      highlight.set("fields", highlightFields)
      root.set("highlight", highlight)

    if example.aggregationFields.nonEmpty then
      val aggsNode = jsonMapper.createObjectNode()
      example.aggregationFields.foreach { fieldName =>
        val termsNode = jsonMapper.createObjectNode()
        termsNode.put("field", fieldName)
        termsNode.put("size", 10)
        val aggNode = jsonMapper.createObjectNode()
        aggNode.set("terms", termsNode)
        aggsNode.set(fieldName, aggNode)
      }
      root.set("aggs", aggsNode)
    root

  private def buildBoolQuery(example: ElasticsearchQueryDefinition): ObjectNode =
    val boolNode = jsonMapper.createObjectNode()
    val mustNode = jsonMapper.createArrayNode()
    val multiMatch = jsonMapper.createObjectNode()
    multiMatch.put("query", example.query)
    val fields = jsonMapper.createArrayNode()
    example.searchFields.foreach(fields.add)
    multiMatch.set("fields", fields)
    val multiMatchWrapper = jsonMapper.createObjectNode()
    multiMatchWrapper.set("multi_match", multiMatch)
    mustNode.add(multiMatchWrapper)
    boolNode.set("must", mustNode)

    if example.filters.nonEmpty then
      val filterNode = jsonMapper.createArrayNode()
      example.filters.foreach { case (fieldName, values) =>
        if values.size == 1 then
          filterNode.add(termNode(fieldName, values.head))
        else filterNode.add(termsNode(fieldName, values))
      }
      boolNode.set("filter", filterNode)

    val wrapper = jsonMapper.createObjectNode()
    wrapper.set("bool", boolNode)
    wrapper

  private def termNode(fieldName: String, value: String): ObjectNode =
    val termValue = jsonMapper.createObjectNode()
    termValue.put(fieldName, value)
    val wrapper = jsonMapper.createObjectNode()
    wrapper.set("term", termValue)
    wrapper

  private def termsNode(fieldName: String, values: Seq[String]): ObjectNode =
    val termsValue = jsonMapper.createObjectNode()
    val array = jsonMapper.createArrayNode()
    values.foreach(array.add)
    termsValue.set(fieldName, array)
    val wrapper = jsonMapper.createObjectNode()
    wrapper.set("terms", termsValue)
    wrapper

  private def toQueryHit(hitNode: JsonNode): ElasticsearchQueryHit =
    val source = hitNode.path("_source")
    val highlightFields =
      if hitNode.path("highlight").isObject then
        hitNode.path("highlight").iterator().asScala.toSeq.flatMap { valueNode =>
          val values = valueNode.iterator().asScala.map(_.asText("").trim).filter(_.nonEmpty).toSeq
          values.headOption
        }
      else Seq.empty
    val snippet = highlightFields.headOption.getOrElse(source.path("text").asText("").take(180))
    val exactFields = exactFieldNames.flatMap { fieldName =>
      val values = sourceFieldValues(source, fieldName)
      if values.nonEmpty then Some(fieldName -> values) else None
    }.toMap
    ElasticsearchQueryHit(
      id = hitNode.path("_id").asText(""),
      docType = source.path("doc_type").asText(""),
      title = source.path("title").asText(""),
      sourceFile = source.path("source_file").asText(""),
      rowId = source.path("row_id").asText(""),
      score = hitNode.path("_score").floatValue(),
      snippet = snippet,
      exactFields = exactFields
    )

  private def totalHits(totalNode: JsonNode): Long =
    if totalNode.isIntegralNumber then totalNode.asLong()
    else totalNode.path("value").asLong(0L)

  private def sourceFieldValues(source: JsonNode, fieldName: String): Seq[String] =
    val node = source.path(fieldName)
    if node.isMissingNode || node.isNull then Seq.empty
    else if node.isArray then node.iterator().asScala.map(_.asText("").trim).filter(_.nonEmpty).toSeq
    else Seq(node.asText("").trim).filter(_.nonEmpty)

  private def appendBulkRecord(builder: StringBuilder, indexName: String, sourceDocument: LuceneSourceDocument): Unit =
    builder.append(jsonMapper.writeValueAsString(Map("index" -> Map(
      "_index" -> indexName,
      "_id" -> sourceDocument.docId
    ))))
    builder.append('\n')
    builder.append(jsonMapper.writeValueAsString(ElasticsearchExportService.toElasticsearchDocument(sourceDocument)))
    builder.append('\n')

  private def postBulkPayload(elasticsearchUrl: String, payload: String): Unit =
    val request = authorizedJsonRequest(
      URI.create(s"${stripTrailingSlash(elasticsearchUrl)}/_bulk"),
      payload,
      "POST",
      "application/x-ndjson"
    )
    val response = httpClient.send(request, HttpResponse.BodyHandlers.ofString())
    require2xx(response, "post Elasticsearch bulk payload")
    val responseNode = jsonMapper.readTree(response.body())
    if responseNode.path("errors").asBoolean(false) then
      throw new IllegalStateException(s"Elasticsearch bulk request returned item errors: ${response.body()}")

  private def authorizedJsonRequest(
      uri: URI,
      body: String,
      method: String,
      contentType: String = "application/json"
  ): HttpRequest =
    val builder = HttpRequest
      .newBuilder(uri)
      .header("Content-Type", contentType)
      .header("Accept", "application/json")
    Option(System.getenv("ELASTICSEARCH_API_KEY")).filter(_.trim.nonEmpty).foreach { value =>
      builder.header("Authorization", s"ApiKey ${value.trim}")
    }
    method match
      case "PUT"  => builder.PUT(HttpRequest.BodyPublishers.ofString(body)).build()
      case "POST" => builder.POST(HttpRequest.BodyPublishers.ofString(body)).build()
      case other  => throw new IllegalArgumentException(s"Unsupported HTTP method: $other")

  private def require2xx(response: HttpResponse[String], action: String): Unit =
    val statusCode = response.statusCode()
    if statusCode < 200 || statusCode >= 300 then
      throw new IllegalStateException(s"Failed to $action. HTTP $statusCode: ${response.body()}")

  private def stripTrailingSlash(value: String): String = value.stripSuffix("/")

  private def validatedBaseUrl(rawUrl: String): String =
    OutboundUrlValidator.validate("Elasticsearch", rawUrl, ApiConfig.loadSecurityConfig()).toString.stripSuffix("/")

  private final case class ElasticsearchQueryDefinition(
      name: String,
      description: String,
      query: String,
      filters: Map[String, Seq[String]],
      searchFields: Seq[String],
      highlightFields: Seq[String],
      aggregationFields: Seq[String],
      rows: Int = 5
  )

  private val queryExamples = Seq(
    ElasticsearchQueryDefinition(
      name = "literature_isopropanolamine_fungicide",
      description = "Find literature about isopropanolamine and fungicide",
      query = "isopropanolamine fungicide",
      filters = Map("doc_type" -> Seq("literature")),
      searchFields = Seq("title", "abstract", "keywords", "citation", "text"),
      highlightFields = Seq("title", "abstract", "citation", "text"),
      aggregationFields = Seq("publication_type", "pubchem_data_source")
    ),
    ElasticsearchQueryDefinition(
      name = "literature_pmid_40581877",
      description = "Find literature linked to PMID 40581877",
      query = "isopropanolamine",
      filters = Map("doc_type" -> Seq("literature"), "pmid" -> Seq("40581877")),
      searchFields = Seq("title", "abstract", "citation", "text"),
      highlightFields = Seq("title", "abstract", "citation"),
      aggregationFields = Seq("publication_type")
    ),
    ElasticsearchQueryDefinition(
      name = "patent_electronic_grade_after_2020",
      description = "Find patents about electronic grade isopropanolamine filed after 2020",
      query = "electronic grade isopropanolamine",
      filters = Map("doc_type" -> Seq("patent")),
      searchFields = Seq("title", "abstract", "inventors", "assignees", "text"),
      highlightFields = Seq("title", "abstract", "text"),
      aggregationFields = Seq("doc_type")
    ),
    ElasticsearchQueryDefinition(
      name = "bioactivity_confirmatory_estrogen_or_plasmodium",
      description = "Find confirmatory bioactivity records mentioning estrogen receptor or plasmodium falciparum",
      query = "estrogen receptor plasmodium falciparum",
      filters = Map("doc_type" -> Seq("bioactivity"), "aid_type" -> Seq("confirmatory")),
      searchFields = Seq("bioassay_name", "target_name", "activity", "activity_type", "text"),
      highlightFields = Seq("bioassay_name", "target_name", "text"),
      aggregationFields = Seq("taxonomy_id", "aid_type")
    ),
    ElasticsearchQueryDefinition(
      name = "pathway_accession_smp0002032",
      description = "Exact lookup by PathBank accession SMP0002032",
      query = "glutathione metabolism",
      filters = Map("doc_type" -> Seq("pathway"), "pathway_accession" -> Seq("pathbank:smp0002032")),
      searchFields = Seq("title", "pathway_name", "pathway_category", "text"),
      highlightFields = Seq("title", "pathway_name", "text"),
      aggregationFields = Seq("taxonomy_id", "data_source")
    )
  )
