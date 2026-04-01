package org.example.search.solr

import org.example.search.lucene.LuceneDatasetLoader
import org.example.search.lucene.LuceneDocumentBatch
import org.example.utils as fsUtils
import org.slf4j.LoggerFactory
import tools.jackson.databind.json.JsonMapper
import tools.jackson.module.scala.DefaultScalaModule

import java.nio.file.Files
import java.nio.file.Path

object SolrCli:
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
    val outDirectory = dataRoot.resolve("out").resolve("solr")
    val docsPath = outDirectory.resolve("cid4.solr.docs.jsonl")
    val configsetPath = outDirectory.resolve("configsets").resolve("cid4").resolve("conf")
    Files.createDirectories(outDirectory)

    val collection = Option(System.getenv("SOLR_COLLECTION")).filter(_.trim.nonEmpty).getOrElse("cid4")
    val solrUrl = Option(System.getenv("SOLR_URL")).filter(_.trim.nonEmpty)
    val batches = documentBatches(dataRoot)

    val exportSummary =
      if normalizedMode == "export" || normalizedMode == "all" then
        Some(SolrExportService.exportDocuments(collection, docsPath, configsetPath, batches))
      else None

    val runtimeSummary = solrUrl match
      case Some(url) =>
        SolrRuntimeSummary(
          mode = normalizedMode,
          solrUrl = Some(url),
          collection = collection,
          available = true,
          status = "configured",
          message = s"Solr live mode enabled for collection '$collection'"
        )
      case None =>
        SolrRuntimeSummary(
          mode = normalizedMode,
          solrUrl = None,
          collection = collection,
          available = false,
          status = "skipped",
          message = "SOLR_URL is not set; only offline export artifacts were produced"
        )

    val ingestSummary =
      if (normalizedMode == "post" || normalizedMode == "all") && solrUrl.nonEmpty then
        Some(SolrRuntimeService.postDocuments(solrUrl.get, collection, batches))
      else None

    val queryExamples =
      if (normalizedMode == "query" || normalizedMode == "all") && solrUrl.nonEmpty then
        SolrRuntimeService.runExampleQueries(solrUrl.get, collection)
      else Seq.empty

    val summary = SolrRunSummary(exportSummary, runtimeSummary, ingestSummary, queryExamples)
    val summaryPath = outDirectory.resolve("cid4.solr.summary.json")
    jsonMapper.writerWithDefaultPrettyPrinter().writeValue(summaryPath.toFile, summary)
    logger.info(s"Solr summary written to $summaryPath")

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
