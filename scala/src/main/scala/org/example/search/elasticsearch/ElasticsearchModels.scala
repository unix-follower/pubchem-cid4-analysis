package org.example.search.elasticsearch

final case class ElasticsearchExportSummary(
    indexName: String,
    bulkPath: String,
    configDirectory: String,
    documentCount: Int,
    countsByDocType: Map[String, Int],
    sourceFiles: Seq[String]
)

final case class ElasticsearchRuntimeSummary(
    mode: String,
    elasticsearchUrl: Option[String],
    indexName: String,
    available: Boolean,
    status: String,
    message: String
)

final case class ElasticsearchIngestSummary(
    status: String,
    indexName: String,
    postedDocumentCount: Int,
    batchSize: Int
)

final case class ElasticsearchAggregationBucket(
    value: String,
    count: Long
)

final case class ElasticsearchQueryHit(
    id: String,
    docType: String,
    title: String,
    sourceFile: String,
    rowId: String,
    score: Float,
    snippet: String,
    exactFields: Map[String, Seq[String]]
)

final case class ElasticsearchQueryExampleResult(
    name: String,
    description: String,
    status: String,
    query: String,
    filters: Map[String, Seq[String]],
    totalHits: Long,
    aggregations: Map[String, Seq[ElasticsearchAggregationBucket]],
    hits: Seq[ElasticsearchQueryHit]
)

final case class ElasticsearchRunSummary(
    exportSummary: Option[ElasticsearchExportSummary],
    runtime: ElasticsearchRuntimeSummary,
    ingest: Option[ElasticsearchIngestSummary],
    queryExamples: Seq[ElasticsearchQueryExampleResult]
)
