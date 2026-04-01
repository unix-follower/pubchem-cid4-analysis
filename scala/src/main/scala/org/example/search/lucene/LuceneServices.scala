package org.example.search.lucene

import org.apache.lucene.analysis.Analyzer
import org.apache.lucene.analysis.LowerCaseFilter
import org.apache.lucene.analysis.Tokenizer
import org.apache.lucene.analysis.core.KeywordAnalyzer
import org.apache.lucene.analysis.core.KeywordTokenizer
import org.apache.lucene.analysis.miscellaneous.PerFieldAnalyzerWrapper
import org.apache.lucene.analysis.standard.StandardAnalyzer
import org.apache.lucene.document.Document
import org.apache.lucene.document.Field
import org.apache.lucene.document.FloatPoint
import org.apache.lucene.document.IntPoint
import org.apache.lucene.document.StoredField
import org.apache.lucene.document.StringField
import org.apache.lucene.document.TextField
import org.apache.lucene.index.DirectoryReader
import org.apache.lucene.index.IndexWriter
import org.apache.lucene.index.IndexWriterConfig
import org.apache.lucene.index.Term
import org.apache.lucene.queryparser.classic.MultiFieldQueryParser
import org.apache.lucene.search.BooleanClause.Occur
import org.apache.lucene.search.BooleanQuery
import org.apache.lucene.search.IndexSearcher
import org.apache.lucene.search.Query
import org.apache.lucene.search.ScoreDoc
import org.apache.lucene.search.TermQuery
import org.apache.lucene.store.FSDirectory
import org.slf4j.LoggerFactory

import java.nio.file.Files
import java.nio.file.Path
import scala.jdk.CollectionConverters.*

object LuceneIndexService:
  private val logger = LoggerFactory.getLogger(getClass)

  def buildIndex(indexPath: Path, batches: Seq[LuceneDocumentBatch]): LuceneIndexBuildSummary =
    Files.createDirectories(indexPath)
    val directory = FSDirectory.open(indexPath)
    val writerConfig = new IndexWriterConfig(buildAnalyzer())
    writerConfig.setOpenMode(IndexWriterConfig.OpenMode.CREATE)

    val writer = new IndexWriter(directory, writerConfig)
    var totalDocuments = 0
    val countsByDocType = scala.collection.mutable.Map.empty[String, Int].withDefaultValue(0)
    val sourceFiles = scala.collection.mutable.LinkedHashSet.empty[String]
    try
      batches.foreach { batch =>
        val documents = batch.loader()
        sourceFiles += batch.sourceFile
        documents.foreach { document =>
          writer.addDocument(toLuceneDocument(document))
          totalDocuments += 1
          countsByDocType.update(document.docType, countsByDocType(document.docType) + 1)
        }
        logger.info(s"Finished indexing ${batch.sourceFile}")
      }
      writer.commit()
    finally
      writer.close()
      directory.close()

    val summary = LuceneIndexBuildSummary(
      indexPath = indexPath.toAbsolutePath.toString,
      documentCount = totalDocuments,
      countsByDocType = countsByDocType.toSeq.sortBy(_._1).toMap,
      sourceFiles = sourceFiles.toSeq
    )
    logger.info(s"Built Lucene index with ${summary.documentCount} document(s) at ${summary.indexPath}")
    summary

  def buildAnalyzer(): Analyzer =
    val perField = Map[String, Analyzer](
      "doc_type" -> lowerCaseKeywordAnalyzer,
      "aid_type" -> lowerCaseKeywordAnalyzer,
      "activity_label" -> lowerCaseKeywordAnalyzer,
      "publication_type" -> lowerCaseKeywordAnalyzer,
      "pubchem_data_source" -> lowerCaseKeywordAnalyzer,
      "pathway_accession" -> lowerCaseKeywordAnalyzer,
      "pmid" -> new KeywordAnalyzer(),
      "doi" -> lowerCaseKeywordAnalyzer,
      "publicationnumber" -> lowerCaseKeywordAnalyzer,
      "taxonomy_id" -> new KeywordAnalyzer(),
      "bioassay_aid" -> new KeywordAnalyzer(),
      "protein_accession" -> lowerCaseKeywordAnalyzer,
      "gene_id" -> new KeywordAnalyzer(),
      "source_id" -> lowerCaseKeywordAnalyzer
    )
    new PerFieldAnalyzerWrapper(new StandardAnalyzer(), perField.asJava)

  private def lowerCaseKeywordAnalyzer: Analyzer = new Analyzer:
    override protected def createComponents(fieldName: String): Analyzer.TokenStreamComponents =
      val tokenizer: Tokenizer = new KeywordTokenizer()
      val tokenStream = new LowerCaseFilter(tokenizer)
      new Analyzer.TokenStreamComponents(tokenizer, tokenStream)

  private def toLuceneDocument(document: LuceneSourceDocument): Document =
    val luceneDocument = new Document()
    luceneDocument.add(new StringField("doc_id", document.docId, Field.Store.YES))
    luceneDocument.add(new StringField("doc_type", document.docType, Field.Store.YES))
    luceneDocument.add(new StringField("source_file", document.sourceFile, Field.Store.YES))
    luceneDocument.add(new StringField("source_row_id", document.sourceRowId, Field.Store.YES))
    if document.title.nonEmpty then
      luceneDocument.add(new TextField("title", document.title, Field.Store.YES))

    document.textFields.foreach { case (fieldName, value) =>
      if value.nonEmpty then luceneDocument.add(new TextField(fieldName, value, Field.Store.YES))
    }

    document.exactFields.foreach { case (fieldName, values) =>
      values.foreach { value =>
        luceneDocument.add(new StringField(fieldName, value, Field.Store.YES))
      }
    }

    document.intFields.foreach { case (fieldName, value) =>
      luceneDocument.add(new IntPoint(fieldName, value))
      luceneDocument.add(new StoredField(fieldName, value))
    }

    document.floatFields.foreach { case (fieldName, value) =>
      luceneDocument.add(new FloatPoint(fieldName, value))
      luceneDocument.add(new StoredField(fieldName, value))
    }

    luceneDocument.add(new StoredField("raw_payload", document.rawPayload))
    luceneDocument

object LuceneQueryService:
  private val logger = LoggerFactory.getLogger(getClass)
  private val snippetFields = Seq(
    "abstract",
    "citation",
    "bioassay_name",
    "target_name",
    "reaction",
    "equation",
    "taxonomy_name",
    "compound_text",
    "title"
  )

  def runExampleQueries(indexPath: Path): LuceneQueryRunSummary =
    val directory = FSDirectory.open(indexPath)
    val reader = DirectoryReader.open(directory)
    val searcher = new IndexSearcher(reader)
    val analyzer = LuceneIndexService.buildAnalyzer()

    try
      val examples = Seq(
        runExample(
          searcher,
          "literature_isopropanolamine_fungicide",
          "Find literature about isopropanolamine and fungicide",
          buildTextQuery(
            analyzer,
            "literature",
            Array("title", "abstract", "keywords", "citation", "publication_name", "subject"),
            "isopropanolamine AND fungicide"
          )
        ),
        runExample(
          searcher,
          "literature_pmid_40581877",
          "Find literature linked to PMID 40581877",
          exactDocTypeQuery("literature", "pmid", "40581877")
        ),
        runExample(
          searcher,
          "patent_electronic_grade_after_2020",
          "Find patents about electronic grade isopropanolamine filed after 2020",
          patentDateThresholdQuery(analyzer)
        ),
        runExample(
          searcher,
          "bioactivity_confirmatory_under_100",
          "Find confirmatory bioactivity records mentioning estrogen receptor or Plasmodium falciparum with Activity_Value <= 100",
          bioactivityThresholdQuery(analyzer)
        ),
        runExample(
          searcher,
          "pathway_accession_smp0002032",
          "Exact lookup by PathBank accession SMP0002032",
          exactDocTypeQuery("pathway", "pathway_accession", "pathbank:smp0002032")
        )
      )
      LuceneQueryRunSummary(indexPath.toAbsolutePath.toString, examples)
    finally
      reader.close()
      directory.close()
      analyzer.close()

  private def runExample(
      searcher: IndexSearcher,
      name: String,
      description: String,
      query: Query
  ): LuceneQueryExampleResult =
    val topDocs = searcher.search(query, 5)
    val hits = topDocs.scoreDocs.toSeq.map(scoreDoc => toSearchHit(searcher, scoreDoc))
    logger.info(s"Lucene example '$name' produced ${topDocs.totalHits.value} hit(s)")
    LuceneQueryExampleResult(name, description, topDocs.totalHits.value, hits)

  private def toSearchHit(searcher: IndexSearcher, scoreDoc: ScoreDoc): LuceneSearchHit =
    val document = searcher.storedFields().document(scoreDoc.doc)
    val exactFieldNames = Seq(
      "pmid",
      "doi",
      "publicationnumber",
      "aid_type",
      "bioassay_aid",
      "taxonomy_id",
      "pathway_accession",
      "publication_date",
      "prioritydate",
      "grantdate"
    )
    LuceneSearchHit(
      docId = document.get("doc_id"),
      docType = document.get("doc_type"),
      title = Option(document.get("title")).getOrElse(""),
      sourceFile = Option(document.get("source_file")).getOrElse(""),
      sourceRowId = Option(document.get("source_row_id")).getOrElse(""),
      score = scoreDoc.score,
      snippet = buildSnippet(document),
      exactFields = exactFieldNames.flatMap { fieldName =>
        val values = document.getValues(fieldName).toSeq.filter(_.nonEmpty)
        if values.nonEmpty then Some(fieldName -> values) else None
      }.toMap
    )

  private def buildSnippet(document: Document): String =
    snippetFields
      .iterator
      .map(fieldName => Option(document.get(fieldName)).getOrElse(""))
      .map(_.trim)
      .find(_.nonEmpty)
      .map(value => if value.length <= 240 then value else s"${value.take(237)}...")
      .getOrElse("")

  private def buildTextQuery(
      analyzer: Analyzer,
      docType: String,
      fields: Array[String],
      rawQuery: String
  ): Query =
    val parser = new MultiFieldQueryParser(fields, analyzer)
    val parsed = parser.parse(rawQuery)
    new BooleanQuery.Builder()
      .add(new TermQuery(new Term("doc_type", docType.toLowerCase)), Occur.FILTER)
      .add(parsed, Occur.MUST)
      .build()

  private def exactDocTypeQuery(docType: String, fieldName: String, value: String): Query =
    new BooleanQuery.Builder()
      .add(new TermQuery(new Term("doc_type", docType.toLowerCase)), Occur.FILTER)
      .add(new TermQuery(new Term(fieldName, value.toLowerCase)), Occur.MUST)
      .build()

  private def patentDateThresholdQuery(analyzer: Analyzer): Query =
    new BooleanQuery.Builder()
      .add(new TermQuery(new Term("doc_type", "patent")), Occur.FILTER)
      .add(IntPoint.newRangeQuery("priority_year", 2020, Int.MaxValue), Occur.FILTER)
      .add(
        new MultiFieldQueryParser(Array("title", "abstract", "inventors", "assignees"), analyzer)
          .parse("\"electronic grade\" AND isopropanolamine"),
        Occur.MUST
      )
      .build()

  private def bioactivityThresholdQuery(analyzer: Analyzer): Query =
    new BooleanQuery.Builder()
      .add(new TermQuery(new Term("doc_type", "bioactivity")), Occur.FILTER)
      .add(new TermQuery(new Term("aid_type", "confirmatory")), Occur.FILTER)
      .add(FloatPoint.newRangeQuery("activity_value", Float.MinValue, 100.0f), Occur.FILTER)
      .add(
        new MultiFieldQueryParser(Array("bioassay_name", "target_name"), analyzer)
          .parse("\"estrogen receptor\" OR \"plasmodium falciparum\""),
        Occur.MUST
      )
      .build()
