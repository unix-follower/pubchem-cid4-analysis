export interface AlgorithmGraphNode {
  id: string
  label: string
  x?: number
  y?: number
}

export interface AlgorithmGraphEdge {
  id: string
  source: string
  target: string
  label?: string
  weight?: number
}

export interface AlgorithmGraph {
  id: string
  title: string
  directed: boolean
  nodes: AlgorithmGraphNode[]
  edges: AlgorithmGraphEdge[]
}

export interface GraphTraceStep {
  label: string
  detail: string
  activeNodeIds: string[]
  activeEdgeIds: string[]
  visitedNodeIds: string[]
  frontierNodeIds: string[]
  pathNodeIds: string[]
  pathEdgeIds: string[]
}

export interface GraphTraceResult {
  algorithm: string
  headline: string
  detail: string
  order: string[]
  steps: GraphTraceStep[]
  graph?: AlgorithmGraph
  metrics?: Record<string, number | string | boolean>
}

export interface GraphNodeMetric {
  nodeId: string
  label: string
  degree: number
  eccentricity: number
}

export interface MolecularGraphMetrics {
  nodeMetrics: GraphNodeMetric[]
  degreeSequence: number[]
  density: number
  diameter: number
  radius: number
  centerNodeIds: string[]
  connectedComponentCount: number
}

export interface MatrixAnalysis {
  adjacencyMatrix: number[][]
  degreeMatrix: number[][]
  laplacianMatrix: number[][]
  eigenvalues: number[]
  fiedlerValue: number | null
}

export interface MorganIteration {
  round: number
  labels: Record<string, number>
  changedNodeIds: string[]
}

export interface MorganAnalysisResult {
  rounds: MorganIteration[]
  stabilizedAfterRound: number
}

export interface SortTraceStep {
  label: string
  detail: string
  values: number[]
  activeIndices: number[]
}

export interface SortTraceResult {
  algorithm: string
  steps: SortTraceStep[]
  sortedValues: number[]
  comparisons: number
  writes: number
}

export interface BinarySearchTraceStep {
  label: string
  detail: string
  low: number
  high: number
  middle: number
  values: number[]
  activeIndices: number[]
}

export interface BinarySearchTraceResult {
  threshold: number
  index: number
  value: number | null
  steps: BinarySearchTraceStep[]
}

export interface DeduplicationResult<T> {
  uniqueItems: T[]
  duplicates: T[]
  duplicateKeys: string[]
}
