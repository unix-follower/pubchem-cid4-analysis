package org.example.nlp.opennlp

import opennlp.tools.chunker.ChunkerME
import opennlp.tools.chunker.ChunkerModel
import opennlp.tools.doccat.DoccatFactory
import opennlp.tools.doccat.DocumentCategorizerME
import opennlp.tools.doccat.DocumentSample
import opennlp.tools.postag.POSModel
import opennlp.tools.postag.POSTaggerME
import opennlp.tools.sentdetect.SentenceDetectorME
import opennlp.tools.sentdetect.SentenceModel
import opennlp.tools.tokenize.SimpleTokenizer
import opennlp.tools.tokenize.Tokenizer
import opennlp.tools.tokenize.TokenizerME
import opennlp.tools.tokenize.TokenizerModel
import opennlp.tools.util.CollectionObjectStream
import opennlp.tools.util.TrainingParameters
import org.slf4j.LoggerFactory

import java.io.InputStream
import java.nio.file.Files
import java.nio.file.Path
import scala.collection.mutable
import scala.jdk.CollectionConverters.*
import scala.util.Try

object OpenNlpService:
  private val logger = LoggerFactory.getLogger(getClass)
  private val simpleTokenizer = SimpleTokenizer.INSTANCE
  private val sentenceSplitRegex = "(?<=[.!?])\\s+".r
  private val tokenPattern = "(?i)[a-z0-9]+(?:[-'][a-z0-9]+)*".r
  private val stopwords = Set(
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "in",
    "into",
    "is",
    "of",
    "on",
    "or",
    "that",
    "the",
    "their",
    "this",
    "to",
    "with",
    "using",
    "used"
  )
  private val preserveTokens =
    Set("1-amino-2-propanol", "1-aminopropan-2-ol", "isopropanolamine", "nadh", "ic50", "er-alpha", "tox21")

  final case class Runtime(processor: TextProcessor, summary: OpenNlpRuntimeSummary)

  def buildRuntime(modelDirectory: Option[Path]): Runtime =
    val sentenceModel = loadModel(modelDirectory, "en-sent.bin")(in => new SentenceModel(in))
    val tokenModel = loadModel(modelDirectory, "en-token.bin")(in => new TokenizerModel(in))
    val posModel = loadModel(modelDirectory, "en-pos-maxent.bin")(in => new POSModel(in))
    val chunkerModel = loadModel(modelDirectory, "en-chunker.bin")(in => new ChunkerModel(in))

    val sentenceDetector = sentenceModel.map(new SentenceDetectorME(_))
    val tokenizer = tokenModel.map(new TokenizerME(_)).getOrElse(simpleTokenizer)
    val posTagger = posModel.map(new POSTaggerME(_))
    val chunker = chunkerModel.map(new ChunkerME(_))

    val mode =
      if sentenceDetector.nonEmpty && posTagger.nonEmpty && chunker.nonEmpty then "opennlp"
      else if sentenceDetector.nonEmpty || posTagger.nonEmpty || chunker.nonEmpty then "hybrid"
      else "heuristic"

    Runtime(
      new TextProcessor(sentenceDetector, tokenizer, posTagger, chunker),
      OpenNlpRuntimeSummary(
        mode = mode,
        modelDirectory = modelDirectory.map(_.toString),
        sentenceDetector = componentStatus(
          "sentence_detector",
          sentenceDetector.nonEmpty,
          if sentenceDetector.nonEmpty then "model" else "regex",
          if sentenceDetector.nonEmpty then "SentenceDetectorME loaded from model"
          else "Regex sentence splitting fallback",
          modelDirectory.map(_.resolve("en-sent.bin")).filter(Files.exists(_)).map(_.toString)
        ),
        tokenizer = componentStatus(
          "tokenizer",
          true,
          if tokenModel.nonEmpty then "model" else "simple",
          if tokenModel.nonEmpty then "TokenizerME loaded from model" else "SimpleTokenizer fallback",
          modelDirectory.map(_.resolve("en-token.bin")).filter(Files.exists(_)).map(_.toString)
        ),
        posTagger = componentStatus(
          "pos_tagger",
          posTagger.nonEmpty,
          if posTagger.nonEmpty then "model" else "skipped",
          if posTagger.nonEmpty then "POSTaggerME loaded from model"
          else "POS tagging unavailable without en-pos-maxent.bin",
          modelDirectory.map(_.resolve("en-pos-maxent.bin")).filter(Files.exists(_)).map(_.toString)
        ),
        chunker = componentStatus(
          "chunker",
          chunker.nonEmpty,
          if chunker.nonEmpty then "model" else "ngrams",
          if chunker.nonEmpty then "ChunkerME loaded from model" else "Noun phrase fallback uses n-grams",
          modelDirectory.map(_.resolve("en-chunker.bin")).filter(Files.exists(_)).map(_.toString)
        )
      )
    )

  def analyzeWorkflow(
      spec: OpenNlpWorkflowSpec,
      runtime: Runtime,
      outputPath: Path
  ): OpenNlpWorkflowSummary =
    val tokenCounts = mutable.Map.empty[String, Int].withDefaultValue(0)
    val bigramCounts = mutable.Map.empty[String, Int].withDefaultValue(0)
    val trigramCounts = mutable.Map.empty[String, Int].withDefaultValue(0)
    val nounPhraseCounts = mutable.Map.empty[String, Int].withDefaultValue(0)
    val sampleDocuments = mutable.ArrayBuffer.empty[OpenNlpSampleDocument]
    val labeledDocuments = mutable.ArrayBuffer.empty[CategorizationInput]
    var documentCount = 0
    var nonEmptyTextCount = 0
    var totalSentenceCount = 0
    var totalTokenCount = 0

    spec.loader().foreach { document =>
      documentCount += 1
      val text = document.text.trim
      if text.nonEmpty then
        nonEmptyTextCount += 1
        val sentences = runtime.processor.sentences(text)
        totalSentenceCount += sentences.size
        val normalizedTokens = runtime.processor.normalizedTokens(text)
        totalTokenCount += normalizedTokens.size
        incrementCounts(tokenCounts, normalizedTokens)
        incrementCounts(bigramCounts, ngrams(normalizedTokens, 2))
        incrementCounts(trigramCounts, ngrams(normalizedTokens, 3))
        val nounPhrases = runtime.processor.nounPhrases(text)
        incrementCounts(nounPhraseCounts, nounPhrases)

        if sampleDocuments.size < 3 then
          sampleDocuments += OpenNlpSampleDocument(
            docId = document.docId,
            title = document.title,
            sentenceCount = sentences.size,
            tokenCount = normalizedTokens.size,
            nounPhrases = nounPhrases.take(5),
            label = document.label
          )

        if spec.labelName.nonEmpty then
          document.label
            .map(_.trim)
            .filter(label => label.nonEmpty && normalizedTokens.nonEmpty)
            .foreach(label =>
              labeledDocuments += CategorizationInput(document.docId, document.title, label, normalizedTokens.toArray)
            )
    }

    val categorization =
      spec.labelName.map(labelName => trainCategorizer(labelName, labeledDocuments.toVector))

    OpenNlpWorkflowSummary(
      name = spec.name,
      description = spec.description,
      sourceFiles = spec.sourceFiles,
      documentCount = documentCount,
      nonEmptyTextCount = nonEmptyTextCount,
      totalSentenceCount = totalSentenceCount,
      totalTokenCount = totalTokenCount,
      averageSentencesPerDocument = average(totalSentenceCount, nonEmptyTextCount),
      averageTokensPerDocument = average(totalTokenCount, nonEmptyTextCount),
      topTokens = topFrequencies(tokenCounts),
      topBigrams = topFrequencies(bigramCounts),
      topTrigrams = topFrequencies(trigramCounts),
      topNounPhrases = topFrequencies(nounPhraseCounts),
      categorization = categorization,
      sampleDocuments = sampleDocuments.toSeq,
      runtimeMode = runtime.summary.mode,
      outputPath = outputPath.toString
    )

  private def loadModel[T](modelDirectory: Option[Path], fileName: String)(loader: InputStream => T): Option[T] =
    modelDirectory
      .map(_.resolve(fileName))
      .filter(Files.exists(_))
      .flatMap { path =>
        Try {
          val inputStream = Files.newInputStream(path)
          try loader(inputStream)
          finally inputStream.close()
        }.recover { case error =>
          logger.warn(s"Failed to load OpenNLP model from $path", error)
          null.asInstanceOf[T]
        }.toOption.filter(_ != null)
      }

  private def componentStatus(
      name: String,
      available: Boolean,
      strategy: String,
      detail: String,
      modelPath: Option[String]
  ): OpenNlpComponentStatus =
    OpenNlpComponentStatus(name, available, strategy, detail, modelPath)

  private def incrementCounts(counter: mutable.Map[String, Int], values: Seq[String]): Unit =
    values.foreach(value => counter.update(value, counter(value) + 1))

  private def ngrams(tokens: Seq[String], size: Int): Seq[String] =
    if tokens.size < size then Seq.empty
    else tokens.sliding(size).map(_.mkString(" ")).toSeq

  private def average(total: Int, count: Int): Double =
    if count == 0 then 0.0 else total.toDouble / count.toDouble

  private def topFrequencies(counter: mutable.Map[String, Int], limit: Int = 15): Seq[OpenNlpFrequency] =
    counter.toSeq
      .sortBy { case (term, count) => (-count, term) }
      .take(limit)
      .map { case (term, count) => OpenNlpFrequency(term, count) }

  private def trainCategorizer(
      labelName: String,
      documents: Vector[CategorizationInput]
  ): OpenNlpCategorizationSummary =
    val labelCounts = documents.groupMapReduce(_.label)(_ => 1)(_ + _)
    if documents.size < 8 || labelCounts.size < 2 then
      OpenNlpCategorizationSummary(
        status = "skipped",
        labelName = labelName,
        labelCounts = labelCounts,
        trainingDocumentCount = 0,
        evaluationDocumentCount = 0,
        accuracy = None,
        samplePredictions = Seq.empty,
        message = "Not enough labeled documents to train a document categorizer"
      )
    else
      val (trainingDocs, evaluationDocs) = stratifiedSplit(documents)
      if trainingDocs.isEmpty || evaluationDocs.isEmpty then
        OpenNlpCategorizationSummary(
          status = "skipped",
          labelName = labelName,
          labelCounts = labelCounts,
          trainingDocumentCount = trainingDocs.size,
          evaluationDocumentCount = evaluationDocs.size,
          accuracy = None,
          samplePredictions = Seq.empty,
          message = "Labeled documents did not support a meaningful train/evaluation split"
        )
      else
        val trainingSamples = trainingDocs.map(doc => new DocumentSample(doc.label, doc.tokens))
        val sampleStream = new CollectionObjectStream[DocumentSample](trainingSamples.asJava)
        val params = TrainingParameters.defaultParams()
        params.put(TrainingParameters.ITERATIONS_PARAM, "40")
        params.put(TrainingParameters.CUTOFF_PARAM, "0")
        val model = DocumentCategorizerME.train("en", sampleStream, params, new DoccatFactory())
        val categorizer = new DocumentCategorizerME(model)
        val predictions = evaluationDocs.map { doc =>
          val outcomes = categorizer.categorize(doc.tokens)
          val predicted = categorizer.getBestCategory(outcomes)
          OpenNlpPrediction(
            docId = doc.docId,
            title = doc.title,
            expectedLabel = Some(doc.label),
            predictedLabel = predicted,
            score = categorizer.scoreMap(doc.tokens).get(predicted).doubleValue()
          )
        }
        val accuracy =
          if predictions.nonEmpty then
            Some(predictions.count(prediction =>
              prediction.expectedLabel.contains(prediction.predictedLabel)
            ).toDouble / predictions.size.toDouble)
          else None
        OpenNlpCategorizationSummary(
          status = "trained",
          labelName = labelName,
          labelCounts = labelCounts,
          trainingDocumentCount = trainingDocs.size,
          evaluationDocumentCount = evaluationDocs.size,
          accuracy = accuracy,
          samplePredictions = predictions.take(5),
          message = "DocumentCategorizerME trained from dataset labels"
        )

  private def stratifiedSplit(documents: Vector[CategorizationInput])
      : (Vector[CategorizationInput], Vector[CategorizationInput]) =
    val grouped = documents.groupBy(_.label).toVector.sortBy(_._1)
    val training = Vector.newBuilder[CategorizationInput]
    val evaluation = Vector.newBuilder[CategorizationInput]
    grouped.foreach { case (_, rows) =>
      val sortedRows = rows.sortBy(_.docId)
      val splitPoint = math.max(1, math.floor(sortedRows.size * 0.8d).toInt)
      val cappedSplit = math.min(splitPoint, sortedRows.size - 1)
      val (trainRows, testRows) = sortedRows.splitAt(cappedSplit)
      training ++= trainRows
      evaluation ++= testRows
    }
    (training.result(), evaluation.result())

  private final case class CategorizationInput(docId: String, title: String, label: String, tokens: Array[String])

  final class TextProcessor(
      sentenceDetector: Option[SentenceDetectorME],
      tokenizer: Tokenizer,
      posTagger: Option[POSTaggerME],
      chunker: Option[ChunkerME]
  ):
    def sentences(text: String): Seq[String] =
      val trimmed = text.trim
      if trimmed.isEmpty then Seq.empty
      else
        sentenceDetector
          .map(_.sentDetect(trimmed).toSeq.map(_.trim).filter(_.nonEmpty))
          .getOrElse(sentenceSplitRegex.split(trimmed).toSeq.map(_.trim).filter(_.nonEmpty))

    def normalizedTokens(text: String): Seq[String] =
      tokenize(text).flatMap(normalizeToken)

    def nounPhrases(text: String): Seq[String] =
      val sentenceSeq = sentences(text)
      val modelPhrases =
        for
          tagger <- posTagger.toSeq
          chunkerModel <- chunker.toSeq
          sentence <- sentenceSeq
          tokens = tokenize(sentence)
          if tokens.nonEmpty
          tags = tagger.tag(tokens.toArray)
          chunks = chunkerModel.chunk(tokens.toArray, tags)
          phrase <- chunkNounPhrases(tokens, chunks)
        yield phrase

      if modelPhrases.nonEmpty then modelPhrases
      else
        sentenceSeq
          .flatMap(sentence => ngrams(normalizedTokens(sentence), 2) ++ ngrams(normalizedTokens(sentence), 3))
          .filter(phrase => phrase.split(' ').length >= 2)

    private def tokenize(text: String): Seq[String] =
      tokenizer.tokenize(text).toSeq.map(_.trim).filter(_.nonEmpty)

    private def chunkNounPhrases(tokens: Seq[String], chunkTags: Array[String]): Seq[String] =
      val builder = Vector.newBuilder[String]
      val current = mutable.ArrayBuffer.empty[String]
      tokens.zip(chunkTags.toSeq).foreach { case (token, tag) =>
        if tag == "B-NP" then
          flushCurrent(current, builder)
          normalizeToken(token).foreach(current += _)
        else if tag == "I-NP" then
          normalizeToken(token).foreach(current += _)
        else flushCurrent(current, builder)
      }
      flushCurrent(current, builder)
      builder.result().filter(_.nonEmpty)

    private def flushCurrent(
        current: mutable.ArrayBuffer[String],
        builder: mutable.Builder[String, Vector[String]]
    ): Unit =
      if current.nonEmpty then
        val phrase = current.mkString(" ").trim
        if phrase.split(' ').length >= 2 then builder += phrase
        current.clear()

  private def normalizeToken(token: String): Option[String] =
    val lower = token.trim.toLowerCase
    if preserveTokens.contains(lower) then Some(lower)
    else
      tokenPattern.findFirstIn(lower).filter { candidate =>
        candidate.length > 1 && (!stopwords.contains(candidate) || preserveTokens.contains(candidate))
      }
