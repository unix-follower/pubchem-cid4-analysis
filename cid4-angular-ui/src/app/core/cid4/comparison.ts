import { MoleculeGraph } from "./types"

export interface AtomDisplacementRow {
  atomId: number
  elementSymbol: string
  displacement: number
}

export interface BondDeltaRow {
  bondId: string
  source: number
  target: number
  lengthDelta: number
}

export interface MoleculeComparisonSummary {
  comparedAtomCount: number
  comparedBondCount: number
  meanAtomDisplacement: number
  maxAtomDisplacement: number
  maxBondLengthDelta: number
  topAtomDisplacements: AtomDisplacementRow[]
  topBondDeltas: BondDeltaRow[]
}

export function compareMolecules(
  activeMolecule: MoleculeGraph,
  referenceMolecule: MoleculeGraph,
): MoleculeComparisonSummary | null {
  const referenceAtoms = new Map(referenceMolecule.atoms.map((atom) => [atom.id, atom]))
  const atomDisplacements = activeMolecule.atoms.flatMap((atom) => {
    const referenceAtom = referenceAtoms.get(atom.id)

    if (!referenceAtom) {
      return []
    }

    return [
      {
        atomId: atom.id,
        elementSymbol: atom.elementSymbol,
        displacement: distanceBetweenAtoms(atom, referenceAtom),
      },
    ]
  })

  const referenceBondLengths = new Map(
    referenceMolecule.bonds.map((bond) => [bond.id, bondLength(referenceMolecule, bond.id)]),
  )
  const bondDeltas = activeMolecule.bonds.flatMap((bond) => {
    const referenceLength = referenceBondLengths.get(bond.id)
    const activeLength = bondLength(activeMolecule, bond.id)

    if (referenceLength === undefined || referenceLength === null || activeLength === null) {
      return []
    }

    return [
      {
        bondId: bond.id,
        source: bond.source,
        target: bond.target,
        lengthDelta: Math.abs(activeLength - referenceLength),
      },
    ]
  })

  if (atomDisplacements.length === 0 && bondDeltas.length === 0) {
    return null
  }

  const meanAtomDisplacement =
    atomDisplacements.length === 0
      ? 0
      : atomDisplacements.reduce((total, atom) => total + atom.displacement, 0) /
        atomDisplacements.length
  const maxAtomDisplacement = atomDisplacements.reduce(
    (currentMax, atom) => Math.max(currentMax, atom.displacement),
    0,
  )
  const maxBondLengthDelta = bondDeltas.reduce(
    (currentMax, bond) => Math.max(currentMax, bond.lengthDelta),
    0,
  )

  return {
    comparedAtomCount: atomDisplacements.length,
    comparedBondCount: bondDeltas.length,
    meanAtomDisplacement,
    maxAtomDisplacement,
    maxBondLengthDelta,
    topAtomDisplacements: [...atomDisplacements]
      .sort((left, right) => right.displacement - left.displacement)
      .slice(0, 3),
    topBondDeltas: [...bondDeltas]
      .sort((left, right) => right.lengthDelta - left.lengthDelta)
      .slice(0, 3),
  }
}

function bondLength(molecule: MoleculeGraph, bondId: string): number | null {
  const bond = molecule.bonds.find((candidate) => candidate.id === bondId)

  if (!bond) {
    return null
  }

  const atomsById = new Map(molecule.atoms.map((atom) => [atom.id, atom]))
  const source = atomsById.get(bond.source)
  const target = atomsById.get(bond.target)

  if (!source || !target) {
    return null
  }

  return distanceBetweenAtoms(source, target)
}

function distanceBetweenAtoms(
  left: Pick<MoleculeGraph["atoms"][number], "x" | "y" | "z">,
  right: Pick<MoleculeGraph["atoms"][number], "x" | "y" | "z">,
): number {
  return Math.hypot(left.x - right.x, left.y - right.y, left.z - right.z)
}
