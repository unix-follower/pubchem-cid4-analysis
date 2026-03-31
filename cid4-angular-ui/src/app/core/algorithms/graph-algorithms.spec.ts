import {
  buildLaplacianAnalysis,
  buildMolecularGraphMetrics,
  buildMorganAnalysis,
  buildShortestPathTrace,
} from "./graph-algorithms"
import { AlgorithmGraph } from "./types"

describe("graph-algorithms", () => {
  it("computes degree sequence, density, eccentricity, and diameter", () => {
    const graph: AlgorithmGraph = {
      id: "path-3",
      title: "Path graph",
      directed: false,
      nodes: [
        { id: "1", label: "A" },
        { id: "2", label: "B" },
        { id: "3", label: "C" },
      ],
      edges: [
        { id: "1-2", source: "1", target: "2" },
        { id: "2-3", source: "2", target: "3" },
      ],
    }

    const metrics = buildMolecularGraphMetrics(graph)

    expect(metrics.degreeSequence).toEqual([2, 1, 1])
    expect(metrics.density).toBeCloseTo(0.67, 2)
    expect(metrics.diameter).toBe(2)
    expect(metrics.radius).toBe(1)
    expect(metrics.centerNodeIds).toEqual(["2"])
    expect(metrics.nodeMetrics).toEqual([
      { nodeId: "1", label: "A", degree: 1, eccentricity: 2 },
      { nodeId: "2", label: "B", degree: 2, eccentricity: 1 },
      { nodeId: "3", label: "C", degree: 1, eccentricity: 2 },
    ])
  })

  it("builds Laplacian matrices and a positive Fiedler value for a connected graph", () => {
    const graph: AlgorithmGraph = {
      id: "path-3",
      title: "Path graph",
      directed: false,
      nodes: [
        { id: "1", label: "A" },
        { id: "2", label: "B" },
        { id: "3", label: "C" },
      ],
      edges: [
        { id: "1-2", source: "1", target: "2" },
        { id: "2-3", source: "2", target: "3" },
      ],
    }

    const analysis = buildLaplacianAnalysis(graph)

    expect(analysis.adjacencyMatrix).toEqual([
      [0, 1, 0],
      [1, 0, 1],
      [0, 1, 0],
    ])
    expect(analysis.laplacianMatrix).toEqual([
      [1, -1, 0],
      [-1, 2, -1],
      [0, -1, 1],
    ])
    expect(analysis.eigenvalues).toEqual([0, 1, 3])
    expect(analysis.fiedlerValue).toBe(1)
  })

  it("propagates Morgan labels until stabilization", () => {
    const graph: AlgorithmGraph = {
      id: "star",
      title: "Star graph",
      directed: false,
      nodes: [
        { id: "1", label: "Center" },
        { id: "2", label: "Leaf 1" },
        { id: "3", label: "Leaf 2" },
      ],
      edges: [
        { id: "1-2", source: "1", target: "2" },
        { id: "1-3", source: "1", target: "3" },
      ],
    }

    const analysis = buildMorganAnalysis(graph, 4)

    expect(analysis.rounds[0].labels).toEqual({ "1": 2, "2": 1, "3": 1 })
    expect(analysis.rounds[1].labels).toEqual({ "1": 2, "2": 1, "3": 1 })
    expect(analysis.rounds[1].changedNodeIds).toEqual([])
    expect(analysis.stabilizedAfterRound).toBe(1)
  })

  it("uses bond weights for shortest path selection", () => {
    const graph: AlgorithmGraph = {
      id: "weighted",
      title: "Weighted path graph",
      directed: false,
      nodes: [
        { id: "1", label: "A" },
        { id: "2", label: "B" },
        { id: "3", label: "C" },
      ],
      edges: [
        { id: "1-2", source: "1", target: "2", weight: 5 },
        { id: "1-3", source: "1", target: "3", weight: 1 },
        { id: "3-2", source: "3", target: "2", weight: 1 },
      ],
    }

    const trace = buildShortestPathTrace(graph, "1", "2")

    expect(trace.order).toEqual(["1", "3", "2"])
    expect(trace.metrics?.["pathCost"]).toBe(2)
  })
})
