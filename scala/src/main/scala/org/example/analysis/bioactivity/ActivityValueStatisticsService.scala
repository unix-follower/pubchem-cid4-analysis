package org.example.analysis.bioactivity

import org.apache.commons.csv.CSVFormat
import org.apache.commons.csv.CSVParser
import org.apache.commons.csv.CSVPrinter
import org.apache.commons.math3.stat.descriptive.moment.Mean
import org.apache.commons.math3.stat.descriptive.moment.Skewness
import org.apache.commons.math3.stat.descriptive.moment.Variance

import java.awt.BasicStroke
import java.awt.Color
import java.awt.Font
import java.awt.Graphics2D
import java.awt.RenderingHints
import java.awt.image.BufferedImage
import java.nio.charset.StandardCharsets
import java.nio.file.Files
import java.nio.file.Path
import javax.imageio.ImageIO
import scala.jdk.CollectionConverters.*
import scala.util.Try

final case class ActivityValueRowCounts(
    totalRows: Int,
    rowsWithNumericActivityValue: Int,
    positiveNumericRows: Int,
    zeroActivityValueRows: Int,
    negativeActivityValueRows: Int,
    nonNumericOrMissingActivityValueRows: Int,
    retainedPositiveNumericRows: Int,
    droppedRows: Int,
    retainedUniqueBioassays: Int
)

final case class ActivityValueStatistics(
    sampleSize: Int,
    mean: Double,
    variance: Double,
    varianceDefinition: String,
    skewness: Option[Double],
    min: Double,
    q25: Double,
    median: Double,
    q75: Double,
    max: Double
)

final case class ActivityValueNormalityTest(
    name: String,
    computed: Boolean,
    reasonNotComputed: Option[String],
    sampleSize: Int,
    alpha: Double,
    statistic: Option[Double],
    pValue: Option[Double],
    rejectNormality: Option[Boolean],
    interpretation: String
)

final case class ActivityValueRepresentativeRow(
    bioactivityId: Long,
    bioAssayAid: Long,
    activity: String,
    aidType: String,
    activityType: String,
    activityValue: Double
)

final case class ActivityValueRetainedRowDefinition(predicate: String, excludedRows: Vector[String])

final case class ActivityValueAnalysis(
    targetQuantity: String,
    retainedRowDefinition: ActivityValueRetainedRowDefinition,
    representativeRows: Vector[ActivityValueRepresentativeRow],
    notes: Vector[String]
)

final case class ActivityValueStatisticsSummaryResult(
    rowCounts: ActivityValueRowCounts,
    statistics: ActivityValueStatistics,
    normalityTest: ActivityValueNormalityTest,
    analysis: ActivityValueAnalysis
)

final case class ActivityValueStatisticsAnalysisResult(
    headers: Vector[String],
    rows: Vector[Map[String, String]],
    summary: ActivityValueStatisticsSummaryResult
)

object ActivityValueStatisticsService:
  private val CsvFormat = CSVFormat.DEFAULT.builder().setHeader().setSkipHeaderRecord(true).build()
  private val RequiredColumns =
    Vector("Bioactivity_ID", "BioAssay_AID", "Activity", "Aid_Type", "Activity_Type", "Activity_Value")
  private val DefaultShapiroAlpha = 0.05

  def analyze(
      csvPath: Path,
      shapiroAlpha: Double = DefaultShapiroAlpha
  ): ActivityValueStatisticsAnalysisResult =
    require(shapiroAlpha > 0.0 && shapiroAlpha < 1.0, "Shapiro-Wilk alpha must be between 0 and 1")

    val parser = CSVParser.parse(csvPath, StandardCharsets.UTF_8, CsvFormat)

    try
      val headers = parser.getHeaderNames.asScala.toVector
      validateHeaders(headers)

      val allRows = parser.iterator().asScala.toVector.map { record =>
        headers.map(header => header -> record.get(header)).toMap
      }

      val numericValues = allRows.map(row => parseDouble(row("Activity_Value")))
      val rowsWithNumericActivityValue = numericValues.count(_.isDefined)
      val positiveNumericRows = numericValues.count(_.exists(_ > 0.0))
      val zeroActivityValueRows = numericValues.count(_.contains(0.0))
      val negativeActivityValueRows = numericValues.count(_.exists(_ < 0.0))

      val retainedRows = allRows.flatMap { row =>
        parsePositiveDouble(row("Activity_Value")).map { activityValue =>
          row ++ Map(
            "Activity" -> normalizeLabel(row.getOrElse("Activity", ""), fallback = "Unknown"),
            "Aid_Type" -> normalizeLabel(row.getOrElse("Aid_Type", ""), fallback = "Unknown"),
            "Activity_Type" -> normalizeLabel(row.getOrElse("Activity_Type", ""), fallback = "Unknown"),
            "Target_Name" -> normalizeLabel(row.getOrElse("Target_Name", ""), fallback = "Unknown"),
            "BioAssay_Name" -> normalizeLabel(row.getOrElse("BioAssay_Name", ""), fallback = "Unknown"),
            "Activity_Value" -> activityValue.toString
          )
        }
      }.sortBy(row => (-row("Activity_Value").toDouble, row("BioAssay_AID").toLong, row("Bioactivity_ID").toLong))

      if retainedRows.isEmpty then
        throw IllegalStateException(s"No positive numeric Activity_Value rows were found in ${csvPath.getFileName}")

      val values = retainedRows.map(_("Activity_Value").toDouble)
      val sampleSize = values.size
      val sortedValues = values.sorted.toArray
      val meanValue = new Mean().evaluate(sortedValues)
      val varianceValue = if sampleSize > 1 then new Variance(true).evaluate(sortedValues) else 0.0
      val skewnessValue = if sampleSize > 2 then Some(new Skewness().evaluate(sortedValues)) else None
      val representativeRows = selectRepresentativeRows(retainedRows).map(toRepresentativeRow)

      val normalityTest =
        if sampleSize < 3 then
          ActivityValueNormalityTest(
            name = "Shapiro-Wilk",
            computed = false,
            reasonNotComputed = Some("Shapiro-Wilk requires at least 3 retained observations."),
            sampleSize = sampleSize,
            alpha = shapiroAlpha,
            statistic = None,
            pValue = None,
            rejectNormality = None,
            interpretation = "Normality was not tested because too few positive numeric rows were retained."
          )
        else
          ActivityValueNormalityTest(
            name = "Shapiro-Wilk",
            computed = false,
            reasonNotComputed = Some(
              "Shapiro-Wilk is not available in the current Scala dependency set; the test is reported as not computed."
            ),
            sampleSize = sampleSize,
            alpha = shapiroAlpha,
            statistic = None,
            pValue = None,
            rejectNormality = None,
            interpretation =
              "Normality was not tested because the current Scala implementation does not yet provide Shapiro-Wilk."
          )

      ActivityValueStatisticsAnalysisResult(
        headers = headers,
        rows = retainedRows,
        summary = ActivityValueStatisticsSummaryResult(
          rowCounts = ActivityValueRowCounts(
            totalRows = allRows.size,
            rowsWithNumericActivityValue = rowsWithNumericActivityValue,
            positiveNumericRows = positiveNumericRows,
            zeroActivityValueRows = zeroActivityValueRows,
            negativeActivityValueRows = negativeActivityValueRows,
            nonNumericOrMissingActivityValueRows = allRows.size - rowsWithNumericActivityValue,
            retainedPositiveNumericRows = retainedRows.size,
            droppedRows = allRows.size - retainedRows.size,
            retainedUniqueBioassays = retainedRows.map(_("BioAssay_AID").toLong).distinct.size
          ),
          statistics = ActivityValueStatistics(
            sampleSize = sampleSize,
            mean = meanValue,
            variance = varianceValue,
            varianceDefinition = "sample_variance_ddof_1",
            skewness = skewnessValue,
            min = values.min,
            q25 = computeLinearQuantile(sortedValues, 0.25),
            median = computeLinearQuantile(sortedValues, 0.5),
            q75 = computeLinearQuantile(sortedValues, 0.75),
            max = values.max
          ),
          normalityTest = normalityTest,
          analysis = ActivityValueAnalysis(
            targetQuantity = "Positive numeric Activity_Value distribution",
            retainedRowDefinition = ActivityValueRetainedRowDefinition(
              predicate = "Activity_Value is numeric and strictly greater than 0",
              excludedRows = Vector(
                "missing Activity_Value",
                "non-numeric Activity_Value",
                "Activity_Value = 0",
                "Activity_Value < 0"
              )
            ),
            representativeRows = representativeRows,
            notes = Vector(
              "The retained distribution aggregates all positive numeric Activity_Value rows regardless of Activity_Type.",
              "Variance is reported as the sample variance with ddof = 1 to match the Python implementation.",
              "The plot shows a log-scale histogram and a diagnostic status panel for Shapiro-Wilk / Q-Q availability."
            )
          )
        )
      )
    finally
      parser.close()

  def writeCsv(result: ActivityValueStatisticsAnalysisResult, outputPath: Path): Path =
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

  def writePlot(result: ActivityValueStatisticsAnalysisResult, outputPath: Path): Path =
    Files.createDirectories(outputPath.getParent)

    val image = new BufferedImage(1200, 600, BufferedImage.TYPE_INT_ARGB)
    val graphics = image.createGraphics()

    try
      graphics.setRenderingHint(RenderingHints.KEY_ANTIALIASING, RenderingHints.VALUE_ANTIALIAS_ON)
      graphics.setColor(Color.WHITE)
      graphics.fillRect(0, 0, image.getWidth, image.getHeight)

      val titleFont = new Font("SansSerif", Font.BOLD, 24)
      val labelFont = new Font("SansSerif", Font.PLAIN, 16)
      val smallFont = new Font("SansSerif", Font.PLAIN, 14)

      graphics.setColor(new Color(32, 32, 32))
      graphics.setFont(titleFont)
      graphics.drawString("Positive Numeric Activity_Value Diagnostics", 300, 40)

      val values = result.rows.map(_("Activity_Value").toDouble)
      drawHistogramPanel(graphics, values, 60, 90, 500, 430, labelFont, smallFont)
      drawDiagnosticPanel(graphics, result.summary.normalityTest, 640, 90, 500, 430, labelFont, smallFont)
    finally
      graphics.dispose()

    ImageIO.write(image, "png", outputPath.toFile)
    outputPath

  private def validateHeaders(headers: Vector[String]): Unit =
    val missing = RequiredColumns.filterNot(headers.contains)
    if missing.nonEmpty then
      throw IllegalArgumentException(s"Bioactivity CSV is missing required columns: ${missing.mkString(", ")}")

  private def parseDouble(value: String): Option[Double] =
    Option(value).map(_.trim).filter(_.nonEmpty).flatMap(raw => Try(raw.toDouble).toOption)

  private def parsePositiveDouble(value: String): Option[Double] =
    parseDouble(value).filter(_ > 0.0)

  private def computeLinearQuantile(sortedValues: Array[Double], probability: Double): Double =
    require(sortedValues.nonEmpty, "Quantile computation requires at least one value")
    require(probability >= 0.0 && probability <= 1.0, "Quantile probability must be between 0 and 1")

    if sortedValues.length == 1 then sortedValues.head
    else
      val position = (sortedValues.length - 1).toDouble * probability
      val lowerIndex = math.floor(position).toInt
      val upperIndex = math.ceil(position).toInt
      if lowerIndex == upperIndex then sortedValues(lowerIndex)
      else
        val weight = position - lowerIndex.toDouble
        sortedValues(lowerIndex) + weight * (sortedValues(upperIndex) - sortedValues(lowerIndex))

  private def normalizeLabel(value: String, fallback: String): String =
    Option(value).map(_.trim).filter(_.nonEmpty).getOrElse(fallback)

  private def selectRepresentativeRows(rows: Vector[Map[String, String]]): Vector[Map[String, String]] =
    Vector(0, rows.size / 2, rows.size - 1).distinct.sorted.map(rows)

  private def toRepresentativeRow(row: Map[String, String]): ActivityValueRepresentativeRow =
    ActivityValueRepresentativeRow(
      bioactivityId = row("Bioactivity_ID").toLong,
      bioAssayAid = row("BioAssay_AID").toLong,
      activity = row("Activity"),
      aidType = row("Aid_Type"),
      activityType = row("Activity_Type"),
      activityValue = row("Activity_Value").toDouble
    )

  private def drawHistogramPanel(
      graphics: Graphics2D,
      values: Vector[Double],
      x: Int,
      y: Int,
      width: Int,
      height: Int,
      labelFont: Font,
      smallFont: Font
  ): Unit =
    graphics.setColor(Color.BLACK)
    graphics.setFont(labelFont)
    graphics.drawString("Positive Numeric Activity_Value Histogram", x + 60, y - 20)

    val logValues = values.map(math.log10)
    val minLog = logValues.min
    val maxLog = logValues.max
    val binCount = if values.size <= 4 then values.size else 8
    val safeBinCount = math.max(1, binCount)
    val binWidth = if math.abs(maxLog - minLog) < 1e-12 then 1.0 else (maxLog - minLog) / safeBinCount.toDouble

    val counts = Vector.tabulate(safeBinCount) { index =>
      if safeBinCount == 1 then values.size
      else
        val lower = minLog + index * binWidth
        val upper = if index == safeBinCount - 1 then maxLog + 1e-12 else lower + binWidth
        logValues.count(value => value >= lower && value < upper)
    }

    val axisLeft = x + 60
    val axisTop = y + 20
    val axisWidth = width - 90
    val axisHeight = height - 90
    val maxCount = math.max(1, counts.max)

    graphics.setColor(new Color(235, 235, 235))
    graphics.fillRect(axisLeft, axisTop, axisWidth, axisHeight)
    graphics.setColor(Color.DARK_GRAY)
    graphics.drawRect(axisLeft, axisTop, axisWidth, axisHeight)

    counts.zipWithIndex.foreach { case (count, index) =>
      val barWidth = axisWidth.toDouble / safeBinCount.toDouble
      val barHeight = axisHeight.toDouble * (count.toDouble / maxCount.toDouble)
      val barX = axisLeft + math.round(index * barWidth).toInt + 1
      val barY = axisTop + axisHeight - math.round(barHeight).toInt
      graphics.setColor(new Color(95, 144, 187))
      graphics.fillRect(barX, barY, math.max(1, math.round(barWidth).toInt - 2), math.round(barHeight).toInt)
      graphics.setColor(Color.BLACK)
      graphics.drawRect(barX, barY, math.max(1, math.round(barWidth).toInt - 2), math.round(barHeight).toInt)
    }

    graphics.setFont(smallFont)
    graphics.setColor(Color.BLACK)
    graphics.drawString("Frequency", x, axisTop + axisHeight / 2)
    graphics.drawString("Activity_Value (log10 scale)", axisLeft + 130, y + height - 10)

    val tickCount = 4
    Vector.tabulate(tickCount + 1) { tickIndex =>
      val t = tickIndex.toDouble / tickCount.toDouble
      val tickLog = minLog + t * (maxLog - minLog)
      val tickX = axisLeft + math.round(t * axisWidth.toDouble).toInt
      val label = formatCompact(math.pow(10.0, tickLog))
      (tickX, label)
    }.foreach { case (tickX, label) =>
      graphics.drawLine(tickX, axisTop + axisHeight, tickX, axisTop + axisHeight + 6)
      graphics.drawString(label, tickX - 14, axisTop + axisHeight + 24)
    }

    Vector.tabulate(maxCount + 1)(index => index).foreach { tick =>
      val tickY = axisTop + axisHeight - math.round(axisHeight.toDouble * tick.toDouble / maxCount.toDouble).toInt
      graphics.drawLine(axisLeft - 6, tickY, axisLeft, tickY)
      graphics.drawString(tick.toString, axisLeft - 28, tickY + 5)
    }

  private def drawDiagnosticPanel(
      graphics: Graphics2D,
      normalityTest: ActivityValueNormalityTest,
      x: Int,
      y: Int,
      width: Int,
      height: Int,
      labelFont: Font,
      smallFont: Font
  ): Unit =
    graphics.setColor(Color.BLACK)
    graphics.setFont(labelFont)
    graphics.drawString("Normality / Q-Q Diagnostics", x + 105, y - 20)

    graphics.setColor(new Color(245, 245, 245))
    graphics.fillRect(x + 10, y + 20, width - 20, height - 40)
    graphics.setColor(Color.DARK_GRAY)
    graphics.setStroke(new BasicStroke(1.5f))
    graphics.drawRect(x + 10, y + 20, width - 20, height - 40)

    graphics.setColor(Color.BLACK)
    graphics.setFont(labelFont)
    val headline = if normalityTest.computed then "Shapiro-Wilk computed" else "Shapiro-Wilk not computed"
    graphics.drawString(headline, x + 125, y + 95)
    graphics.setFont(smallFont)

    val lines = Vector(
      s"sample size = ${normalityTest.sampleSize}",
      f"alpha = ${normalityTest.alpha}%.2f",
      normalityTest.reasonNotComputed.getOrElse("Q-Q panel not rendered in the current Scala implementation."),
      normalityTest.interpretation
    )

    lines.zipWithIndex.foreach { case (line, index) =>
      drawWrappedString(graphics, line, x + 45, y + 150 + index * 70, width - 90)
    }

  private def drawWrappedString(graphics: Graphics2D, text: String, x: Int, y: Int, maxWidth: Int): Unit =
    val words = text.split(" ").toVector
    var currentLine = ""
    var lineIndex = 0

    words.foreach { word =>
      val candidate = if currentLine.isEmpty then word else s"$currentLine $word"
      val candidateWidth = graphics.getFontMetrics.stringWidth(candidate)
      if candidateWidth <= maxWidth then currentLine = candidate
      else
        graphics.drawString(currentLine, x, y + lineIndex * 22)
        currentLine = word
        lineIndex += 1
    }

    if currentLine.nonEmpty then graphics.drawString(currentLine, x, y + lineIndex * 22)

  private def formatCompact(value: Double): String =
    f"$value%.4g"
