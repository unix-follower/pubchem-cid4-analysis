package org.example.model

import com.fasterxml.jackson.annotation.JsonCreator
import com.fasterxml.jackson.annotation.JsonProperty

@JsonCreator
final case class Conformer3DCompoundDto(@JsonProperty("PC_Compounds") pcCompounds: Seq[PcCompound])

final case class PcCompound(
    id: CompoundId,
    atoms: Atoms,
    bonds: Bonds,
    stereo: Seq[Stereo],
    coords: Seq[Coordinates],
    props: Seq[DataEntry],
    count: CompoundCount
)

@JsonCreator
final case class CompoundId(id: CidRef)

@JsonCreator
final case class CidRef(cid: Int)

@JsonCreator
final case class Atoms(aid: Seq[Int], element: Seq[Int])

@JsonCreator
final case class Bonds(aid1: Seq[Int], aid2: Seq[Int], order: Seq[Int])

@JsonCreator
final case class Stereo(tetrahedral: TetrahedralStereo)

@JsonCreator
final case class TetrahedralStereo(
    center: Int,
    above: Int,
    top: Int,
    bottom: Int,
    below: Int,
    parity: Int,
    `type`: Int
)

@JsonCreator
final case class Coordinates(
    @JsonProperty("type") coordinateTypes: Seq[Int],
    aid: Seq[Int],
    conformers: Seq[Conformer],
    data: Seq[DataEntry]
)

@JsonCreator
final case class Conformer(
    x: Seq[Double],
    y: Seq[Double],
    z: Seq[Double],
    data: Seq[DataEntry]
)

@JsonCreator
final case class DataEntry(urn: Urn, value: DataValue)

@JsonCreator
final case class Urn(
    label: String,
    name: Option[String],
    datatype: Int,
    parameters: Option[String],
    version: Option[String],
    software: Option[String],
    source: Option[String],
    release: Option[String]
)

@JsonCreator
final case class DataValue(
    @JsonProperty("sval") stringValue: Option[String],
    @JsonProperty("fval") floatingPointValue: Option[Double],
    @JsonProperty("slist") stringList: Option[Seq[String]],
    @JsonProperty("fvec") floatVector: Option[Seq[Double]],
    @JsonProperty("ivec") integerVector: Option[Seq[Int]]
)

@JsonCreator
final case class CompoundCount(
    @JsonProperty("heavy_atom") heavyAtom: Int,
    @JsonProperty("atom_chiral") atomChiral: Int,
    @JsonProperty("atom_chiral_def") atomChiralDef: Int,
    @JsonProperty("atom_chiral_undef") atomChiralUndef: Int,
    @JsonProperty("bond_chiral") bondChiral: Int,
    @JsonProperty("bond_chiral_def") bondChiralDef: Int,
    @JsonProperty("bond_chiral_undef") bondChiralUndef: Int,
    @JsonProperty("isotope_atom") isotopeAtom: Int,
    @JsonProperty("covalent_unit") covalentUnit: Int,
    tautomers: Int
)
