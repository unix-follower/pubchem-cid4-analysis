import {
  AdjacencyRow,
  ComponentGroup,
  CompoundSectionNode,
  FlatSectionNode,
  LayoutMode,
  MatrixRow,
  MoleculeGraph,
  Point,
} from "./types"

export function buildAdjacencyList(
  molecule: MoleculeGraph,
  activeBondIds?: ReadonlySet<string>,
): AdjacencyRow[] {
  const adjacency = new Map<number, number[]>()

  for (const atom of molecule.atoms) {
    adjacency.set(atom.id, [])
  }

  for (const bond of molecule.bonds) {
    if (activeBondIds && !activeBondIds.has(bond.id)) {
      continue
    }

    adjacency.get(bond.source)?.push(bond.target)
    adjacency.get(bond.target)?.push(bond.source)
  }

  return molecule.atoms
    .map((atom) => ({
      atomId: atom.id,
      neighbors: [...(adjacency.get(atom.id) ?? [])].sort((left, right) => left - right),
    }))
    .sort((left, right) => left.atomId - right.atomId)
}

export function buildAdjacencyMatrix(
  molecule: MoleculeGraph,
  activeBondIds?: ReadonlySet<string>,
): MatrixRow[] {
  const orderedAtoms = [...molecule.atoms].sort((left, right) => left.id - right.id)
  const indexByAtomId = new Map(orderedAtoms.map((atom, index) => [atom.id, index]))
  const matrix = orderedAtoms.map(() => orderedAtoms.map(() => 0))

  for (const bond of molecule.bonds) {
    if (activeBondIds && !activeBondIds.has(bond.id)) {
      continue
    }

    const sourceIndex = indexByAtomId.get(bond.source)
    const targetIndex = indexByAtomId.get(bond.target)

    if (sourceIndex === undefined || targetIndex === undefined) {
      continue
    }

    matrix[sourceIndex][targetIndex] = bond.order
    matrix[targetIndex][sourceIndex] = bond.order
  }

  return orderedAtoms.map((atom, index) => ({
    atomId: atom.id,
    values: matrix[index],
  }))
}

export function findConnectedComponents(
  molecule: MoleculeGraph,
  activeBondIds?: ReadonlySet<string>,
): ComponentGroup[] {
  const parent = new Map<number, number>()

  for (const atom of molecule.atoms) {
    parent.set(atom.id, atom.id)
  }

  const find = (atomId: number): number => {
    const nextParent = parent.get(atomId)

    if (nextParent === undefined || nextParent === atomId) {
      return atomId
    }

    const root = find(nextParent)
    parent.set(atomId, root)
    return root
  }

  const union = (left: number, right: number): void => {
    const leftRoot = find(left)
    const rightRoot = find(right)

    if (leftRoot === rightRoot) {
      return
    }

    if (leftRoot < rightRoot) {
      parent.set(rightRoot, leftRoot)
    } else {
      parent.set(leftRoot, rightRoot)
    }
  }

  for (const bond of molecule.bonds) {
    if (activeBondIds && !activeBondIds.has(bond.id)) {
      continue
    }

    union(bond.source, bond.target)
  }

  const groups = new Map<number, number[]>()

  for (const atom of molecule.atoms) {
    const root = find(atom.id)
    const group = groups.get(root) ?? []
    group.push(atom.id)
    groups.set(root, group)
  }

  return [...groups.entries()]
    .map(([root, atomIds], index) => ({
      id: `component-${index + 1}-root-${root}`,
      atomIds: atomIds.sort((left, right) => left - right),
    }))
    .sort((left, right) => left.atomIds[0] - right.atomIds[0])
}

export function flattenSections(nodes: CompoundSectionNode[], depth = 0): FlatSectionNode[] {
  return nodes.flatMap((node) => [
    {
      id: node.id,
      heading: node.heading,
      description: node.description,
      depth,
      childCount: node.children.length,
    },
    ...flattenSections(node.children, depth + 1),
  ])
}

export function buildLayoutPositions(
  molecule: MoleculeGraph,
  mode: LayoutMode,
): Map<number, Point> {
  if (mode === "circle") {
    return new Map(
      molecule.atoms.map((atom, index) => {
        const angle = (index / molecule.atoms.length) * Math.PI * 2

        return [
          atom.id,
          {
            x: Math.cos(angle),
            y: Math.sin(angle),
          },
        ]
      }),
    )
  }

  return new Map(molecule.atoms.map((atom) => [atom.id, { x: atom.x, y: atom.y }]))
}
