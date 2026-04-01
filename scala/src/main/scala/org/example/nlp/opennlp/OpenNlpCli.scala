package org.example.nlp.opennlp

import org.example.utils as fsUtils
import org.slf4j.LoggerFactory
import tools.jackson.databind.json.JsonMapper
import tools.jackson.module.scala.DefaultScalaModule

import java.nio.file.Files
import java.nio.file.Path

object OpenNlpCli:
  private val logger = LoggerFactory.getLogger(getClass)
  private val jsonMapper = JsonMapper.builder().addModule(DefaultScalaModule()).build()

  def run(mode: String): Unit =
    val dataDirectory = fsUtils.getDataDir()
    if dataDirectory == null then
      throw new IllegalStateException("Env variable DATA_DIR is not set")

    val normalizedMode =
      mode.trim.toLowerCase match
        case "literature" | "patent" | "assay" | "pathway" | "taxonomy" | "cpdat" | "toxicology" |
            "springer" | "all" => mode.trim.toLowerCase
        case _ => "all"

    val dataRoot = Path.of(dataDirectory)
    val outDirectory = dataRoot.resolve("out").resolve("opennlp")
    Files.createDirectories(outDirectory)

    val runtime = OpenNlpService.buildRuntime(resolveModelDirectory())
    val selectedWorkflows =
      workflowSpecs(dataRoot).filter(spec => normalizedMode == "all" || spec.name == normalizedMode)

    val workflowOutputs = selectedWorkflows.map { spec =>
      val outputPath = outDirectory.resolve(s"cid4.opennlp.${spec.name}.summary.json")
      val summary = OpenNlpService.analyzeWorkflow(spec, runtime, outputPath)
      jsonMapper.writerWithDefaultPrettyPrinter().writeValue(outputPath.toFile, summary)
      logger.info(s"OpenNLP workflow '${spec.name}' summary written to $outputPath")
      spec.name -> outputPath.toString
    }.toMap

    val runSummary = OpenNlpRunSummary(
      runtime = runtime.summary,
      generatedAtPath = outDirectory,
      workflowOutputs = workflowOutputs
    )
    val summaryPath = outDirectory.resolve("cid4.opennlp.summary.json")
    jsonMapper.writerWithDefaultPrettyPrinter().writeValue(summaryPath.toFile, runSummary)
    logger.info(s"OpenNLP run summary written to $summaryPath")

  private def workflowSpecs(dataRoot: Path): Seq[OpenNlpWorkflowSpec] =
    Seq(
      OpenNlpWorkflowSpec(
        name = "literature",
        description =
          "Sentence, token, phrase, and publication-type analysis over literature titles, abstracts, keywords, citations, and subjects",
        sourceFiles = Seq("pubchem_cid_4_literature.csv"),
        labelName = Some("publication_type"),
        loader = () => OpenNlpDatasetLoader.literatureDocuments(dataRoot)
      ),
      OpenNlpWorkflowSpec(
        name = "patent",
        description = "Sentence, token, and phrase analysis over patent titles, abstracts, inventors, and assignees",
        sourceFiles = Seq("pubchem_cid_4_patent.csv"),
        labelName = None,
        loader = () => OpenNlpDatasetLoader.patentDocuments(dataRoot)
      ),
      OpenNlpWorkflowSpec(
        name = "assay",
        description =
          "Phrase extraction and assay-family categorization over bioassay names, targets, activity types, and citations",
        sourceFiles = Seq("pubchem_cid_4_bioactivity.csv"),
        labelName = Some("aid_type"),
        loader = () => OpenNlpDatasetLoader.assayDocuments(dataRoot)
      ),
      OpenNlpWorkflowSpec(
        name = "pathway",
        description = "Reaction and pathway text normalization over pathway and pathway-reaction rows",
        sourceFiles = Seq("pubchem_cid_4_pathway.csv", "pubchem_cid_4_pathwayreaction.csv"),
        labelName = Some("pathway_source"),
        loader = () => OpenNlpDatasetLoader.pathwayDocuments(dataRoot)
      ),
      OpenNlpWorkflowSpec(
        name = "taxonomy",
        description = "Organism and taxonomy phrase extraction over taxonomy and source-organism strings",
        sourceFiles = Seq("pubchem_cid_4_consolidatedcompoundtaxonomy.csv"),
        labelName = Some("data_source"),
        loader = () => OpenNlpDatasetLoader.taxonomyDocuments(dataRoot)
      ),
      OpenNlpWorkflowSpec(
        name = "cpdat",
        description = "Product-use phrase extraction and categorization over CPDat categories and descriptions",
        sourceFiles = Seq("pubchem_cid_4_cpdat.csv"),
        labelName = Some("categorization_type"),
        loader = () => OpenNlpDatasetLoader.cpdatDocuments(dataRoot)
      ),
      OpenNlpWorkflowSpec(
        name = "toxicology",
        description = "Short toxicology phrase extraction over ChemIDplus effect, route, reference, and dose fields",
        sourceFiles = Seq("pubchem_sid_134971235_chemidplus.csv"),
        labelName = Some("route"),
        loader = () => OpenNlpDatasetLoader.toxicologyDocuments(dataRoot)
      ),
      OpenNlpWorkflowSpec(
        name = "springer",
        description = "Compact publication metadata processing over Springer Nature article rows",
        sourceFiles = Seq("pubchem_sid_341143784_springernature.csv"),
        labelName = Some("publication_type"),
        loader = () => OpenNlpDatasetLoader.springerDocuments(dataRoot)
      )
    )

  private def resolveModelDirectory(): Option[Path] =
    Option(System.getenv("OPENNLP_MODEL_DIR")).map(_.trim).filter(_.nonEmpty).map(Path.of(_))
