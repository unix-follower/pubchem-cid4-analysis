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
  const root = input as UnknownRecord
  const compounds = root["PC_Compounds"] as unknown[]
  const compound = compounds[0] as UnknownRecord
  const compoundId = compound["id"] as UnknownRecord
  const compoundIdBody = compoundId["id"] as UnknownRecord
  const cid = compoundIdBody["cid"] as number

  const atoms = compound["atoms"] as UnknownRecord
  const atomIds = atoms["aid"] as number[]
  const atomicNumbers = atoms["element"] as number[]

  if (atomIds.length !== atomicNumbers.length) {
    throw new Error("Atom ids and element arrays must have the same length")
  }

  const bonds = compound["bonds"] as UnknownRecord
  const bondAid1 = bonds["aid1"] as number[]
  const bondAid2 = bonds["aid2"] as number[]
  const bondOrders = bonds["order"] as number[]

  if (bondAid1.length !== bondAid2.length || bondAid1.length !== bondOrders.length) {
    throw new Error("Bond arrays must have the same length")
  }

  const coords = compound["coords"] as unknown[]
  const coordinateRecord = coords[0] as UnknownRecord
  const conformers = coordinateRecord["conformers"] as unknown[]
  const conformer = conformers[0] as UnknownRecord
  const coordinateAtomIds = Array.isArray(coordinateRecord["aid"])
    ? (coordinateRecord["aid"] as number[])
    : atomIds

  const x = conformer["x"] as number[]
  const y = conformer["y"] as number[]
  const z = Array.isArray(conformer["z"])
    ? (conformer["z"] as number[])
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
  const root = input as UnknownRecord
  const record = root["Record"] as UnknownRecord
  const sections = record["Section"] as unknown[]

  return {
    recordNumber: record["RecordNumber"] as number,
    title: record["RecordTitle"] as string,
    sections: sections.map((section, index) => parseSection(section, `section-${index}`)),
  }
}

function parseSection(input: unknown, id: string): CompoundSectionNode {
  const section = input as UnknownRecord
  const children = section["Section"] as CompoundSectionNode[]

  return {
    id,
    heading: section["TOCHeading"] as string,
    description: section["Description"] as string,
    children: children.map((child, index) => parseSection(child, `${id}-${index}`)),
  }
}
