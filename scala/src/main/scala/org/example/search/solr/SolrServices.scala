package org.example.search.solr

import org.apache.solr.client.solrj.SolrQuery
import org.apache.solr.client.solrj.impl.Http2SolrClient
import org.apache.solr.common.SolrInputDocument
import org.apache.solr.common.params.HighlightParams
import org.example.search.lucene.LuceneDocumentBatch
import org.example.search.lucene.LuceneSourceDocument
import org.slf4j.LoggerFactory
import tools.jackson.databind.json.JsonMapper
import tools.jackson.module.scala.DefaultScalaModule

import java.io.IOException
import java.nio.charset.StandardCharsets
import java.nio.file.Files
import java.nio.file.Path
import scala.jdk.CollectionConverters.*
import scala.util.Using

object SolrExportService:
  private val logger = LoggerFactory.getLogger(getClass)
  private val jsonMapper = JsonMapper.builder().addModule(DefaultScalaModule()).build()
  private val configsetResources = Seq(
    "/solr/cid4/conf/managed-schema.xml",
    "/solr/cid4/conf/solrconfig.xml",
    "/solr/cid4/conf/synonyms.txt"
  )

  def exportDocuments(
      collection: String,
      docsPath: Path,
      configsetPath: Path,
      batches: Seq[LuceneDocumentBatch]
  ): SolrExportSummary =
    Files.createDirectories(docsPath.getParent)
    writeConfigset(configsetPath)

    val countsByDocType = scala.collection.mutable.Map.empty[String, Int].withDefaultValue(0)
    val sourceFiles = scala.collection.mutable.LinkedHashSet.empty[String]
    var totalDocuments = 0

    Using.resource(Files.newBufferedWriter(docsPath, StandardCharsets.UTF_8)) { writer =>
      batches.foreach { batch =>
        sourceFiles += batch.sourceFile
        batch.loader().foreach { sourceDocument =>
          val exportDocument = toSolrExportDocument(sourceDocument)
          writer.write(jsonMapper.writeValueAsString(exportDocument))
          writer.newLine()
          totalDocuments += 1
          countsByDocType.update(sourceDocument.docType, countsByDocType(sourceDocument.docType) + 1)
        }
        logger.info(s"Finished Solr export for ${batch.sourceFile}")
      }
    }

    SolrExportSummary(
      collection = collection,
      docsPath = docsPath.toAbsolutePath.toString,
      configsetPath = configsetPath.toAbsolutePath.toString,
      documentCount = totalDocuments,
      countsByDocType = countsByDocType.toSeq.sortBy(_._1).toMap,
      sourceFiles = sourceFiles.toSeq
    )

  def toSolrInputDocument(sourceDocument: LuceneSourceDocument): SolrInputDocument =
    val solrDocument = new SolrInputDocument()
    toSolrExportDocument(sourceDocument).foreach { case (fieldName, value) =>
      value match
        case values: Seq[?] => values.foreach(item => solrDocument.addField(fieldName, item.asInstanceOf[AnyRef]))
        case other          => solrDocument.addField(fieldName, other.asInstanceOf[AnyRef])
    }
    solrDocument

  private def toSolrExportDocument(sourceDocument: LuceneSourceDocument): Map[String, Any] =
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
        fields.update(s"${fieldName}_txt", normalized)
    }

    sourceDocument.exactFields.foreach { case (fieldName, values) =>
      val normalizedValues = values
        .map(_.trim)
        .filter(_.nonEmpty)
        .map(_.toLowerCase)
        .distinct
      if normalizedValues.nonEmpty then
        fields.update(s"${fieldName}_ss", normalizedValues)
    }

    sourceDocument.intFields.foreach { case (fieldName, value) =>
      fields.update(s"${fieldName}_i", value)
    }

    sourceDocument.floatFields.foreach { case (fieldName, value) =>
      fields.update(s"${fieldName}_f", value)
    }

    fields.toMap

  private def writeConfigset(configsetPath: Path): Unit =
    configsetResources.foreach { resourcePath =>
      val fileName = resourcePath.split('/').last
      val targetPath = configsetPath.resolve(fileName)
      Files.createDirectories(targetPath.getParent)
      Using.resource(Option(getClass.getResourceAsStream(resourcePath)).getOrElse {
        throw new IOException(s"Missing bundled Solr resource: $resourcePath")
      }) { inputStream =>
        Files.copy(inputStream, targetPath, java.nio.file.StandardCopyOption.REPLACE_EXISTING)
      }
    }

object SolrRuntimeService:
  private val logger = LoggerFactory.getLogger(getClass)
  private val exactFieldNames = Seq(
    "pmid_ss",
    "doi_ss",
    "publicationnumber_ss",
    "aid_type_ss",
    "bioassay_aid_ss",
    "taxonomy_id_ss",
    "pathway_accession_ss"
  )

  def postDocuments(
      solrUrl: String,
      collection: String,
      batches: Seq[LuceneDocumentBatch],
      batchSize: Int = 500
  ): SolrIngestSummary =
    val client = new Http2SolrClient.Builder(solrUrl).build()
    var postedDocuments = 0
    val buffer = scala.collection.mutable.ArrayBuffer.empty[SolrInputDocument]

    try
      batches.foreach { batch =>
        batch.loader().foreach { sourceDocument =>
          buffer += SolrExportService.toSolrInputDocument(sourceDocument)
          if buffer.size >= batchSize then
            client.add(collection, buffer.asJava)
            postedDocuments += buffer.size
            buffer.clear()
        }
      }
      if buffer.nonEmpty then
        client.add(collection, buffer.asJava)
        postedDocuments += buffer.size
        buffer.clear()

      client.commit(collection)
      logger.info(s"Posted $postedDocuments document(s) to Solr collection '$collection'")
      SolrIngestSummary("posted", collection, postedDocuments, batchSize)
    finally client.close()

  def runExampleQueries(solrUrl: String, collection: String): Seq[SolrQueryExampleResult] =
    val client = new Http2SolrClient.Builder(solrUrl).build()
    try solrExamples.map(example => executeExample(client, collection, example))
    finally client.close()

  private def executeExample(
      client: Http2SolrClient,
      collection: String,
      example: SolrQueryDefinition
  ): SolrQueryExampleResult =
    val query = new SolrQuery()
    query.setQuery(example.query)
    if example.filterQueries.nonEmpty then query.setFilterQueries(example.filterQueries*)
    query.setRows(example.rows)
    query.setHighlight(true)
    query.setParam(HighlightParams.SNIPPETS, "1")
    query.setParam(HighlightParams.FRAGSIZE, "180")
    example.highlightFields.foreach(query.addHighlightField)
    if example.facetFields.nonEmpty then
      query.setFacet(true)
      example.facetFields.foreach(fieldName => query.addFacetField(fieldName))

    val response = client.query(collection, query)
    val highlights = Option(response.getHighlighting).map(_.asScala.toMap).getOrElse(Map.empty)
    val results = response.getResults

    val hits = results.asScala.toSeq.map { document =>
      val id = Option(document.getFieldValue("id")).map(_.toString).getOrElse("")
      val hitHighlights = highlights
        .get(id)
        .map(_.asScala.toMap.view.mapValues(_.asScala.toSeq).toMap)
        .getOrElse(Map.empty)
      val snippet = example.highlightFields.iterator
        .flatMap(fieldName => hitHighlights.get(fieldName).toSeq.flatten)
        .map(_.trim)
        .find(_.nonEmpty)
        .getOrElse(Option(document.getFieldValue("text")).map(_.toString.take(180)).getOrElse(""))
      val exactFields = exactFieldNames.flatMap { fieldName =>
        val values =
          Option(document.getFieldValues(fieldName)).map(_.asScala.toSeq.map(_.toString)).getOrElse(Seq.empty)
        if values.nonEmpty then Some(fieldName.stripSuffix("_ss") -> values) else None
      }.toMap

      SolrQueryHit(
        id = id,
        docType = Option(document.getFieldValue("doc_type")).map(_.toString).getOrElse(""),
        title = Option(document.getFieldValue("title")).map(_.toString).getOrElse(""),
        sourceFile = Option(document.getFieldValue("source_file")).map(_.toString).getOrElse(""),
        rowId = Option(document.getFieldValue("row_id")).map(_.toString).getOrElse(""),
        score = Option(document.getFieldValue("score")).map(_.toString.toFloat).getOrElse(0.0f),
        snippet = snippet,
        exactFields = exactFields
      )
    }

    val facets = Option(response.getFacetFields).map(_.asScala.toSeq).getOrElse(Seq.empty).flatMap { facetField =>
      val buckets = Option(facetField.getValues).map(_.asScala.toSeq).getOrElse(Seq.empty).map { count =>
        SolrFacetBucket(count.getName, count.getCount)
      }
      if buckets.nonEmpty then Some(facetField.getName -> buckets) else None
    }.toMap

    SolrQueryExampleResult(
      name = example.name,
      description = example.description,
      status = "ok",
      query = example.query,
      filterQueries = example.filterQueries,
      totalHits = results.getNumFound,
      facets = facets,
      hits = hits
    )

  private final case class SolrQueryDefinition(
      name: String,
      description: String,
      query: String,
      filterQueries: Seq[String],
      highlightFields: Seq[String],
      facetFields: Seq[String],
      rows: Int = 5
  )

  private val solrExamples = Seq(
    SolrQueryDefinition(
      name = "literature_isopropanolamine_fungicide",
      description = "Find literature about isopropanolamine and fungicide",
      query = "isopropanolamine fungicide",
      filterQueries = Seq("doc_type:literature"),
      highlightFields = Seq("title", "abstract_txt", "citation_txt", "text"),
      facetFields = Seq("publication_type_ss", "pubchem_data_source_ss")
    ),
    SolrQueryDefinition(
      name = "literature_pmid_40581877",
      description = "Find literature linked to PMID 40581877",
      query = "*:*",
      filterQueries = Seq("doc_type:literature", "pmid_ss:40581877"),
      highlightFields = Seq("title", "abstract_txt", "citation_txt"),
      facetFields = Seq("publication_type_ss")
    ),
    SolrQueryDefinition(
      name = "patent_electronic_grade_after_2020",
      description = "Find patents about electronic grade isopropanolamine filed after 2020",
      query = "\"electronic grade\" AND isopropanolamine",
      filterQueries = Seq("doc_type:patent", "priority_year_i:[2020 TO *]"),
      highlightFields = Seq("title", "abstract_txt"),
      facetFields = Seq("doc_type")
    ),
    SolrQueryDefinition(
      name = "bioactivity_confirmatory_under_100",
      description =
        "Find confirmatory bioactivity records mentioning estrogen receptor or plasmodium falciparum with Activity_Value <= 100",
      query = "\"estrogen receptor\" OR \"plasmodium falciparum\"",
      filterQueries = Seq("doc_type:bioactivity", "aid_type_ss:confirmatory", "activity_value_f:[* TO 100]"),
      highlightFields = Seq("bioassay_name_txt", "target_name_txt", "text"),
      facetFields = Seq("taxonomy_id_ss", "aid_type_ss")
    ),
    SolrQueryDefinition(
      name = "pathway_accession_smp0002032",
      description = "Exact lookup by PathBank accession SMP0002032",
      query = "*:*",
      filterQueries = Seq("doc_type:pathway", "pathway_accession_ss:pathbank\\:smp0002032"),
      highlightFields = Seq("title", "pathway_name_txt"),
      facetFields = Seq("taxonomy_id_ss", "data_source_ss")
    )
  )
