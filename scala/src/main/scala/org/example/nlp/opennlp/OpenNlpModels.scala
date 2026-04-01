package org.example.nlp.opennlp

import java.nio.file.Path

final case class OpenNlpTextDocument(
    docId: String,
    workflow: String,
    title: String,
    text: String,
    metadata: Map[String, String],
    label: Option[String]
)

final case class OpenNlpWorkflowSpec(
    name: String,
    description: String,
    sourceFiles: Seq[String],
    labelName: Option[String],
    loader: () => Iterator[OpenNlpTextDocument]
)

final case class OpenNlpComponentStatus(
    name: String,
    available: Boolean,
    strategy: String,
    detail: String,
    modelPath: Option[String]
)

final case class OpenNlpRuntimeSummary(
    mode: String,
    modelDirectory: Option[String],
    sentenceDetector: OpenNlpComponentStatus,
    tokenizer: OpenNlpComponentStatus,
    posTagger: OpenNlpComponentStatus,
    chunker: OpenNlpComponentStatus
)

final case class OpenNlpFrequency(term: String, count: Int)

final case class OpenNlpPrediction(
    docId: String,
    title: String,
    expectedLabel: Option[String],
    predictedLabel: String,
    score: Double
)

final case class OpenNlpCategorizationSummary(
    status: String,
    labelName: String,
    labelCounts: Map[String, Int],
    trainingDocumentCount: Int,
    evaluationDocumentCount: Int,
    accuracy: Option[Double],
    samplePredictions: Seq[OpenNlpPrediction],
    message: String
)

final case class OpenNlpSampleDocument(
    docId: String,
    title: String,
    sentenceCount: Int,
    tokenCount: Int,
    nounPhrases: Seq[String],
    label: Option[String]
)

final case class OpenNlpWorkflowSummary(
    name: String,
    description: String,
    sourceFiles: Seq[String],
    documentCount: Int,
    nonEmptyTextCount: Int,
    totalSentenceCount: Int,
    totalTokenCount: Int,
    averageSentencesPerDocument: Double,
    averageTokensPerDocument: Double,
    topTokens: Seq[OpenNlpFrequency],
    topBigrams: Seq[OpenNlpFrequency],
    topTrigrams: Seq[OpenNlpFrequency],
    topNounPhrases: Seq[OpenNlpFrequency],
    categorization: Option[OpenNlpCategorizationSummary],
    sampleDocuments: Seq[OpenNlpSampleDocument],
    runtimeMode: String,
    outputPath: String
)

final case class OpenNlpRunSummary(
    runtime: OpenNlpRuntimeSummary,
    generatedAtPath: Path,
    workflowOutputs: Map[String, String]
)
