import { CompoundRecord, CompoundSectionNode, MoleculeGraph } from "./types"

const ELEMENT_SYMBOLS: Record<number, string> = {
  1: "H",
  6: "C",
  7: "N",
  8: "O",
}

const ELEMENT_MASSES: Record<number, number> = {
  1: 1.008,
  6: 12.011,
  7: 14.007,
  8: 15.999,
}

type UnknownRecord = Record<string, unknown>

export function parseConformerPayload(input: unknown): MoleculeGraph {
  return parsePcCompoundPayload(input, "Molecular Graph")
}

export function parseStructurePayload(input: unknown): MoleculeGraph {
  return parsePcCompoundPayload(input, "2D Structure")
}

function parsePcCompoundPayload(input: unknown, titleSuffix: string): MoleculeGraph {
  const root = expectRecord(input, "root")
  const compounds = expectArray(root["PC_Compounds"], "PC_Compounds")
  const compound = expectRecord(compounds[0], "PC_Compounds[0]")
  const compoundId = expectRecord(compound["id"], "PC_Compounds[0].id")
  const compoundIdBody = expectRecord(compoundId["id"], "PC_Compounds[0].id.id")
  const cid = expectNumber(compoundIdBody["cid"], "PC_Compounds[0].id.id.cid")

  const atoms = expectRecord(compound["atoms"], "PC_Compounds[0].atoms")
  const atomIds = expectNumberArray(atoms["aid"], "PC_Compounds[0].atoms.aid")
  const atomicNumbers = expectNumberArray(atoms["element"], "PC_Compounds[0].atoms.element")

  if (atomIds.length !== atomicNumbers.length) {
    throw new Error("Atom ids and element arrays must have the same length")
  }

  const bonds = expectRecord(compound["bonds"], "PC_Compounds[0].bonds")
  const bondAid1 = expectNumberArray(bonds["aid1"], "PC_Compounds[0].bonds.aid1")
  const bondAid2 = expectNumberArray(bonds["aid2"], "PC_Compounds[0].bonds.aid2")
  const bondOrders = expectNumberArray(bonds["order"], "PC_Compounds[0].bonds.order")

  if (bondAid1.length !== bondAid2.length || bondAid1.length !== bondOrders.length) {
    throw new Error("Bond arrays must have the same length")
  }

  const coords = expectArray(compound["coords"], "PC_Compounds[0].coords")
  const coordinateRecord = expectRecord(coords[0], "PC_Compounds[0].coords[0]")
  const conformers = expectArray(
    coordinateRecord["conformers"],
    "PC_Compounds[0].coords[0].conformers",
  )
  const conformer = expectRecord(conformers[0], "PC_Compounds[0].coords[0].conformers[0]")
  const coordinateAtomIds = Array.isArray(coordinateRecord["aid"])
    ? expectNumberArray(coordinateRecord["aid"], "PC_Compounds[0].coords[0].aid")
    : atomIds

  const x = expectNumberArray(conformer["x"], "PC_Compounds[0].coords[0].conformers[0].x")
  const y = expectNumberArray(conformer["y"], "PC_Compounds[0].coords[0].conformers[0].y")
  const z = Array.isArray(conformer["z"])
    ? expectNumberArray(conformer["z"], "PC_Compounds[0].coords[0].conformers[0].z")
    : new Array(coordinateAtomIds.length).fill(0)

  if (
    coordinateAtomIds.length !== x.length ||
    coordinateAtomIds.length !== y.length ||
    coordinateAtomIds.length !== z.length
  ) {
    throw new Error("Coordinate arrays must match the atom count")
  }

  const coordinatesByAtomId = new Map(
    coordinateAtomIds.map((atomId, index) => [
      atomId,
      {
        x: x[index],
        y: y[index],
        z: z[index],
      },
    ]),
  )

  return {
    cid,
    title: `CID ${cid} ${titleSuffix}`,
    atoms: atomIds.map((id, index) => {
      const atomicNumber = atomicNumbers[index]
      const coordinates = coordinatesByAtomId.get(id)

      if (!coordinates) {
        throw new Error(`Missing coordinates for atom ${id}`)
      }

      return {
        id,
        atomicNumber,
        elementSymbol: ELEMENT_SYMBOLS[atomicNumber] ?? `Z${atomicNumber}`,
        mass: ELEMENT_MASSES[atomicNumber] ?? atomicNumber,
        hybridization: null,
        x: coordinates.x,
        y: coordinates.y,
        z: coordinates.z,
      }
    }),
    bonds: bondAid1.map((source, index) => ({
      id: `${Math.min(source, bondAid2[index])}-${Math.max(source, bondAid2[index])}`,
      source,
      target: bondAid2[index],
      order: bondOrders[index],
    })),
  }
}

export function parseCompoundRecordPayload(input: unknown): CompoundRecord {
  const root = expectRecord(input, "root")
  const record = expectRecord(root["Record"], "Record")
  const recordNumber = expectNumber(record["RecordNumber"], "Record.RecordNumber")
  const title = expectString(record["RecordTitle"], "Record.RecordTitle")
  const sections = expectArray(record["Section"], "Record.Section")

  return {
    recordNumber,
    title,
    sections: sections.map((section, index) =>
      parseSection(section, `section-${index}`, `Record.Section[${index}]`),
    ),
  }
}

function parseSection(input: unknown, id: string, path: string): CompoundSectionNode {
  const section = expectRecord(input, path)
  const children = Array.isArray(section["Section"]) ? section["Section"] : []

  return {
    id,
    heading: expectString(section["TOCHeading"], `${path}.TOCHeading`),
    description: typeof section["Description"] === "string" ? section["Description"] : null,
    children: children.map((child, index) =>
      parseSection(child, `${id}-${index}`, `${path}.Section[${index}]`),
    ),
  }
}

function expectRecord(input: unknown, path: string): UnknownRecord {
  if (!input || typeof input !== "object" || Array.isArray(input)) {
    throw new Error(`${path} must be an object`)
  }

  return input as UnknownRecord
}

function expectArray(input: unknown, path: string): unknown[] {
  if (!Array.isArray(input)) {
    throw new Error(`${path} must be an array`)
  }

  return input
}

function expectNumber(input: unknown, path: string): number {
  if (typeof input !== "number" || Number.isNaN(input)) {
    throw new Error(`${path} must be a number`)
  }

  return input
}

function expectString(input: unknown, path: string): string {
  if (typeof input !== "string" || input.length === 0) {
    throw new Error(`${path} must be a non-empty string`)
  }

  return input
}

function expectNumberArray(input: unknown, path: string): number[] {
  const values = expectArray(input, path)

  return values.map((value, index) => expectNumber(value, `${path}[${index}]`))
}
