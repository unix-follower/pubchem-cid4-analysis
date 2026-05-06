import { ChangeDetectionStrategy, Component, computed, effect, signal } from "@angular/core"
import { injectQuery } from "@tanstack/angular-query-experimental"

import {
  buildMergeSortTrace,
  buildQuickSortTrace,
  buildThresholdBinarySearchTrace,
} from "../../core/algorithms/array-algorithms"
import {
  buildBfsTrace,
  buildCycleDetectionTrace,
  buildDfsTrace,
  buildLaplacianAnalysis,
  buildMinimumSpanningTreeTrace,
  buildMolecularGraphMetrics,
  buildMorganAnalysis,
  buildShortestPathTrace,
  buildTopologicalSortTrace,
} from "../../core/algorithms/graph-algorithms"
import {
  AlgorithmGraph,
  BinarySearchTraceResult,
  GraphTraceResult,
  MatrixAnalysis,
  MolecularGraphMetrics,
  MorganAnalysisResult,
} from "../../core/algorithms/types"
import { buildLayoutPositions } from "../../core/cid4/graph"
import { parseConformerPayload } from "../../core/cid4/parser"
import { MoleculeGraph, Point } from "../../core/cid4/types"
import { CytoscapeGraphComponent } from "./cytoscape-graph.component"

const GRAPH_SCENARIOS = [
  "bfs",
  "dfs",
  "weighted-shortest-path",
  "shortest-path",
  "morgan-labeling",
  "cycle-detection",
  "minimum-spanning-tree",
  "topological-sort",
] as const

const SORT_ALGORITHMS = ["merge-sort", "quick-sort"] as const

type GraphScenario = (typeof GRAPH_SCENARIOS)[number]
type SortAlgorithm = (typeof SORT_ALGORITHMS)[number]

interface PathwayResponse {
  graph: AlgorithmGraph
}

interface ReactionNetworkSummary {
  pathwayCount: number
  reactionCount: number
  compoundCount: number
  taxonomyCount: number
  edgeCount: number
  cid4ParticipationEdgeCount: number
}

interface ReactionNetworkResponse {
  graph: AlgorithmGraph
  summary: ReactionNetworkSummary
}

interface BioactivityRecord {
  aid: number
  assay: string
  activityValue: number
}

interface BioactivityResponse {
  records: BioactivityRecord[]
}

interface TaxonomyRecord {
  taxonomyId: number
  sourceOrganism: string
}

interface TaxonomyResponse {
  organisms: TaxonomyRecord[]
}

@Component({
  selector: "app-algorithms-page",
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [CytoscapeGraphComponent],
  templateUrl: "./algorithms.page.html",
  styleUrl: "./algorithms.page.css",
})
export class AlgorithmsPage {
  protected readonly graphScenarios = GRAPH_SCENARIOS
  protected readonly sortAlgorithms = SORT_ALGORITHMS

  protected readonly graphScenario = signal<GraphScenario>("bfs")
  protected readonly graphStepIndex = signal(0)
  protected readonly sortAlgorithm = signal<SortAlgorithm>("merge-sort")
  protected readonly sortStepIndex = signal(0)

  protected readonly moleculeQuery = injectQuery(() => ({
    queryKey: ["algorithms", "cid4", "conformer"],
    queryFn: fetchMolecule,
  }))

  protected readonly pathwayQuery = injectQuery(() => ({
    queryKey: ["algorithms", "pathway"],
    queryFn: fetchPathway,
  }))

  protected readonly reactionNetworkQuery = injectQuery(() => ({
    queryKey: ["algorithms", "reaction-network"],
    queryFn: fetchReactionNetwork,
  }))

  protected readonly bioactivityQuery = injectQuery(() => ({
    queryKey: ["algorithms", "bioactivity"],
    queryFn: fetchBioactivity,
  }))

  protected readonly taxonomyQuery = injectQuery(() => ({
    queryKey: ["algorithms", "taxonomy"],
    queryFn: fetchTaxonomy,
  }))

  protected readonly moleculeGraph = computed(() => {
    const molecule = this.moleculeQuery.data()
    return molecule ? mapMoleculeToAlgorithmGraph(molecule) : null
  })

  protected readonly weightedBondGraph = computed(() => {
    const molecule = this.moleculeQuery.data()
    return molecule ? buildWeightedBondGraph(molecule) : null
  })

  protected readonly completeDistanceGraph = computed(() => {
    const molecule = this.moleculeQuery.data()
    return molecule ? buildCompleteDistanceGraph(molecule) : null
  })

  protected readonly activeGraphTrace = computed<GraphTraceResult | null>(() => {
    const scenario = this.graphScenario()

    if (scenario === "topological-sort") {
      const pathway = this.pathwayQuery.data()
      return pathway ? buildTopologicalSortTrace(pathway) : null
    }

    const moleculeGraph = this.moleculeGraph()
    const weightedBondGraph = this.weightedBondGraph()

    if (!moleculeGraph) {
      return null
    }

    switch (scenario) {
      case "bfs":
        return buildBfsTrace(moleculeGraph, "1")
      case "dfs":
        return buildDfsTrace(moleculeGraph, "1")
      case "weighted-shortest-path":
        return weightedBondGraph ? buildShortestPathTrace(weightedBondGraph, "1", "2") : null
      case "shortest-path":
        return buildShortestPathTrace(moleculeGraph, "1", "2")
      case "morgan-labeling":
        return buildMorganTrace(moleculeGraph)
      case "cycle-detection":
        return buildCycleDetectionTrace(moleculeGraph, "1")
      case "minimum-spanning-tree": {
        const completeGraph = this.completeDistanceGraph()
        return completeGraph ? buildMinimumSpanningTreeTrace(completeGraph) : null
      }
      default:
        return null
    }
  })

  protected readonly activeGraphDisplayGraph = computed(() => {
    const trace = this.activeGraphTrace()
    const scenario = this.graphScenario()

    if (scenario === "minimum-spanning-tree") {
      return trace?.graph ?? emptyGraph("mst")
    }

    if (scenario === "weighted-shortest-path") {
      return this.weightedBondGraph() ?? emptyGraph("weighted-bonds")
    }

    if (scenario === "topological-sort") {
      return this.pathwayQuery.data() ?? emptyGraph("pathway")
    }

    return this.moleculeGraph() ?? emptyGraph("molecule")
  })

  protected readonly activeGraphStep = computed(() => {
    const trace = this.activeGraphTrace()
    const index = this.graphStepIndex()
    return trace?.steps[index] ?? null
  })

  protected readonly graphScenarioLabel = computed(() =>
    this.formatScenarioLabel(this.graphScenario()),
  )
  protected readonly graphMetrics = computed(() => {
    const metrics = this.activeGraphTrace()?.metrics ?? {}
    return Object.entries(metrics).map(([label, value]) => ({
      label: humanizeMetricLabel(label),
      value: String(value),
    }))
  })
  protected readonly molecularMetrics = computed<MolecularGraphMetrics | null>(() => {
    const graph = this.moleculeGraph()
    return graph ? buildMolecularGraphMetrics(graph) : null
  })
  protected readonly reactionNetworkGraph = computed(
    () => this.reactionNetworkQuery.data()?.graph ?? null,
  )
  protected readonly reactionNetworkSummary = computed(
    () => this.reactionNetworkQuery.data()?.summary ?? null,
  )
  protected readonly reactionNetworkUndirectedGraph = computed<AlgorithmGraph | null>(() => {
    const graph = this.reactionNetworkGraph()
    return graph ? asUndirectedGraph(graph) : null
  })
  protected readonly reactionNetworkTopologicalTrace = computed<GraphTraceResult | null>(() => {
    const graph = this.reactionNetworkGraph()
    return graph ? buildTopologicalSortTrace(graph) : null
  })
  protected readonly reactionNetworkMetrics = computed<MolecularGraphMetrics | null>(() => {
    const graph = this.reactionNetworkUndirectedGraph()
    return graph ? buildMolecularGraphMetrics(graph) : null
  })
  protected readonly reactionNetworkLaplacianAnalysis = computed<MatrixAnalysis | null>(() => {
    const graph = this.reactionNetworkUndirectedGraph()
    return graph ? buildLaplacianAnalysis(graph) : null
  })
  protected readonly reactionNetworkMatrixHeader = computed(() => {
    return this.reactionNetworkUndirectedGraph()?.nodes.map((node) => node.label) ?? []
  })
  protected readonly reactionNetworkLaplacianRows = computed(() => {
    const header = this.reactionNetworkMatrixHeader()
    const matrix = this.reactionNetworkLaplacianAnalysis()?.laplacianMatrix ?? []
    return matrix.map((values, index) => ({
      label: header[index] ?? String(index + 1),
      values,
    }))
  })
  protected readonly reactionNetworkOrderLabels = computed(() => {
    const trace = this.reactionNetworkTopologicalTrace()
    const graph = this.reactionNetworkGraph()
    if (!trace || !graph) {
      return []
    }

    const labelById = new Map(graph.nodes.map((node) => [node.id, node.label]))
    return trace.order.map((nodeId) => labelById.get(nodeId) ?? nodeId)
  })
  protected readonly laplacianAnalysis = computed<MatrixAnalysis | null>(() => {
    const graph = this.moleculeGraph()
    return graph ? buildLaplacianAnalysis(graph) : null
  })
  protected readonly morganAnalysis = computed<MorganAnalysisResult | null>(() => {
    const graph = this.moleculeGraph()
    return graph ? buildMorganAnalysis(graph, 4) : null
  })
  protected readonly matrixHeader = computed(() => {
    return this.moleculeGraph()?.nodes.map((node) => node.label) ?? []
  })
  protected readonly laplacianRows = computed(() => {
    const header = this.matrixHeader()
    const matrix = this.laplacianAnalysis()?.laplacianMatrix ?? []
    return matrix.map((values, index) => ({
      label: header[index] ?? String(index + 1),
      values,
    }))
  })

  protected readonly bioactivityValues = computed(
    () => this.bioactivityQuery.data()?.records.map((record) => record.activityValue) ?? [],
  )
  protected readonly mergeSortTrace = computed(() => buildMergeSortTrace(this.bioactivityValues()))
  protected readonly quickSortTrace = computed(() => buildQuickSortTrace(this.bioactivityValues()))
  protected readonly activeSortTrace = computed(() =>
    this.sortAlgorithm() === "merge-sort" ? this.mergeSortTrace() : this.quickSortTrace(),
  )
  protected readonly activeSortStep = computed(() => {
    const trace = this.activeSortTrace()
    return trace.steps[this.sortStepIndex()] ?? null
  })
  protected readonly binarySearchTrace = computed<BinarySearchTraceResult>(() => {
    return buildThresholdBinarySearchTrace(this.mergeSortTrace().sortedValues, 100)
  })

  constructor() {
    effect(
      () => {
        const steps = this.activeGraphTrace()?.steps.length ?? 0
        const maxIndex = Math.max(0, steps - 1)

        if (this.graphStepIndex() > maxIndex) {
          this.graphStepIndex.set(maxIndex)
        }
      },
      { allowSignalWrites: true },
    )

    effect(
      () => {
        const steps = this.activeSortTrace().steps.length
        const maxIndex = Math.max(0, steps - 1)

        if (this.sortStepIndex() > maxIndex) {
          this.sortStepIndex.set(maxIndex)
        }
      },
      { allowSignalWrites: true },
    )
  }

  protected selectGraphScenario(scenario: GraphScenario): void {
    this.graphScenario.set(scenario)
    this.graphStepIndex.set(0)
  }

  protected stepGraphBackward(): void {
    this.graphStepIndex.update((value) => Math.max(0, value - 1))
  }

  protected stepGraphForward(): void {
    const stepCount = this.activeGraphTrace()?.steps.length ?? 0
    this.graphStepIndex.update((value) => Math.min(Math.max(0, stepCount - 1), value + 1))
  }

  protected selectSortAlgorithm(algorithm: SortAlgorithm): void {
    this.sortAlgorithm.set(algorithm)
    this.sortStepIndex.set(0)
  }

  protected stepSortBackward(): void {
    this.sortStepIndex.update((value) => Math.max(0, value - 1))
  }

  protected stepSortForward(): void {
    const stepCount = this.activeSortTrace().steps.length
    this.sortStepIndex.update((value) => Math.min(Math.max(0, stepCount - 1), value + 1))
  }

  protected formatScenarioLabel(scenario: GraphScenario): string {
    switch (scenario) {
      case "bfs":
        return "BFS"
      case "dfs":
        return "DFS"
      case "weighted-shortest-path":
        return "Weighted path"
      case "shortest-path":
        return "Shortest path"
      case "morgan-labeling":
        return "Morgan labels"
      case "cycle-detection":
        return "Cycle detection"
      case "minimum-spanning-tree":
        return "MST"
      case "topological-sort":
        return "Topological sort"
    }
  }

  protected formatSortLabel(algorithm: SortAlgorithm): string {
    return algorithm === "merge-sort" ? "Merge sort" : "Quick sort"
  }

  protected sortBarHeight(value: number): number {
    const values = this.bioactivityValues()
    const max = Math.max(...values, 1)
    return (value / max) * 100
  }

  protected formatMorganLabels(labels: Record<string, number>): string {
    return Object.entries(labels)
      .map(([nodeId, value]) => `${nodeId}:${value}`)
      .join(" · ")
  }
}

async function fetchJson(url: string): Promise<unknown> {
  const response = await fetch(url)

  if (!response.ok) {
    throw new Error(`Request failed with status ${response.status}`)
  }

  return response.json() as Promise<unknown>
}

async function fetchMolecule(): Promise<MoleculeGraph> {
  return parseConformerPayload(await fetchJson("/api/cid4/conformer/1"))
}

async function fetchPathway(): Promise<AlgorithmGraph> {
  const payload = (await fetchJson("/api/algorithms/pathway")) as PathwayResponse
  return payload.graph
}

async function fetchReactionNetwork(): Promise<ReactionNetworkResponse> {
  return (await fetchJson("/api/algorithms/reaction-network")) as ReactionNetworkResponse
}

async function fetchBioactivity(): Promise<BioactivityResponse> {
  return (await fetchJson("/api/algorithms/bioactivity")) as BioactivityResponse
}

async function fetchTaxonomy(): Promise<TaxonomyResponse> {
  return (await fetchJson("/api/algorithms/taxonomy")) as TaxonomyResponse
}

function mapMoleculeToAlgorithmGraph(molecule: MoleculeGraph): AlgorithmGraph {
  const positions = normalizePositions(buildLayoutPositions(molecule, "source"))

  return {
    id: `molecule-${molecule.cid}`,
    title: molecule.title,
    directed: false,
    nodes: molecule.atoms.map((atom) => ({
      id: String(atom.id),
      label: `${atom.elementSymbol}${atom.id}`,
      x: positions.get(atom.id)?.x,
      y: positions.get(atom.id)?.y,
    })),
    edges: molecule.bonds.map((bond) => ({
      id: bond.id,
      label: String(bond.order),
      source: String(bond.source),
      target: String(bond.target),
      weight: 1,
    })),
  }
}

function buildCompleteDistanceGraph(molecule: MoleculeGraph): AlgorithmGraph {
  const positions = normalizePositions(buildLayoutPositions(molecule, "source"))
  const nodes = molecule.atoms.map((atom) => ({
    id: String(atom.id),
    label: `${atom.elementSymbol}${atom.id}`,
    x: positions.get(atom.id)?.x,
    y: positions.get(atom.id)?.y,
  }))
  const edges = molecule.atoms.flatMap((sourceAtom, sourceIndex) => {
    return molecule.atoms.slice(sourceIndex + 1).map((targetAtom) => ({
      id: `${sourceAtom.id}-${targetAtom.id}`,
      source: String(sourceAtom.id),
      target: String(targetAtom.id),
      label: euclideanDistance(sourceAtom, targetAtom).toFixed(2),
      weight: euclideanDistance(sourceAtom, targetAtom),
    }))
  })

  return {
    id: `complete-${molecule.cid}`,
    title: `${molecule.title} complete distance graph`,
    directed: false,
    nodes,
    edges,
  }
}

function buildWeightedBondGraph(molecule: MoleculeGraph): AlgorithmGraph {
  const positions = normalizePositions(buildLayoutPositions(molecule, "source"))
  const atomsById = new Map(molecule.atoms.map((atom) => [atom.id, atom]))

  return {
    id: `weighted-bonds-${molecule.cid}`,
    title: `${molecule.title} weighted bond graph`,
    directed: false,
    nodes: molecule.atoms.map((atom) => ({
      id: String(atom.id),
      label: `${atom.elementSymbol}${atom.id}`,
      x: positions.get(atom.id)?.x,
      y: positions.get(atom.id)?.y,
    })),
    edges: molecule.bonds.map((bond) => {
      const source = atomsById.get(bond.source)
      const target = atomsById.get(bond.target)
      const weight = source && target ? euclideanDistance(source, target) : 1

      return {
        id: bond.id,
        label: weight.toFixed(2),
        source: String(bond.source),
        target: String(bond.target),
        weight,
      }
    }),
  }
}

function asUndirectedGraph(graph: AlgorithmGraph): AlgorithmGraph {
  return {
    ...graph,
    directed: false,
  }
}

function buildMorganTrace(graph: AlgorithmGraph): GraphTraceResult {
  const analysis = buildMorganAnalysis(graph, 4)
  const finalRound = analysis.rounds.at(-1)

  return {
    algorithm: "Morgan label propagation",
    headline: `Stabilized after round ${analysis.stabilizedAfterRound}`,
    detail:
      "Each round re-labels atoms from their local neighborhoods to approximate the intuition behind circular fingerprints.",
    order: analysis.rounds.map((round) => `Round ${round.round}`),
    steps: analysis.rounds.map((round) => ({
      label: `Round ${round.round}`,
      detail: `Labels ${formatMorganRound(round.labels)}. Changed nodes: ${round.changedNodeIds.join(", ") || "None"}.`,
      activeNodeIds: round.changedNodeIds,
      activeEdgeIds: [],
      visitedNodeIds: graph.nodes.map((node) => node.id),
      frontierNodeIds: [],
      pathNodeIds: [],
      pathEdgeIds: [],
    })),
    metrics: {
      stabilizedAfterRound: analysis.stabilizedAfterRound,
      distinctLabels: new Set(Object.values(finalRound?.labels ?? {})).size,
    },
  }
}

function normalizePositions(points: Map<number, Point>): Map<number, Point> {
  const entries = [...points.entries()]

  if (entries.length === 0) {
    return new Map()
  }

  const xValues = entries.map(([, point]) => point.x)
  const yValues = entries.map(([, point]) => point.y)
  const minX = Math.min(...xValues)
  const maxX = Math.max(...xValues)
  const minY = Math.min(...yValues)
  const maxY = Math.max(...yValues)
  const width = maxX - minX || 1
  const height = maxY - minY || 1

  return new Map(
    entries.map(([id, point]) => [
      id,
      {
        x: 80 + ((point.x - minX) / width) * 520,
        y: 60 + ((point.y - minY) / height) * 300,
      },
    ]),
  )
}

function euclideanDistance(
  left: MoleculeGraph["atoms"][number],
  right: MoleculeGraph["atoms"][number],
): number {
  const dx = left.x - right.x
  const dy = left.y - right.y
  const dz = left.z - right.z
  return Math.hypot(dx, dy, dz)
}

function humanizeMetricLabel(label: string): string {
  return label.replaceAll(/([A-Z])/g, " $1").replace(/^./, (value) => value.toUpperCase())
}

function formatMorganRound(labels: Record<string, number>): string {
  return Object.entries(labels)
    .map(([nodeId, value]) => `${nodeId}:${value}`)
    .join(", ")
}

function emptyGraph(id: string): AlgorithmGraph {
  return {
    id,
    title: id,
    directed: false,
    nodes: [],
    edges: [],
  }
}
