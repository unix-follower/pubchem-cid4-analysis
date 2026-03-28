package org.example

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

def readJson = {
  val dataDirectory = fsUtils.getDataDir()
  if (dataDirectory == null) {
    throw new IllegalStateException("Env variable DATA_DIR is not set")
  }

  val jsonPath = Path.of(s"$dataDirectory/Conformer3D_COMPOUND_CID_4(1).json")

  val jsonMapper = JsonMapper.builder()
    .addModule(DefaultScalaModule())
    .build()

  val dto = jsonMapper.readValue(Files.readAllBytes(jsonPath), classOf[Conformer3DCompoundDto])

  val compoundCount = dto.pcCompounds.size
  val firstCompound = dto.pcCompounds.headOption
  val atomCount = firstCompound.map(_.atoms.aid.size).getOrElse(0)
  val conformerCount = firstCompound.map(_.coords.flatMap(_.conformers).size).getOrElse(0)

  logger.info(s"Loaded $compoundCount compound(s) from $jsonPath")
  logger.info(s"First compound atoms: $atomCount")
  logger.info(s"First compound conformers: $conformerCount")
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
def main(): Unit =
  readJson
  readSdf()
