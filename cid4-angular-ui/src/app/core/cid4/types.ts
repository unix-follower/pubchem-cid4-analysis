export interface AtomNode {
  id: number
  atomicNumber: number
  elementSymbol: string
  mass: number
  hybridization: string | null
  x: number
  y: number
  z: number
}

export interface BondEdge {
  id: string
  source: number
  target: number
  order: number
}

export interface MoleculeGraph {
  cid: number
  title: string
  atoms: AtomNode[]
  bonds: BondEdge[]
}

export interface AdjacencyRow {
  atomId: number
  neighbors: number[]
}

export interface MatrixRow {
  atomId: number
  values: number[]
}

export interface ComponentGroup {
  id: string
  atomIds: number[]
}

export interface CompoundSectionNode {
  id: string
  heading: string
  description: string | null
  children: CompoundSectionNode[]
}

export interface CompoundRecord {
  recordNumber: number
  title: string
  sections: CompoundSectionNode[]
}

export interface FlatSectionNode {
  id: string
  heading: string
  description: string | null
  depth: number
  childCount: number
}

export interface Point {
  x: number
  y: number
}

export type LayoutMode = "source" | "circle"
