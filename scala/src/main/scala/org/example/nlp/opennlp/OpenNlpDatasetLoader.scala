package org.example.nlp.opennlp

import org.apache.commons.csv.CSVFormat
import org.apache.commons.csv.CSVRecord
import org.apache.commons.csv.DuplicateHeaderMode
import org.example.search.lucene.LuceneDatasetLoader
import org.example.search.lucene.LuceneSourceDocument
import tools.jackson.databind.json.JsonMapper
import tools.jackson.module.scala.DefaultScalaModule

import java.nio.charset.StandardCharsets
import java.nio.file.Files
import java.nio.file.Path
import scala.jdk.CollectionConverters.*
import scala.util.Try

object OpenNlpDatasetLoader:
  private val csvFormat = CSVFormat.DEFAULT
    .builder()
    .setHeader()
    .setSkipHeaderRecord(true)
    .setIgnoreEmptyLines(true)
    .setTrim(true)
    .setDuplicateHeaderMode(DuplicateHeaderMode.ALLOW_ALL)
    .build()

  private val jsonMapper = JsonMapper.builder().addModule(DefaultScalaModule()).build()

  def literatureDocuments(dataRoot: Path): Iterator[OpenNlpTextDocument] =
    LuceneDatasetLoader
      .loadLiteratureDocuments(dataRoot.resolve("pubchem_cid_4_literature.csv"))
      .map(doc =>
        fromLucene(
          workflow = "literature",
          doc = doc,
          preferredTextFields = Seq("title", "abstract", "keywords", "citation", "subject", "publication_name"),
          label = firstExact(doc, "publication_type")
        )
      )

  def patentDocuments(dataRoot: Path): Iterator[OpenNlpTextDocument] =
    LuceneDatasetLoader
      .loadPatentDocuments(dataRoot.resolve("pubchem_cid_4_patent.csv"))
      .map(doc =>
        fromLucene(
          workflow = "patent",
          doc = doc,
          preferredTextFields = Seq("title", "abstract", "inventors", "assignees"),
          label = None
        )
      )

  def assayDocuments(dataRoot: Path): Iterator[OpenNlpTextDocument] =
    LuceneDatasetLoader
      .loadBioactivityDocuments(dataRoot.resolve("pubchem_cid_4_bioactivity.csv"))
      .map(doc =>
        fromLucene(
          workflow = "assay",
          doc = doc,
          preferredTextFields = Seq(
            "bioassay_name",
            "target_name",
            "activity_type",
            "bioassay_data_source",
            "citation"
          ),
          label = firstExact(doc, "aid_type")
        )
      )

  def pathwayDocuments(dataRoot: Path): Iterator[OpenNlpTextDocument] =
    val pathwayRows =
      LuceneDatasetLoader
        .loadPathwayDocuments(dataRoot.resolve("pubchem_cid_4_pathway.csv"))
        .map(doc =>
          fromLucene(
            workflow = "pathway",
            doc = doc,
            preferredTextFields = Seq("pathway_name", "pathway_type", "pathway_category", "taxonomy_name", "citation"),
            label = firstExact(doc, "data_source")
          )
        )
    val reactionRows =
      LuceneDatasetLoader
        .loadPathwayReactionDocuments(dataRoot.resolve("pubchem_cid_4_pathwayreaction.csv"))
        .map(doc =>
          fromLucene(
            workflow = "pathway",
            doc = doc,
            preferredTextFields = Seq("equation", "reaction", "control", "taxonomy_name"),
            label = firstExact(doc, "pathway_accession")
          )
        )
    pathwayRows ++ reactionRows

  def taxonomyDocuments(dataRoot: Path): Iterator[OpenNlpTextDocument] =
    LuceneDatasetLoader
      .loadTaxonomyDocuments(dataRoot.resolve("pubchem_cid_4_consolidatedcompoundtaxonomy.csv"))
      .map(doc =>
        fromLucene(
          workflow = "taxonomy",
          doc = doc,
          preferredTextFields = Seq("source_organism", "taxonomy_name", "source", "compound"),
          label = firstExact(doc, "data_source")
        )
      )

  def cpdatDocuments(dataRoot: Path): Iterator[OpenNlpTextDocument] =
    LuceneDatasetLoader
      .loadCpdatDocuments(dataRoot.resolve("pubchem_cid_4_cpdat.csv"))
      .map(doc =>
        fromLucene(
          workflow = "cpdat",
          doc = doc,
          preferredTextFields = Seq("category", "category_description", "compound_name"),
          label = firstExact(doc, "categorization_type")
        )
      )

  def toxicologyDocuments(dataRoot: Path): Iterator[OpenNlpTextDocument] =
    iterateCsv(dataRoot.resolve("pubchem_sid_134971235_chemidplus.csv")).zipWithIndex.map { case (record, index) =>
      val rowId = firstNonEmpty(recordValue(record, "gid"), recordValue(record, "Substance_SID"), index.toString)
      val title = firstNonEmpty(recordValue(record, "Effect"), recordValue(record, "Route"), s"toxicology_$index")
      OpenNlpTextDocument(
        docId = s"toxicology::pubchem_sid_134971235_chemidplus.csv::$rowId",
        workflow = "toxicology",
        title = title,
        text = compactText(
          Seq(
            recordValue(record, "Effect"),
            recordValue(record, "Route"),
            recordValue(record, "Reference"),
            recordValue(record, "Test_Type"),
            recordValue(record, "Dose")
          )
        ),
        metadata = compactMetadata(
          "compound_cid" -> recordValue(record, "Compound_CID"),
          "substance_sid" -> recordValue(record, "Substance_SID"),
          "route" -> recordValue(record, "Route"),
          "test_type" -> recordValue(record, "Test_Type")
        ),
        label = Option(recordValue(record, "Route")).filter(_.nonEmpty)
      )
    }

  def springerDocuments(dataRoot: Path): Iterator[OpenNlpTextDocument] =
    iterateCsv(dataRoot.resolve("pubchem_sid_341143784_springernature.csv")).zipWithIndex.map { case (record, index) =>
      val rowId = firstNonEmpty(recordValue(record, "oid"), recordValue(record, "DOI"), index.toString)
      val title = firstNonEmpty(recordValue(record, "Title"), s"springer_$index")
      OpenNlpTextDocument(
        docId = s"springer::pubchem_sid_341143784_springernature.csv::$rowId",
        workflow = "springer",
        title = title,
        text = compactText(
          Seq(
            recordValue(record, "Title"),
            recordValue(record, "Publication_Name"),
            recordValue(record, "Subject"),
            recordValue(record, "Publication_Type")
          )
        ),
        metadata = compactMetadata(
          "doi" -> recordValue(record, "DOI"),
          "pmid" -> recordValue(record, "PMID"),
          "publication_type" -> recordValue(record, "Publication_Type"),
          "publication_date" -> recordValue(record, "Publication_Date")
        ),
        label = Option(recordValue(record, "Publication_Type")).filter(_.nonEmpty)
      )
    }

  private def fromLucene(
      workflow: String,
      doc: LuceneSourceDocument,
      preferredTextFields: Seq[String],
      label: Option[String]
  ): OpenNlpTextDocument =
    val chosenText =
      preferredTextFields
        .flatMap(field => doc.textFields.get(field).map(value => field -> value))
        .distinctBy(_._2)
        .map(_._2)
    val fallbackText = doc.textFields.values.toSeq
    OpenNlpTextDocument(
      docId = doc.docId,
      workflow = workflow,
      title = doc.title,
      text = compactText(if chosenText.nonEmpty then chosenText else fallbackText),
      metadata = compactMetadata(
        Map("source_file" -> doc.sourceFile, "source_row_id" -> doc.sourceRowId) ++
          doc.exactFields.map { case (key, values) => key -> values.mkString("|") }
      ),
      label = label.filter(_.trim.nonEmpty)
    )

  private def firstExact(doc: LuceneSourceDocument, field: String): Option[String] =
    doc.exactFields.get(field).flatMap(_.headOption).map(_.trim).filter(_.nonEmpty)

  private def compactText(values: Seq[String]): String =
    values.map(_.trim).filter(_.nonEmpty).distinct.mkString("\n\n")

  private def compactMetadata(entries: (String, String)*): Map[String, String] =
    entries.collect { case (key, value) if value.trim.nonEmpty => key -> value.trim }.toMap

  private def compactMetadata(entries: Map[String, String]): Map[String, String] =
    entries.collect { case (key, value) if value.trim.nonEmpty => key -> value.trim }

  private def iterateCsv(path: Path): Iterator[CSVRecord] =
    val reader = Files.newBufferedReader(path, StandardCharsets.UTF_8)
    val parser = csvFormat.parse(reader)
    val records = parser.iterator().asScala
    new Iterator[CSVRecord]:
      private var closed = false

      private def closeResources(): Unit =
        if !closed then
          closed = true
          parser.close()
          reader.close()

      override def hasNext: Boolean =
        val available = records.hasNext
        if !available then closeResources()
        available

      override def next(): CSVRecord =
        if hasNext then records.next()
        else throw new NoSuchElementException(s"No more CSV records in $path")

  private def recordValue(record: CSVRecord, field: String): String =
    Try(Option(record.get(field)).getOrElse("").trim).getOrElse("")

  private def firstNonEmpty(values: String*): String =
    values.iterator.map(_.trim).find(_.nonEmpty).getOrElse("")
