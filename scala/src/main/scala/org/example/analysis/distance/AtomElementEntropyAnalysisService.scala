package org.example.analysis.distance

import org.apache.commons.csv.CSVFormat
import org.apache.commons.csv.CSVPrinter
import org.example.model.PcCompound
import org.knowm.xchart.BitmapEncoder
import org.knowm.xchart.BitmapEncoder.BitmapFormat
import org.knowm.xchart.CategoryChartBuilder
import org.openscience.cdk.config.Isotopes

import java.nio.charset.StandardCharsets
import java.nio.file.Files
import java.nio.file.Path
import scala.jdk.CollectionConverters.*

final case class AtomElementEntropyRowCounts(
    totalAtomRows: Int,
    retainedAtomRows: Int,
    requiredElementCategories: Int,
    observedRequiredElementCategories: Int,
    unexpectedElementRows: Int,
    unexpectedElementCategories: Int
)

final case class AtomElementEntropyMetrics(
    formula: String,
    logBase: String,
    value: Double,
    maximumEntropyForObservedSupport: Double,
    normalizedEntropy: Double
)

final case class AtomElementDistributionEntry(
    count: Int,
    proportion: Double,
    logProportion: Option[Double],
    shannonContribution: Double
)

final case class AtomElementDominantElement(element: String, count: Int, proportion: Double)

final case class AtomElementEntropyAnalysis(
    targetQuantity: String,
    requiredElements: Vector[String],
    uniqueRetainedElements: Int,
    dominantElement: AtomElementDominantElement,
    unexpectedElements: Map[String, Int],
    notes: Vector[String]
)

final case class AtomElementEntropySummaryResult(
    rowCounts: AtomElementEntropyRowCounts,
    entropy: AtomElementEntropyMetrics,
    distribution: Map[String, AtomElementDistributionEntry],
    analysis: AtomElementEntropyAnalysis
)

final case class AtomElementEntropyAnalysisResult(
    headers: Vector[String],
    rows: Vector[Map[String, String]],
    summary: AtomElementEntropySummaryResult
)

object AtomElementEntropyAnalysisService:
  private val RequiredElements = Vector("O", "N", "C", "H")
  private val Headers = Vector("element", "count", "proportion", "log_proportion", "shannon_contribution")

  def analyze(compound: PcCompound): AtomElementEntropyAnalysisResult =
    require(compound.atoms.aid.size == compound.atoms.element.size, "Compound atom ids and atomic numbers must align")

    val isotopeFactory = Isotopes.getInstance()
    val symbols =
      compound.atoms.element.map(atomicNumber => isotopeFactory.getElementSymbol(atomicNumber).toUpperCase).toVector
    val symbolCounts = symbols.groupMapReduce(identity)(_ => 1)(_ + _)
    val requiredCounts = RequiredElements.map(element => element -> symbolCounts.getOrElse(element, 0)).toMap
    val unexpectedCounts = symbolCounts.filterNot { case (element, _) => RequiredElements.contains(element) }
    val retainedAtomRows = requiredCounts.values.sum

    if retainedAtomRows <= 0 then
      throw IllegalStateException("No required O/N/C/H atom symbols were found in the compound")

    val rows = RequiredElements.map { element =>
      val count = requiredCounts(element)
      val proportion = count.toDouble / retainedAtomRows.toDouble
      val logProportion = if proportion > 0.0 then Some(math.log(proportion)) else None
      val shannonContribution = if proportion > 0.0 then -proportion * math.log(proportion) else 0.0

      Map(
        "element" -> element,
        "count" -> count.toString,
        "proportion" -> proportion.toString,
        "log_proportion" -> logProportion.map(_.toString).getOrElse(""),
        "shannon_contribution" -> shannonContribution.toString
      )
    }

    val observedRequiredElementCategories = rows.count(_("count").toInt > 0)
    val entropyValue = rows.map(_("shannon_contribution").toDouble).sum
    val maximumEntropy =
      if observedRequiredElementCategories > 1 then math.log(observedRequiredElementCategories.toDouble) else 0.0
    val normalizedEntropy = if maximumEntropy > 0.0 then entropyValue / maximumEntropy else 0.0
    val dominantRow = rows.maxBy(row => (row("count").toInt, row("element")))

    AtomElementEntropyAnalysisResult(
      headers = Headers,
      rows = rows,
      summary = AtomElementEntropySummaryResult(
        rowCounts = AtomElementEntropyRowCounts(
          totalAtomRows = symbols.size,
          retainedAtomRows = retainedAtomRows,
          requiredElementCategories = RequiredElements.size,
          observedRequiredElementCategories = observedRequiredElementCategories,
          unexpectedElementRows = unexpectedCounts.values.sum,
          unexpectedElementCategories = unexpectedCounts.size
        ),
        entropy = AtomElementEntropyMetrics(
          formula = "H = -sum(p_i * log(p_i))",
          logBase = "natural_log",
          value = entropyValue,
          maximumEntropyForObservedSupport = maximumEntropy,
          normalizedEntropy = normalizedEntropy
        ),
        distribution = rows.map { row =>
          row("element") -> AtomElementDistributionEntry(
            count = row("count").toInt,
            proportion = row("proportion").toDouble,
            logProportion = row.get("log_proportion").filter(_.nonEmpty).map(_.toDouble),
            shannonContribution = row("shannon_contribution").toDouble
          )
        }.toMap,
        analysis = AtomElementEntropyAnalysis(
          targetQuantity = "Atom element entropy over O/N/C/H proportions",
          requiredElements = RequiredElements,
          uniqueRetainedElements = observedRequiredElementCategories,
          dominantElement = AtomElementDominantElement(
            element = dominantRow("element"),
            count = dominantRow("count").toInt,
            proportion = dominantRow("proportion").toDouble
          ),
          unexpectedElements = unexpectedCounts.toVector.sortBy(_._1).toMap,
          notes = Vector(
            "Entropy is computed only over the required O/N/C/H support requested in the README exercise.",
            "Unexpected atom symbols are excluded from the entropy sum and reported separately for transparency.",
            "Normalized entropy uses the maximum entropy over the observed required-element support rather than the fixed four-element support."
          )
        )
      )
    )

  def writeCsv(result: AtomElementEntropyAnalysisResult, outputPath: Path): Path =
    Files.createDirectories(outputPath.getParent)
    val writer = Files.newBufferedWriter(outputPath, StandardCharsets.UTF_8)
    val printer = new CSVPrinter(writer, CSVFormat.DEFAULT.builder().setHeader(result.headers*).build())

    try
      result.rows.foreach { row =>
        printer.printRecord(result.headers.map(header => row.getOrElse(header, "")).asJava)
      }
    finally
      printer.close(true)

    outputPath

  def writePlot(result: AtomElementEntropyAnalysisResult, outputPath: Path): Path =
    Files.createDirectories(outputPath.getParent)

    val elements = result.rows.map(_("element"))
    val proportions = result.rows.map(_("proportion").toDouble)
    val chart = new CategoryChartBuilder()
      .width(1000)
      .height(650)
      .title(f"Atom Element Proportions (H = ${result.summary.entropy.value}%.4f)")
      .xAxisTitle("Element")
      .yAxisTitle("Proportion")
      .build()

    chart.getStyler.setLegendVisible(false)
    chart.getStyler.setPlotGridLinesVisible(true)
    chart.getStyler.setYAxisMin(0.0)
    chart.getStyler.setYAxisMax(math.max(1.0, proportions.max * 1.15))
    chart.addSeries("Proportion", elements.asJava, proportions.map(Double.box).asJava)

    BitmapEncoder.saveBitmap(chart, outputPath.toString.stripSuffix(".png"), BitmapFormat.PNG)
    outputPath
