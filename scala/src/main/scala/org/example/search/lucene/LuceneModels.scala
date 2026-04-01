package org.example.search.lucene

final case class LuceneSourceDocument(
    docId: String,
    docType: String,
    sourceFile: String,
    sourceRowId: String,
    title: String,
    textFields: Map[String, String],
    exactFields: Map[String, Seq[String]],
    intFields: Map[String, Int],
    floatFields: Map[String, Float],
    rawPayload: String
)

final case class LuceneIndexBuildSummary(
    indexPath: String,
    documentCount: Int,
    countsByDocType: Map[String, Int],
    sourceFiles: Seq[String]
)

final case class LuceneDocumentBatch(
    sourceFile: String,
    loader: () => Iterator[LuceneSourceDocument]
)

final case class LuceneSearchHit(
    docId: String,
    docType: String,
    title: String,
    sourceFile: String,
    sourceRowId: String,
    score: Float,
    snippet: String,
    exactFields: Map[String, Seq[String]]
)

final case class LuceneQueryExampleResult(
    name: String,
    description: String,
    totalHits: Long,
    hits: Seq[LuceneSearchHit]
)

final case class LuceneQueryRunSummary(
    indexPath: String,
    examples: Seq[LuceneQueryExampleResult]
)
