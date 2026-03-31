package org.example

import org.example.analysis.adjacency.AdjacencyMatrix
import org.example.analysis.adjacency.AdjacencyMatrixService
import org.example.analysis.bioactivity.BioactivityAnalysisResult
import org.example.analysis.bioactivity.BioactivityService
import org.example.analysis.bioactivity.HillDoseResponseAnalysisResult
import org.example.analysis.bioactivity.HillDoseResponseService
import org.example.analysis.distance.BondAngleAnalysisResult
import org.example.analysis.distance.BondAngleAnalysisService
import org.example.analysis.distance.BondedDistanceAnalysisResult
import org.example.analysis.distance.BondedDistanceAnalysisService
import org.example.analysis.distance.DistanceMatrixResult
import org.example.analysis.distance.DistanceMatrixService
import org.example.analysis.distance.GradientDescentAnalysisResult
import org.example.analysis.distance.GradientDescentAnalysisService
import org.example.analysis.spectrum.EigendecompositionResult
import org.example.analysis.spectrum.EigendecompositionService
import org.example.analysis.spectrum.LaplacianAnalysisResult
import org.example.analysis.spectrum.LaplacianService
import org.example.model.Conformer3DCompoundDto
import org.example.utils as fsUtils
import org.openscience.cdk.DefaultChemObjectBuilder
import org.openscience.cdk.interfaces.IAtomContainer
import org.openscience.cdk.io.iterator.IteratingSDFReader
import org.openscience.cdk.tools.manipulator.AtomContainerManipulator
import org.slf4j.LoggerFactory
import tools.jackson.databind.json.JsonMapper
import tools.jackson.module.scala.DefaultScalaModule

import java.io.File
import java.io.FileInputStream
import java.nio.file.Files
import java.nio.file.Path

private val logger = LoggerFactory.getLogger(this.getClass)

private def newJsonMapper() =
  JsonMapper.builder()
    .addModule(DefaultScalaModule())
    .build()

private def writeAdjacencyMatrix(
    dataDirectory: String,
    sourceFileName: String,
    adjacencyMatrix: AdjacencyMatrix
): Path =
  val outDirectory = Path.of(dataDirectory, "out")
  Files.createDirectories(outDirectory)

  val outputFileName =
    s"${sourceFileName.stripSuffix(".json")}.${adjacencyMatrix.method}.adjacency_matrix.json"
  val outputPath = outDirectory.resolve(outputFileName)
  newJsonMapper().writerWithDefaultPrettyPrinter().writeValue(outputPath.toFile, adjacencyMatrix)
  outputPath

private def writeAdjacencySpectrum(
    dataDirectory: String,
    sourceFileName: String,
    result: EigendecompositionResult
): Path =
  val outDirectory = Path.of(dataDirectory, "out")
  Files.createDirectories(outDirectory)

  val outputFileName =
    s"${sourceFileName.stripSuffix(".json")}.${result.adjacencyMethod}.eigendecomposition.json"
  val outputPath = outDirectory.resolve(outputFileName)
  newJsonMapper().writerWithDefaultPrettyPrinter().writeValue(outputPath.toFile, result)
  outputPath

private def writeLaplacianAnalysis(
    dataDirectory: String,
    sourceFileName: String,
    result: LaplacianAnalysisResult
): Path =
  val outDirectory = Path.of(dataDirectory, "out")
  Files.createDirectories(outDirectory)

  val outputFileName =
    s"${sourceFileName.stripSuffix(".json")}.${result.adjacencyMethod}.laplacian_analysis.json"
  val outputPath = outDirectory.resolve(outputFileName)
  newJsonMapper().writerWithDefaultPrettyPrinter().writeValue(outputPath.toFile, result)
  outputPath

private def writeDistanceMatrix(
    dataDirectory: String,
    sourceFileName: String,
    result: DistanceMatrixResult
): Path =
  val outDirectory = Path.of(dataDirectory, "out")
  Files.createDirectories(outDirectory)

  val outputFileName =
    s"${sourceFileName.stripSuffix(".json")}.${result.sourceMethod}.distance_matrix.json"
  val outputPath = outDirectory.resolve(outputFileName)
  newJsonMapper().writerWithDefaultPrettyPrinter().writeValue(outputPath.toFile, result)
  outputPath

private def writeBondedDistanceAnalysis(
    dataDirectory: String,
    sourceFileName: String,
    result: BondedDistanceAnalysisResult
): Path =
  val outDirectory = Path.of(dataDirectory, "out")
  Files.createDirectories(outDirectory)

  val outputFileName =
    s"${sourceFileName.stripSuffix(".json")}.${result.metadata.sourceDistanceMethod}.bonded_distance_analysis.json"
  val outputPath = outDirectory.resolve(outputFileName)
  newJsonMapper().writerWithDefaultPrettyPrinter().writeValue(outputPath.toFile, result)
  outputPath

private def writeBondAngleAnalysis(
    dataDirectory: String,
    sourceFileName: String,
    result: BondAngleAnalysisResult
): Path =
  val outDirectory = Path.of(dataDirectory, "out")
  Files.createDirectories(outDirectory)

  val outputFileName =
    s"${sourceFileName.stripSuffix(".json")}.${result.metadata.sourceDistanceMethod}.bond_angle_analysis.json"
  val outputPath = outDirectory.resolve(outputFileName)
  newJsonMapper().writerWithDefaultPrettyPrinter().writeValue(outputPath.toFile, result)
  outputPath

private def writeBioactivitySummary(
    dataDirectory: String,
    sourceFileName: String,
    result: BioactivityAnalysisResult
): Path =
  val outDirectory = Path.of(dataDirectory, "out")
  Files.createDirectories(outDirectory)

  val outputFileName = s"${sourceFileName.stripSuffix(".csv")}.ic50_pic50.summary.json"
  val outputPath = outDirectory.resolve(outputFileName)
  newJsonMapper().writerWithDefaultPrettyPrinter().writeValue(outputPath.toFile, result.summary)
  outputPath

private def writeBioactivityFilteredRows(
    dataDirectory: String,
    sourceFileName: String,
    result: BioactivityAnalysisResult
): Path =
  val outDirectory = Path.of(dataDirectory, "out")
  Files.createDirectories(outDirectory)

  val outputFileName = s"${sourceFileName.stripSuffix(".csv")}.ic50_pic50.csv"
  val outputPath = outDirectory.resolve(outputFileName)
  BioactivityService.writeFilteredCsv(result, outputPath)

private def writeBioactivityPlot(
    dataDirectory: String,
    sourceFileName: String,
    result: BioactivityAnalysisResult
): Path =
  val outDirectory = Path.of(dataDirectory, "out")
  Files.createDirectories(outDirectory)

  val outputFileName = s"${sourceFileName.stripSuffix(".csv")}.ic50_pic50.png"
  val outputPath = outDirectory.resolve(outputFileName)
  BioactivityService.writePlot(result, outputPath)

private def writeHillDoseResponseSummary(
    dataDirectory: String,
    sourceFileName: String,
    result: HillDoseResponseAnalysisResult
): Path =
  val outDirectory = Path.of(dataDirectory, "out")
  Files.createDirectories(outDirectory)

  val outputFileName = s"${sourceFileName.stripSuffix(".csv")}.hill_dose_response.summary.json"
  val outputPath = outDirectory.resolve(outputFileName)
  newJsonMapper().writerWithDefaultPrettyPrinter().writeValue(outputPath.toFile, result.summary)
  outputPath

private def writeHillDoseResponseRows(
    dataDirectory: String,
    sourceFileName: String,
    result: HillDoseResponseAnalysisResult
): Path =
  val outDirectory = Path.of(dataDirectory, "out")
  Files.createDirectories(outDirectory)

  val outputFileName = s"${sourceFileName.stripSuffix(".csv")}.hill_dose_response.csv"
  val outputPath = outDirectory.resolve(outputFileName)
  HillDoseResponseService.writeCsv(result, outputPath)

private def writeHillDoseResponsePlot(
    dataDirectory: String,
    sourceFileName: String,
    result: HillDoseResponseAnalysisResult
): Path =
  val outDirectory = Path.of(dataDirectory, "out")
  Files.createDirectories(outDirectory)

  val outputFileName = s"${sourceFileName.stripSuffix(".csv")}.hill_dose_response.png"
  val outputPath = outDirectory.resolve(outputFileName)
  HillDoseResponseService.writePlot(result, outputPath)

private def writeGradientDescentSummary(
    dataDirectory: String,
    sourceFileName: String,
    result: GradientDescentAnalysisResult
): Path =
  val outDirectory = Path.of(dataDirectory, "out")
  Files.createDirectories(outDirectory)

  val outputFileName = s"${sourceFileName.stripSuffix(".json")}.mass_to_atomic_number_gradient_descent.summary.json"
  val outputPath = outDirectory.resolve(outputFileName)
  newJsonMapper().writerWithDefaultPrettyPrinter().writeValue(outputPath.toFile, result.summary)
  outputPath

private def writeGradientDescentTrace(
    dataDirectory: String,
    sourceFileName: String,
    result: GradientDescentAnalysisResult
): Path =
  val outDirectory = Path.of(dataDirectory, "out")
  Files.createDirectories(outDirectory)

  val outputFileName = s"${sourceFileName.stripSuffix(".json")}.mass_to_atomic_number_gradient_descent.csv"
  val outputPath = outDirectory.resolve(outputFileName)
  GradientDescentAnalysisService.writeTraceCsv(result, outputPath)

private def writeGradientDescentLossPlot(
    dataDirectory: String,
    sourceFileName: String,
    result: GradientDescentAnalysisResult
): Path =
  val outDirectory = Path.of(dataDirectory, "out")
  Files.createDirectories(outDirectory)

  val outputFileName = s"${sourceFileName.stripSuffix(".json")}.mass_to_atomic_number_gradient_descent.loss.png"
  val outputPath = outDirectory.resolve(outputFileName)
  GradientDescentAnalysisService.writeLossPlot(result, outputPath)

private def writeGradientDescentFitPlot(
    dataDirectory: String,
    sourceFileName: String,
    result: GradientDescentAnalysisResult
): Path =
  val outDirectory = Path.of(dataDirectory, "out")
  Files.createDirectories(outDirectory)

  val outputFileName = s"${sourceFileName.stripSuffix(".json")}.mass_to_atomic_number_gradient_descent.fit.png"
  val outputPath = outDirectory.resolve(outputFileName)
  GradientDescentAnalysisService.writeFitPlot(result, outputPath)

def readJson(method: String, distanceSource: String) = {
  val dataDirectory = fsUtils.getDataDir()
  if (dataDirectory == null) {
    throw new IllegalStateException("Env variable DATA_DIR is not set")
  }

  val bioactivityPath = Path.of(s"$dataDirectory/pubchem_cid_4_bioactivity.csv")

  val jsonPath = Path.of(s"$dataDirectory/Conformer3D_COMPOUND_CID_4(1).json")
  val sdfPath = Path.of(s"$dataDirectory/Conformer3D_COMPOUND_CID_4(1).sdf")

  val jsonMapper = newJsonMapper()

  val dto = jsonMapper.readValue(Files.readAllBytes(jsonPath), classOf[Conformer3DCompoundDto])

  val compoundCount = dto.pcCompounds.size
  val firstCompound = dto.pcCompounds.headOption
  val atomCount = firstCompound.map(_.atoms.aid.size).getOrElse(0)
  val conformerCount = firstCompound.map(_.coords.flatMap(_.conformers).size).getOrElse(0)

  logger.info(s"Loaded $compoundCount compound(s) from $jsonPath")
  logger.info(s"First compound atoms: $atomCount")
  logger.info(s"First compound conformers: $conformerCount")

  firstCompound.foreach { compound =>
    val distanceMatrix = DistanceMatrixService.analyze(compound, jsonPath, sdfPath, distanceSource)
    val distanceMatrixOutputPath =
      writeDistanceMatrix(dataDirectory, jsonPath.getFileName.toString, distanceMatrix)
    val adjacencyMatrix = AdjacencyMatrixService.build(compound, method)
    val outputPath = writeAdjacencyMatrix(dataDirectory, jsonPath.getFileName.toString, adjacencyMatrix)
    val bondedDistanceAnalysis = BondedDistanceAnalysisService.analyze(distanceMatrix, adjacencyMatrix)
    val bondedDistanceAnalysisOutputPath =
      writeBondedDistanceAnalysis(dataDirectory, jsonPath.getFileName.toString, bondedDistanceAnalysis)
    val bondAngleAnalysis = BondAngleAnalysisService.analyze(distanceMatrix, adjacencyMatrix)
    val bondAngleAnalysisOutputPath =
      writeBondAngleAnalysis(dataDirectory, jsonPath.getFileName.toString, bondAngleAnalysis)
    val gradientDescentAnalysis = GradientDescentAnalysisService.analyze(compound, sdfPath)
    val gradientDescentTraceOutputPath =
      writeGradientDescentTrace(dataDirectory, jsonPath.getFileName.toString, gradientDescentAnalysis)
    val gradientDescentSummaryOutputPath =
      writeGradientDescentSummary(dataDirectory, jsonPath.getFileName.toString, gradientDescentAnalysis)
    val gradientDescentLossPlotOutputPath =
      writeGradientDescentLossPlot(dataDirectory, jsonPath.getFileName.toString, gradientDescentAnalysis)
    val gradientDescentFitPlotOutputPath =
      writeGradientDescentFitPlot(dataDirectory, jsonPath.getFileName.toString, gradientDescentAnalysis)
    val eigendecomposition = EigendecompositionService.compute(adjacencyMatrix)
    val eigendecompositionOutputPath =
      writeAdjacencySpectrum(dataDirectory, jsonPath.getFileName.toString, eigendecomposition)
    val laplacianAnalysis = LaplacianService.analyze(adjacencyMatrix)
    val laplacianOutputPath =
      writeLaplacianAnalysis(dataDirectory, jsonPath.getFileName.toString, laplacianAnalysis)
    val bioactivityAnalysis = BioactivityService.analyze(bioactivityPath)
    val hillDoseResponseAnalysis = HillDoseResponseService.analyze(bioactivityPath)
    val bioactivityRowsOutputPath =
      writeBioactivityFilteredRows(dataDirectory, bioactivityPath.getFileName.toString, bioactivityAnalysis)
    val bioactivitySummaryOutputPath =
      writeBioactivitySummary(dataDirectory, bioactivityPath.getFileName.toString, bioactivityAnalysis)
    val bioactivityPlotOutputPath =
      writeBioactivityPlot(dataDirectory, bioactivityPath.getFileName.toString, bioactivityAnalysis)
    val hillDoseResponseRowsOutputPath =
      writeHillDoseResponseRows(dataDirectory, bioactivityPath.getFileName.toString, hillDoseResponseAnalysis)
    val hillDoseResponseSummaryOutputPath =
      writeHillDoseResponseSummary(dataDirectory, bioactivityPath.getFileName.toString, hillDoseResponseAnalysis)
    val hillDoseResponsePlotOutputPath =
      writeHillDoseResponsePlot(dataDirectory, bioactivityPath.getFileName.toString, hillDoseResponseAnalysis)

    logger.info(s"Adjacency matrix method: ${adjacencyMatrix.method}")
    logger.info(
      s"Adjacency matrix size: ${adjacencyMatrix.values.size}x${adjacencyMatrix.values.headOption.map(_.size).getOrElse(0)}"
    )
    logger.info(s"Distance matrix source: ${distanceMatrix.sourceMethod}")
    logger.info(s"Distance matrix output: $distanceMatrixOutputPath")
    logger.info(s"Bonded distance analysis output: $bondedDistanceAnalysisOutputPath")
    logger.info(s"Bond angle analysis output: $bondAngleAnalysisOutputPath")
    logger.info(s"Gradient descent trace output: $gradientDescentTraceOutputPath")
    logger.info(s"Gradient descent summary output: $gradientDescentSummaryOutputPath")
    logger.info(s"Gradient descent loss plot output: $gradientDescentLossPlotOutputPath")
    logger.info(s"Gradient descent fit plot output: $gradientDescentFitPlotOutputPath")
    logger.info(s"Adjacency matrix output: $outputPath")
    logger.info(s"Adjacency eigendecomposition output: $eigendecompositionOutputPath")
    logger.info(s"Laplacian analysis output: $laplacianOutputPath")
    logger.info(s"Bioactivity filtered rows output: $bioactivityRowsOutputPath")
    logger.info(s"Bioactivity summary output: $bioactivitySummaryOutputPath")
    logger.info(s"Bioactivity plot output: $bioactivityPlotOutputPath")
    logger.info(s"Hill dose-response rows output: $hillDoseResponseRowsOutputPath")
    logger.info(s"Hill dose-response summary output: $hillDoseResponseSummaryOutputPath")
    logger.info(s"Hill dose-response plot output: $hillDoseResponsePlotOutputPath")
  }
}

private def readSdf(): Unit =
  val dataDirectory = fsUtils.getDataDir()
  val sdfFile = new File(s"${dataDirectory}/Conformer3D_COMPOUND_CID_4(1).sdf")
  val builder = DefaultChemObjectBuilder.getInstance()
  val reader = new IteratingSDFReader(new FileInputStream(sdfFile), builder)

  var totalWeight = 0.0
  var moleculeCount = 0
  var exactMolWeight = 0.0

  try
    while (reader.hasNext) {
      val molecule: IAtomContainer = reader.next()
      logger.info(s"Molecule Title: ${molecule.getProperty("cdk:Title")}")
      val elementBasedSum =
        AtomContainerManipulator.getMass(molecule, AtomContainerManipulator.MolWeight)
      val isotopeSpecificSum =
        AtomContainerManipulator.getMass(molecule, AtomContainerManipulator.MonoIsotopic)
      totalWeight += elementBasedSum
      exactMolWeight += isotopeSpecificSum
      moleculeCount += 1
    }
  finally
    reader.close()

  val averageMW = if (moleculeCount > 0) totalWeight / moleculeCount else 0.0
  val averageExactMW = if (moleculeCount > 0) exactMolWeight / moleculeCount else 0.0
  logger.info(f"Average molecular weight: $averageMW")
  logger.info(f"Exact molecular mass: $averageExactMW")

@main
def main(method: String = "jgrapht", distanceSource: String = "json"): Unit =
  readJson(method, distanceSource)
  readSdf()
