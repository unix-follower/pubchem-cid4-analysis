package org.example.search.lucene

import org.example.utils as fsUtils
import org.slf4j.LoggerFactory
import tools.jackson.databind.json.JsonMapper
import tools.jackson.module.scala.DefaultScalaModule

import java.nio.file.Files
import java.nio.file.Path

object LuceneCli:
  private val logger = LoggerFactory.getLogger(getClass)
  private val jsonMapper = JsonMapper.builder().addModule(DefaultScalaModule()).build()

  def run(mode: String): Unit =
    val dataDirectory = fsUtils.getDataDir()
    if dataDirectory == null then
      throw new IllegalStateException("Env variable DATA_DIR is not set")

    val normalizedMode =
      mode.trim.toLowerCase match
        case "build" | "query" | "all" => mode.trim.toLowerCase
        case _                         => "all"

    val outDirectory = Path.of(dataDirectory, "out", "lucene")
    val indexPath = outDirectory.resolve("index")
    Files.createDirectories(outDirectory)
    val dataRoot = Path.of(dataDirectory)

    if normalizedMode == "build" || normalizedMode == "all" then
      val batches = Seq(
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
            LuceneDatasetLoader.loadTaxonomyDocuments(
              dataRoot.resolve("pubchem_cid_4_consolidatedcompoundtaxonomy.csv")
            )
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
          "COMPOUND_CID_4.json",
          () => LuceneDatasetLoader.loadCompoundRecordDocuments(dataRoot.resolve("COMPOUND_CID_4.json"))
        )
      )
      val buildSummary = LuceneIndexService.buildIndex(indexPath, batches)
      writeJson(outDirectory.resolve("cid4.lucene.index.summary.json"), buildSummary)
      logger.info(s"Lucene index summary written to ${outDirectory.resolve("cid4.lucene.index.summary.json")}")

    if normalizedMode == "query" || normalizedMode == "all" then
      if !Files.exists(indexPath) then
        throw new IllegalStateException(s"Lucene index does not exist at $indexPath. Run lucene build first.")
      val querySummary = LuceneQueryService.runExampleQueries(indexPath)
      writeJson(outDirectory.resolve("cid4.lucene.query_examples.summary.json"), querySummary)
      logger.info(s"Lucene query summary written to ${outDirectory.resolve("cid4.lucene.query_examples.summary.json")}")

  private def writeJson(path: Path, value: Any): Unit =
    Files.createDirectories(path.getParent)
    jsonMapper.writerWithDefaultPrettyPrinter().writeValue(path.toFile, value)
