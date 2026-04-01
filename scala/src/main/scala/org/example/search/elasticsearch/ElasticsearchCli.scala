package org.example.search.elasticsearch

import org.example.search.lucene.LuceneDatasetLoader
import org.example.search.lucene.LuceneDocumentBatch
import org.example.utils as fsUtils
import org.slf4j.LoggerFactory
import tools.jackson.databind.json.JsonMapper
import tools.jackson.module.scala.DefaultScalaModule

import java.nio.file.Files
import java.nio.file.Path

object ElasticsearchCli:
  private val logger = LoggerFactory.getLogger(getClass)
  private val jsonMapper = JsonMapper.builder().addModule(DefaultScalaModule()).build()

  def run(mode: String): Unit =
    val dataDirectory = fsUtils.getDataDir()
    if dataDirectory == null then
      throw new IllegalStateException("Env variable DATA_DIR is not set")

    val normalizedMode =
      mode.trim.toLowerCase match
        case "export" | "post" | "query" | "all" => mode.trim.toLowerCase
        case _                                   => "all"

    val dataRoot = Path.of(dataDirectory)
    val outDirectory = dataRoot.resolve("out").resolve("elasticsearch")
    val bulkPath = outDirectory.resolve("cid4.elasticsearch.bulk.ndjson")
    val configDirectory = outDirectory.resolve("config")
    Files.createDirectories(outDirectory)

    val indexName = Option(System.getenv("ELASTICSEARCH_INDEX")).filter(_.trim.nonEmpty).getOrElse("cid4")
    val elasticsearchUrl = Option(System.getenv("ELASTICSEARCH_URL")).filter(_.trim.nonEmpty)
    val batches = documentBatches(dataRoot)

    val exportSummary =
      if normalizedMode == "export" || normalizedMode == "all" then
        Some(ElasticsearchExportService.exportDocuments(indexName, bulkPath, configDirectory, batches))
      else None

    val runtimeSummary = elasticsearchUrl match
      case Some(url) =>
        ElasticsearchRuntimeSummary(
          mode = normalizedMode,
          elasticsearchUrl = Some(url),
          indexName = indexName,
          available = true,
          status = "configured",
          message = s"Elasticsearch live mode enabled for index '$indexName'"
        )
      case None =>
        ElasticsearchRuntimeSummary(
          mode = normalizedMode,
          elasticsearchUrl = None,
          indexName = indexName,
          available = false,
          status = "skipped",
          message = "ELASTICSEARCH_URL is not set; only offline export artifacts were produced"
        )

    val ingestSummary =
      if (normalizedMode == "post" || normalizedMode == "all") && elasticsearchUrl.nonEmpty then
        Some(ElasticsearchRuntimeService.postDocuments(elasticsearchUrl.get, indexName, configDirectory, batches))
      else None

    val queryExamples =
      if (normalizedMode == "query" || normalizedMode == "all") && elasticsearchUrl.nonEmpty then
        ElasticsearchRuntimeService.runExampleQueries(elasticsearchUrl.get, indexName)
      else Seq.empty

    val summary = ElasticsearchRunSummary(exportSummary, runtimeSummary, ingestSummary, queryExamples)
    val summaryPath = outDirectory.resolve("cid4.elasticsearch.summary.json")
    jsonMapper.writerWithDefaultPrettyPrinter().writeValue(summaryPath.toFile, summary)
    logger.info(s"Elasticsearch summary written to $summaryPath")

  private def documentBatches(dataRoot: Path): Seq[LuceneDocumentBatch] =
    Seq(
      LuceneDocumentBatch(
        "pubchem_cid_4_literature.csv",
        () => LuceneDatasetLoader.loadLiteratureDocuments(dataRoot.resolve("pubchem_cid_4_literature.csv"))
      ),
      LuceneDocumentBatch(
        "pubchem_cid_4_patent.csv",
        () => LuceneDatasetLoader.loadPatentDocuments(dataRoot.resolve("pubchem_cid_4_patent.csv"))
      ),
      LuceneDocumentBatch(
        "pubchem_cid_4_bioactivity.csv",
        () => LuceneDatasetLoader.loadBioactivityDocuments(dataRoot.resolve("pubchem_cid_4_bioactivity.csv"))
      ),
      LuceneDocumentBatch(
        "pubchem_cid_4_consolidatedcompoundtaxonomy.csv",
        () =>
          LuceneDatasetLoader.loadTaxonomyDocuments(dataRoot.resolve("pubchem_cid_4_consolidatedcompoundtaxonomy.csv"))
      ),
      LuceneDocumentBatch(
        "pubchem_cid_4_pathway.csv",
        () => LuceneDatasetLoader.loadPathwayDocuments(dataRoot.resolve("pubchem_cid_4_pathway.csv"))
      ),
      LuceneDocumentBatch(
        "pubchem_cid_4_pathwayreaction.csv",
        () => LuceneDatasetLoader.loadPathwayReactionDocuments(dataRoot.resolve("pubchem_cid_4_pathwayreaction.csv"))
      ),
      LuceneDocumentBatch(
        "pubchem_cid_4_cpdat.csv",
        () => LuceneDatasetLoader.loadCpdatDocuments(dataRoot.resolve("pubchem_cid_4_cpdat.csv"))
      ),
      LuceneDocumentBatch(
        "NLM_Curated_Citations_CID_4.json",
        () => LuceneDatasetLoader.loadCuratedCitationDocuments(dataRoot.resolve("NLM_Curated_Citations_CID_4.json"))
      ),
      LuceneDocumentBatch(
        "COMPOUND_CID_4.json",
        () => LuceneDatasetLoader.loadCompoundRecordDocuments(dataRoot.resolve("COMPOUND_CID_4.json"))
      )
    )
