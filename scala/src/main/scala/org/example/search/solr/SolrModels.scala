package org.example.search.solr

final case class SolrExportSummary(
    collection: String,
    docsPath: String,
    configsetPath: String,
    documentCount: Int,
    countsByDocType: Map[String, Int],
    sourceFiles: Seq[String]
)

final case class SolrRuntimeSummary(
    mode: String,
    solrUrl: Option[String],
    collection: String,
    available: Boolean,
    status: String,
    message: String
)

final case class SolrIngestSummary(
    status: String,
    collection: String,
    postedDocumentCount: Int,
    batchSize: Int
)

final case class SolrFacetBucket(
    value: String,
    count: Long
)

final case class SolrQueryHit(
    id: String,
    docType: String,
    title: String,
    sourceFile: String,
    rowId: String,
    score: Float,
    snippet: String,
    exactFields: Map[String, Seq[String]]
)

final case class SolrQueryExampleResult(
    name: String,
    description: String,
    status: String,
    query: String,
    filterQueries: Seq[String],
    totalHits: Long,
    facets: Map[String, Seq[SolrFacetBucket]],
    hits: Seq[SolrQueryHit]
)

final case class SolrRunSummary(
    exportSummary: Option[SolrExportSummary],
    runtime: SolrRuntimeSummary,
    ingest: Option[SolrIngestSummary],
    queryExamples: Seq[SolrQueryExampleResult]
)
