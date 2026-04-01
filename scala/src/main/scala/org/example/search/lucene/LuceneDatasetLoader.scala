package org.example.search.lucene

import org.apache.commons.csv.CSVFormat
import org.apache.commons.csv.CSVRecord
import org.apache.commons.csv.DuplicateHeaderMode
import org.slf4j.LoggerFactory
import tools.jackson.databind.JsonNode
import tools.jackson.databind.json.JsonMapper
import tools.jackson.module.scala.DefaultScalaModule

import java.nio.charset.StandardCharsets
import java.nio.file.Files
import java.nio.file.Path
import scala.jdk.CollectionConverters.*
import scala.util.Try

object LuceneDatasetLoader:
  private val logger = LoggerFactory.getLogger(getClass)
  private val jsonMapper = JsonMapper.builder().addModule(DefaultScalaModule()).build()

  private val csvFormat = CSVFormat.DEFAULT
    .builder()
    .setHeader()
    .setSkipHeaderRecord(true)
    .setIgnoreEmptyLines(true)
    .setTrim(true)
    .setDuplicateHeaderMode(DuplicateHeaderMode.ALLOW_ALL)
    .build()

  def loadLiteratureDocuments(path: Path): Iterator[LuceneSourceDocument] =
    iterateCsv(path).zipWithIndex.map { case (record, index) =>
      val rowId = firstNonEmpty(
        recordValue(record, "PubChem_Literature_ID_(PCLID)"),
        recordValue(record, "PMID"),
        recordValue(record, "DOI"),
        index.toString
      )
      val title = recordValue(record, "Title")
      val payload = rowPayload(record)
      LuceneSourceDocument(
        docId = buildDocId("literature", path.getFileName.toString, rowId),
        docType = "literature",
        sourceFile = path.getFileName.toString,
        sourceRowId = rowId,
        title = title,
        textFields = compactTextFields(
          "title" -> title,
          "abstract" -> recordValue(record, "Abstract"),
          "keywords" -> recordValue(record, "Keywords"),
          "citation" -> recordValue(record, "Citation"),
          "publication_name" -> recordValue(record, "Publication_Name"),
          "subject" -> recordValue(record, "Subject")
        ),
        exactFields = compactExactFields(
          "pclid" -> Seq(recordValue(record, "PubChem_Literature_ID_(PCLID)")),
          "pmid" -> (splitPipeValues(recordValue(
            record,
            "PMID"
          )) ++ splitPipeValues(recordValue(record, "PMID_(All)"))),
          "doi" -> (splitPipeValues(recordValue(record, "DOI")) ++ splitPipeValues(recordValue(record, "DOI_(All)"))),
          "publication_date" -> Seq(recordValue(record, "Publication_Date")),
          "publication_type" -> Seq(recordValue(record, "Publication_Type")),
          "pubchem_data_source" -> Seq(recordValue(record, "PubChem_Data_Source")),
          "pubchem_cid" -> splitPipeValues(recordValue(record, "PubChem_CID")),
          "pubchem_sid" -> splitPipeValues(recordValue(record, "PubChem_SID")),
          "pubchem_aid" -> splitPipeValues(recordValue(record, "PubChem_AID")),
          "pubchem_gene" -> splitPipeValues(recordValue(record, "PubChem_Gene")),
          "pubchem_taxonomy" -> splitPipeValues(recordValue(record, "PubChem_Taxonomy")),
          "pubchem_pathway" -> splitPipeValues(recordValue(record, "PubChem_Pathway"))
        ),
        intFields = compactIntFields(
          "publication_year" -> parseYear(recordValue(record, "Publication_Date"))
        ),
        floatFields = Map.empty,
        rawPayload = payload
      )
    }

  def loadPatentDocuments(path: Path): Iterator[LuceneSourceDocument] =
    iterateCsv(path).zipWithIndex.map { case (record, index) =>
      val rowId = firstNonEmpty(recordValue(record, "gpid"), recordValue(record, "publicationnumber"), index.toString)
      val title = recordValue(record, "title")
      LuceneSourceDocument(
        docId = buildDocId("patent", path.getFileName.toString, rowId),
        docType = "patent",
        sourceFile = path.getFileName.toString,
        sourceRowId = rowId,
        title = title,
        textFields = compactTextFields(
          "title" -> title,
          "abstract" -> recordValue(record, "abstract"),
          "inventors" -> recordValue(record, "inventors"),
          "assignees" -> recordValue(record, "assignees")
        ),
        exactFields = compactExactFields(
          "publicationnumber" -> Seq(recordValue(record, "publicationnumber")),
          "prioritydate" -> Seq(recordValue(record, "prioritydate")),
          "grantdate" -> Seq(recordValue(record, "grantdate")),
          "cid" -> splitPipeValues(recordValue(record, "cids")),
          "sid" -> splitPipeValues(recordValue(record, "sids")),
          "aid" -> splitPipeValues(recordValue(record, "aids")),
          "gene_id" -> splitPipeValues(recordValue(record, "geneids")),
          "protein_accession" -> splitPipeValues(recordValue(record, "protacxns")),
          "taxonomy_id" -> splitPipeValues(recordValue(record, "taxids"))
        ),
        intFields = compactIntFields(
          "priority_year" -> parseYear(recordValue(record, "prioritydate")),
          "grant_year" -> parseYear(recordValue(record, "grantdate"))
        ),
        floatFields = Map.empty,
        rawPayload = rowPayload(record)
      )
    }

  def loadBioactivityDocuments(path: Path): Iterator[LuceneSourceDocument] =
    iterateCsv(path).zipWithIndex.map { case (record, index) =>
      val rowId =
        firstNonEmpty(recordValue(record, "Bioactivity_ID"), recordValue(record, "BioAssay_AID"), index.toString)
      val title = recordValue(record, "BioAssay_Name")
      LuceneSourceDocument(
        docId = buildDocId("bioactivity", path.getFileName.toString, rowId),
        docType = "bioactivity",
        sourceFile = path.getFileName.toString,
        sourceRowId = rowId,
        title = title,
        textFields = compactTextFields(
          "title" -> title,
          "bioassay_name" -> title,
          "target_name" -> recordValue(record, "Target_Name"),
          "activity" -> recordValue(record, "Activity"),
          "activity_type" -> recordValue(record, "Activity_Type"),
          "bioassay_data_source" -> recordValue(record, "Bioassay_Data_Source"),
          "citation" -> recordValue(record, "citations")
        ),
        exactFields = compactExactFields(
          "bioactivity_id" -> Seq(recordValue(record, "Bioactivity_ID")),
          "bioassay_aid" -> Seq(recordValue(record, "BioAssay_AID")),
          "compound_cid" -> Seq(recordValue(record, "Compound_CID")),
          "substance_sid" -> Seq(recordValue(record, "Substance_SID")),
          "protein_accession" -> Seq(recordValue(record, "Protein_Accession")),
          "gene_id" -> Seq(recordValue(record, "Gene_ID")),
          "taxonomy_id" -> Seq(recordValue(record, "Taxonomy_ID")),
          "target_taxonomy_id" -> Seq(recordValue(record, "Target_Taxonomy_ID")),
          "aid_type" -> Seq(recordValue(record, "Aid_Type")),
          "activity_label" -> Seq(recordValue(record, "Activity")),
          "pmid" -> Seq(recordValue(record, "PMID"))
        ),
        intFields = compactIntFields(
          "has_dose_response_curve" -> parseBinaryFlag(recordValue(record, "Has_Dose_Response_Curve")),
          "rnai_bioassay" -> parseBinaryFlag(recordValue(record, "RNAi_BioAssay"))
        ),
        floatFields = compactFloatFields(
          "activity_value" -> parseFloat(recordValue(record, "Activity_Value"))
        ),
        rawPayload = rowPayload(record)
      )
    }

  def loadTaxonomyDocuments(path: Path): Iterator[LuceneSourceDocument] =
    iterateCsv(path).zipWithIndex.map { case (record, index) =>
      val rowId =
        firstNonEmpty(recordValue(record, "Source_Organism_ID"), recordValue(record, "Taxonomy_ID"), index.toString)
      val title = recordValue(record, "Source_Organism")
      LuceneSourceDocument(
        docId = buildDocId("taxonomy", path.getFileName.toString, rowId),
        docType = "taxonomy",
        sourceFile = path.getFileName.toString,
        sourceRowId = rowId,
        title = title,
        textFields = compactTextFields(
          "title" -> title,
          "source_organism" -> title,
          "taxonomy_name" -> recordValue(record, "Taxonomy"),
          "source" -> recordValue(record, "Source"),
          "compound" -> recordValue(record, "Compound")
        ),
        exactFields = compactExactFields(
          "compound_cid" -> Seq(recordValue(record, "Compound_CID")),
          "taxonomy_id" -> Seq(recordValue(record, "Taxonomy_ID")),
          "source_chemical_id" -> Seq(recordValue(record, "Source_Chemical_ID")),
          "source_id" -> Seq(recordValue(record, "Source_ID")),
          "source_organism_id" -> Seq(recordValue(record, "Source_Organism_ID")),
          "data_source" -> Seq(recordValue(record, "Data_Source"))
        ),
        intFields = Map.empty,
        floatFields = Map.empty,
        rawPayload = rowPayload(record)
      )
    }

  def loadPathwayDocuments(path: Path): Iterator[LuceneSourceDocument] =
    iterateCsv(path).zipWithIndex.map { case (record, index) =>
      val rowId =
        firstNonEmpty(recordValue(record, "Pathway_Accession"), recordValue(record, "pathwayid"), index.toString)
      val title = recordValue(record, "Pathway_Name")
      LuceneSourceDocument(
        docId = buildDocId("pathway", path.getFileName.toString, rowId),
        docType = "pathway",
        sourceFile = path.getFileName.toString,
        sourceRowId = rowId,
        title = title,
        textFields = compactTextFields(
          "title" -> title,
          "pathway_name" -> title,
          "pathway_type" -> recordValue(record, "Pathway_Type"),
          "pathway_category" -> recordValue(record, "Pathway_Category"),
          "taxonomy_name" -> recordValue(record, "Taxonomy_Name"),
          "citation" -> recordValue(record, "citations")
        ),
        exactFields = compactExactFields(
          "pathway_accession" -> Seq(recordValue(record, "Pathway_Accession")),
          "source_id" -> Seq(recordValue(record, "Source_ID")),
          "compound_cid" -> splitPipeValues(recordValue(record, "Linked_Compounds")),
          "pubchem_gene" -> splitPipeValues(recordValue(record, "Linked_Genes")),
          "pubchem_protein" -> splitPipeValues(recordValue(record, "Linked_Proteins")),
          "taxonomy_id" -> Seq(recordValue(record, "Taxonomy_ID")),
          "pubchem_enzyme" -> splitPipeValues(recordValue(record, "Linked_ECs")),
          "data_source" -> Seq(recordValue(record, "Data_Source"))
        ),
        intFields = Map.empty,
        floatFields = Map.empty,
        rawPayload = rowPayload(record)
      )
    }

  def loadPathwayReactionDocuments(path: Path): Iterator[LuceneSourceDocument] =
    iterateCsv(path).zipWithIndex.map { case (record, index) =>
      val rowId =
        firstNonEmpty(recordValue(record, "Source_Pathway"), recordValue(record, "PubChem_Pathway"), index.toString)
      val title = firstNonEmpty(
        recordValue(record, "Source_Pathway"),
        recordValue(record, "Equation"),
        recordValue(record, "Reaction")
      )
      LuceneSourceDocument(
        docId = buildDocId("pathway_reaction", path.getFileName.toString, rowId),
        docType = "pathway_reaction",
        sourceFile = path.getFileName.toString,
        sourceRowId = rowId,
        title = title,
        textFields = compactTextFields(
          "title" -> title,
          "equation" -> recordValue(record, "Equation"),
          "reaction" -> recordValue(record, "Reaction"),
          "control" -> recordValue(record, "Control"),
          "taxonomy_name" -> recordValue(record, "Taxonomy")
        ),
        exactFields = compactExactFields(
          "pathway_accession" -> Seq(recordValue(record, "PubChem_Pathway")),
          "source_id" -> Seq(recordValue(record, "id")),
          "compound_cid" -> Seq(recordValue(record, "Compound_CID")),
          "pubchem_protein" -> splitPipeValues(recordValue(record, "PubChem_Protein")),
          "pubchem_gene" -> splitPipeValues(recordValue(record, "PubChem_Gene")),
          "taxonomy_id" -> Seq(recordValue(record, "Taxonomy_ID")),
          "pubchem_enzyme" -> splitPipeValues(recordValue(record, "PubChem_Enzyme")),
          "source_uri" -> Seq(recordValue(record, "Source")),
          "evidence_pmid" -> Seq(recordValue(record, "Evidence_PMID"))
        ),
        intFields = Map.empty,
        floatFields = Map.empty,
        rawPayload = rowPayload(record)
      )
    }

  def loadCpdatDocuments(path: Path): Iterator[LuceneSourceDocument] =
    iterateCsv(path).zipWithIndex.map { case (record, index) =>
      val rowId = firstNonEmpty(recordValue(record, "gid"), recordValue(record, "CID"), index.toString)
      val title = firstNonEmpty(recordValue(record, "Category"), recordValue(record, "cmpdname"), s"cpdat_$index")
      LuceneSourceDocument(
        docId = buildDocId("cpdat", path.getFileName.toString, rowId),
        docType = "cpdat",
        sourceFile = path.getFileName.toString,
        sourceRowId = rowId,
        title = title,
        textFields = compactTextFields(
          "title" -> title,
          "category" -> recordValue(record, "Category"),
          "category_description" -> recordValue(record, "Category_Description"),
          "compound_name" -> recordValue(record, "cmpdname")
        ),
        exactFields = compactExactFields(
          "gid" -> Seq(recordValue(record, "gid")),
          "cid" -> Seq(recordValue(record, "CID")),
          "categorization_type" -> Seq(recordValue(record, "Categorization_Type"))
        ),
        intFields = Map.empty,
        floatFields = Map.empty,
        rawPayload = rowPayload(record)
      )
    }

  def loadCuratedCitationDocuments(path: Path): Iterator[LuceneSourceDocument] =
    val root = jsonMapper.readTree(Files.readString(path))
    val literature = root.path("Literature")
    val recordNumber = textValue(literature.path("RecordNumber"))
    val recordType = textValue(literature.path("RecordType"))
    val allUrl = textValue(literature.path("AllURL"))
    Iterator.single(
      LuceneSourceDocument(
        docId = buildDocId("curated_citation", path.getFileName.toString, firstNonEmpty(recordNumber, "cid4")),
        docType = "curated_citation",
        sourceFile = path.getFileName.toString,
        sourceRowId = firstNonEmpty(recordNumber, "cid4"),
        title = "CID 4 curated citation anchor",
        textFields = compactTextFields(
          "title" -> "CID 4 curated citation anchor",
          "citation_anchor" -> allUrl,
          "record_type" -> recordType
        ),
        exactFields = compactExactFields(
          "record_number" -> Seq(recordNumber),
          "record_type" -> Seq(recordType)
        ),
        intFields = Map.empty,
        floatFields = Map.empty,
        rawPayload = root.toPrettyString
      )
    )

  def loadCompoundRecordDocuments(path: Path): Iterator[LuceneSourceDocument] =
    val root = jsonMapper.readTree(Files.readString(path))
    val record = root.path("Record")
    val compoundTitle = textValue(record.path("RecordTitle"))
    val cid = textValue(record.path("RecordNumber"))
    val sections = record.path("Section")
    flattenSections(sections, Vector.empty, compoundTitle, cid, path.getFileName.toString).iterator

  private def flattenSections(
      sections: JsonNode,
      parentPath: Vector[String],
      compoundTitle: String,
      cid: String,
      sourceFile: String
  ): Seq[LuceneSourceDocument] =
    if !sections.isArray then Seq.empty
    else
      sections.iterator().asScala.toSeq.zipWithIndex.flatMap { case (section, index) =>
        val heading = textValue(section.path("TOCHeading"))
        val sectionKey = if heading.nonEmpty then heading else s"section_$index"
        val sectionPath = parentPath :+ sectionKey
        val sectionText = collectSectionText(section)
        val currentDocument =
          if heading.nonEmpty || sectionText.nonEmpty then
            Seq(
              LuceneSourceDocument(
                docId = buildDocId("compound_record", sourceFile, sectionPath.mkString(" > ")),
                docType = "compound_record",
                sourceFile = sourceFile,
                sourceRowId = sectionPath.mkString(" > "),
                title = s"$compoundTitle - ${sectionPath.last}",
                textFields = compactTextFields(
                  "title" -> s"$compoundTitle - ${sectionPath.last}",
                  "compound_heading" -> sectionPath.mkString(" > "),
                  "compound_text" -> sectionText
                ),
                exactFields = compactExactFields(
                  "cid" -> Seq(cid),
                  "section_path" -> Seq(sectionPath.mkString(" > "))
                ),
                intFields = Map.empty,
                floatFields = Map.empty,
                rawPayload = section.toPrettyString
              )
            )
          else Seq.empty
        currentDocument ++ flattenSections(section.path("Section"), sectionPath, compoundTitle, cid, sourceFile)
      }

  private def collectSectionText(section: JsonNode): String =
    val infoText =
      if section.path("Information").isArray then
        section.path("Information").iterator().asScala.toSeq.flatMap(extractStrings)
      else Seq.empty
    infoText.map(_.trim).filter(_.nonEmpty).distinct.mkString("\n\n")

  private def extractStrings(node: JsonNode): Seq[String] =
    val directKeys = Seq("StringValue", "String", "Value", "Name", "Description")
    val directValues = directKeys.map(key => textValue(node.path(key))).filter(_.nonEmpty)
    val nestedValues =
      if node.isArray then node.iterator().asScala.toSeq.flatMap(extractStrings)
      else if node.isObject then node.iterator().asScala.toSeq.flatMap(extractStrings)
      else Seq.empty
    (directValues ++ nestedValues).distinct

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

  private def rowPayload(record: CSVRecord): String =
    jsonMapper.writeValueAsString(record.toMap.asScala.toMap)

  private def recordValue(record: CSVRecord, field: String): String =
    Try(Option(record.get(field)).getOrElse("").trim).getOrElse("")

  private def compactTextFields(entries: (String, String)*): Map[String, String] =
    entries.collect { case (key, value) if value.trim.nonEmpty => key -> value.trim }.toMap

  private def compactExactFields(entries: (String, Seq[String])*): Map[String, Seq[String]] =
    entries
      .map { case (key, values) =>
        key -> values.map(normalizeExactValue).filter(_.nonEmpty).distinct
      }
      .collect { case (key, values) if values.nonEmpty => key -> values }
      .toMap

  private def compactIntFields(entries: (String, Option[Int])*): Map[String, Int] =
    entries.collect { case (key, Some(value)) => key -> value }.toMap

  private def compactFloatFields(entries: (String, Option[Float])*): Map[String, Float] =
    entries.collect { case (key, Some(value)) => key -> value }.toMap

  private def splitPipeValues(raw: String): Seq[String] =
    val builder = Vector.newBuilder[String]
    val current = new StringBuilder()

    raw.foreach { character =>
      if character == '|' || character == ',' then
        val token = current.result().trim
        if token.nonEmpty then builder += token
        current.clear()
      else current.append(character)
    }

    val finalToken = current.result().trim
    if finalToken.nonEmpty then builder += finalToken
    builder.result()

  private def parseYear(raw: String): Option[Int] =
    """(19|20)\d{2}""".r.findFirstIn(raw).flatMap(value => Try(value.toInt).toOption)

  private def parseBinaryFlag(raw: String): Option[Int] =
    raw.trim.toLowerCase match
      case "1" | "true" | "yes" | "y" => Some(1)
      case "0" | "false" | "no" | "n" => Some(0)
      case _                          => None

  private def parseFloat(raw: String): Option[Float] =
    Try(raw.trim.toFloat).toOption

  private def buildDocId(docType: String, sourceFile: String, rowId: String): String =
    s"$docType::$sourceFile::${rowId.trim}"

  private def firstNonEmpty(values: String*): String =
    values.iterator.map(_.trim).find(_.nonEmpty).getOrElse("")

  private def normalizeExactValue(value: String): String = value.trim.toLowerCase

  private def textValue(node: JsonNode): String =
    if node == null || node.isMissingNode || node.isNull then ""
    else node.asText("").trim
