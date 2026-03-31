import { AlgorithmGraph, AlgorithmGraphEdge, GraphTraceResult, GraphTraceStep } from "./types"

interface Neighbor {
  nodeId: string
  edgeId: string
  weight: number
}

type VisitColor = 0 | 1 | 2

export function buildBfsTrace(graph: AlgorithmGraph, startNodeId: string): GraphTraceResult {
  const adjacency = buildAdjacency(graph)
  const visited = new Set<string>()
  const queue: string[] = [startNodeId]
  const order: string[] = []
  const steps: GraphTraceStep[] = [
    buildStep("Seed queue", `Start BFS at ${startNodeId}.`, {
      frontierNodeIds: queue,
    }),
  ]

  while (queue.length > 0) {
    const current = queue.shift()

    if (!current || visited.has(current)) {
      continue
    }

    visited.add(current)
    order.push(current)
    steps.push(
      buildStep("Visit node", `Dequeued ${current} and marked it visited.`, {
        activeNodeIds: [current],
        visitedNodeIds: [...visited],
        frontierNodeIds: queue,
      }),
    )

    for (const neighbor of adjacency.get(current) ?? []) {
      if (visited.has(neighbor.nodeId) || queue.includes(neighbor.nodeId)) {
        continue
      }

      queue.push(neighbor.nodeId)
      steps.push(
        buildStep("Enqueue neighbor", `Queued ${neighbor.nodeId} from ${current}.`, {
          activeNodeIds: [current, neighbor.nodeId],
          activeEdgeIds: [neighbor.edgeId],
          visitedNodeIds: [...visited],
          frontierNodeIds: queue,
        }),
      )
    }
  }

  return {
    algorithm: "Breadth-first search",
    headline: `BFS order from ${startNodeId}: ${order.join(" -> ")}`,
    detail: "Level-order traversal over the molecular graph using a FIFO queue.",
    order,
    steps,
    metrics: {
      visitedCount: order.length,
    },
  }
}

export function buildDfsTrace(graph: AlgorithmGraph, startNodeId: string): GraphTraceResult {
  const adjacency = buildAdjacency(graph)
  const visited = new Set<string>()
  const order: string[] = []
  const backEdges = new Set<string>()
  const steps: GraphTraceStep[] = []

  const walk = (nodeId: string, parentId: string | null): void => {
    visited.add(nodeId)
    order.push(nodeId)
    steps.push(
      buildStep("Enter node", `DFS entered ${nodeId}.`, {
        activeNodeIds: [nodeId],
        visitedNodeIds: [...visited],
      }),
    )

    for (const neighbor of adjacency.get(nodeId) ?? []) {
      if (neighbor.nodeId === parentId) {
        continue
      }

      if (visited.has(neighbor.nodeId)) {
        backEdges.add(neighbor.edgeId)
        steps.push(
          buildStep(
            "Back edge",
            `Encountered visited neighbor ${neighbor.nodeId} from ${nodeId}.`,
            {
              activeNodeIds: [nodeId, neighbor.nodeId],
              activeEdgeIds: [neighbor.edgeId],
              visitedNodeIds: [...visited],
            },
          ),
        )
        continue
      }

      steps.push(
        buildStep("Traverse edge", `Recursing from ${nodeId} to ${neighbor.nodeId}.`, {
          activeNodeIds: [nodeId, neighbor.nodeId],
          activeEdgeIds: [neighbor.edgeId],
          visitedNodeIds: [...visited],
        }),
      )
      walk(neighbor.nodeId, nodeId)
    }
  }

  walk(startNodeId, null)

  return {
    algorithm: "Depth-first search",
    headline: `DFS order from ${startNodeId}: ${order.join(" -> ")}`,
    detail:
      backEdges.size === 0
        ? "No back-edges were found, which matches the expected acyclic carbon chain."
        : `Detected ${backEdges.size} back-edge(s).`,
    order,
    steps,
    metrics: {
      visitedCount: order.length,
      backEdgeCount: backEdges.size,
    },
  }
}

export function buildShortestPathTrace(
  graph: AlgorithmGraph,
  startNodeId: string,
  targetNodeId: string,
): GraphTraceResult {
  const adjacency = buildAdjacency(graph)
  const distances = new Map<string, number>(
    graph.nodes.map((node) => [node.id, Number.POSITIVE_INFINITY]),
  )
  const previous = new Map<string, { nodeId: string; edgeId: string }>()
  const frontier = new Set<string>([startNodeId])
  const visited = new Set<string>()
  const steps: GraphTraceStep[] = []

  distances.set(startNodeId, 0)

  while (frontier.size > 0) {
    const current = [...frontier].sort((left, right) => {
      return (
        (distances.get(left) ?? Number.POSITIVE_INFINITY) -
        (distances.get(right) ?? Number.POSITIVE_INFINITY)
      )
    })[0]

    frontier.delete(current)

    if (visited.has(current)) {
      continue
    }

    visited.add(current)
    steps.push(
      buildStep("Settle node", `Selected ${current} with distance ${distances.get(current)}.`, {
        activeNodeIds: [current],
        visitedNodeIds: [...visited],
        frontierNodeIds: [...frontier],
      }),
    )

    if (current === targetNodeId) {
      break
    }

    for (const neighbor of adjacency.get(current) ?? []) {
      const candidateDistance =
        (distances.get(current) ?? Number.POSITIVE_INFINITY) + neighbor.weight

      if (candidateDistance >= (distances.get(neighbor.nodeId) ?? Number.POSITIVE_INFINITY)) {
        continue
      }

      distances.set(neighbor.nodeId, candidateDistance)
      previous.set(neighbor.nodeId, { nodeId: current, edgeId: neighbor.edgeId })
      frontier.add(neighbor.nodeId)
      steps.push(
        buildStep(
          "Relax edge",
          `Updated ${neighbor.nodeId} to distance ${roundMetric(candidateDistance)} via ${current}.`,
          {
            activeNodeIds: [current, neighbor.nodeId],
            activeEdgeIds: [neighbor.edgeId],
            visitedNodeIds: [...visited],
            frontierNodeIds: [...frontier],
          },
        ),
      )
    }
  }

  const pathNodeIds: string[] = []
  const pathEdgeIds: string[] = []
  let cursor: string | undefined = targetNodeId

  while (cursor) {
    pathNodeIds.unshift(cursor)
    const link = previous.get(cursor)

    if (!link) {
      break
    }

    pathEdgeIds.unshift(link.edgeId)
    cursor = link.nodeId
  }

  steps.push(
    buildStep(
      "Resolve path",
      `Shortest path ${pathNodeIds.join(" -> ")} with cost ${roundMetric(distances.get(targetNodeId) ?? 0)}.`,
      {
        visitedNodeIds: [...visited],
        pathNodeIds,
        pathEdgeIds,
      },
    ),
  )

  return {
    algorithm: "Shortest path",
    headline: `${startNodeId} to ${targetNodeId}: ${pathNodeIds.join(" -> ")}`,
    detail:
      "Dijkstra degenerates to BFS-style behavior on unit-weight bond edges but remains ready for weighted bond lengths.",
    order: pathNodeIds,
    steps,
    metrics: {
      pathCost: roundMetric(distances.get(targetNodeId) ?? 0),
      hopCount: Math.max(0, pathNodeIds.length - 1),
    },
  }
}

export function buildCycleDetectionTrace(
  graph: AlgorithmGraph,
  startNodeId: string,
): GraphTraceResult {
  const adjacency = buildAdjacency(graph)
  const color = new Map<string, VisitColor>(graph.nodes.map((node) => [node.id, 0]))
  const steps: GraphTraceStep[] = []
  let hasCycle = false

  const walk = (nodeId: string, parentId: string | null): void => {
    if (hasCycle) {
      return
    }

    color.set(nodeId, 1)
    steps.push(
      buildStep("Gray node", `Marked ${nodeId} gray while exploring its neighbors.`, {
        activeNodeIds: [nodeId],
        frontierNodeIds: grayNodes(color),
        visitedNodeIds: blackNodes(color),
      }),
    )

    for (const neighbor of adjacency.get(nodeId) ?? []) {
      if (neighbor.nodeId === parentId) {
        continue
      }

      const neighborColor = color.get(neighbor.nodeId) ?? 0

      if (neighborColor === 1) {
        hasCycle = true
        steps.push(
          buildStep(
            "Cycle found",
            `Edge ${neighbor.edgeId} closes a cycle between ${nodeId} and ${neighbor.nodeId}.`,
            {
              activeNodeIds: [nodeId, neighbor.nodeId],
              activeEdgeIds: [neighbor.edgeId],
              frontierNodeIds: grayNodes(color),
              visitedNodeIds: blackNodes(color),
            },
          ),
        )
        return
      }

      if (neighborColor === 0) {
        walk(neighbor.nodeId, nodeId)
      }
    }

    color.set(nodeId, 2)
    steps.push(
      buildStep("Black node", `Finished ${nodeId}; no cycle found through this branch.`, {
        activeNodeIds: [nodeId],
        frontierNodeIds: grayNodes(color),
        visitedNodeIds: blackNodes(color),
      }),
    )
  }

  walk(startNodeId, null)

  return {
    algorithm: "Cycle detection",
    headline: hasCycle ? "Cycle detected" : "Graph is acyclic",
    detail: hasCycle
      ? "A gray-to-gray edge indicates a cycle."
      : "The molecule stays acyclic under DFS coloring, which matches 1-amino-2-propanol.",
    order: [],
    steps,
    metrics: {
      hasCycle,
    },
  }
}

export function buildTopologicalSortTrace(graph: AlgorithmGraph): GraphTraceResult {
  const inDegree = new Map<string, number>(graph.nodes.map((node) => [node.id, 0]))

  for (const edge of graph.edges) {
    inDegree.set(edge.target, (inDegree.get(edge.target) ?? 0) + 1)
  }

  const queue = [
    ...graph.nodes.map((node) => node.id).filter((id) => (inDegree.get(id) ?? 0) === 0),
  ]
  const order: string[] = []
  const steps: GraphTraceStep[] = [
    buildStep("Seed queue", `Nodes with zero in-degree: ${queue.join(", ")}.`, {
      frontierNodeIds: queue,
    }),
  ]

  while (queue.length > 0) {
    const current = queue.shift()

    if (!current) {
      continue
    }

    order.push(current)
    steps.push(
      buildStep("Emit node", `Placed ${current} into the topological order.`, {
        activeNodeIds: [current],
        visitedNodeIds: order,
        frontierNodeIds: queue,
      }),
    )

    for (const edge of graph.edges.filter((candidate) => candidate.source === current)) {
      const nextDegree = (inDegree.get(edge.target) ?? 1) - 1
      inDegree.set(edge.target, nextDegree)

      steps.push(
        buildStep(
          "Drop in-degree",
          `Edge ${edge.id} reduces ${edge.target} to in-degree ${nextDegree}.`,
          {
            activeNodeIds: [current, edge.target],
            activeEdgeIds: [edge.id],
            visitedNodeIds: order,
            frontierNodeIds: queue,
          },
        ),
      )

      if (nextDegree === 0) {
        queue.push(edge.target)
      }
    }
  }

  return {
    algorithm: "Topological sort",
    headline: `Topological order: ${order.join(" -> ")}`,
    detail:
      order.length === graph.nodes.length
        ? "Kahn's algorithm produced a valid DAG ordering for the pathway steps."
        : "The graph still contains a cycle, so no full topological ordering exists.",
    order,
    steps,
    metrics: {
      emittedCount: order.length,
      nodeCount: graph.nodes.length,
    },
  }
}

export function buildMinimumSpanningTreeTrace(graph: AlgorithmGraph): GraphTraceResult {
  const parent = new Map<string, string>(graph.nodes.map((node) => [node.id, node.id]))
  const rank = new Map<string, number>(graph.nodes.map((node) => [node.id, 0]))
  const sortedEdges = [...graph.edges].sort(
    (left, right) => (left.weight ?? 1) - (right.weight ?? 1),
  )
  const chosenEdges: AlgorithmGraphEdge[] = []
  const chosenNodes = new Set<string>()
  const steps: GraphTraceStep[] = []

  const find = (nodeId: string): string => {
    const root = parent.get(nodeId) ?? nodeId

    if (root === nodeId) {
      return root
    }

    const collapsed = find(root)
    parent.set(nodeId, collapsed)
    return collapsed
  }

  const union = (left: string, right: string): boolean => {
    const leftRoot = find(left)
    const rightRoot = find(right)

    if (leftRoot === rightRoot) {
      return false
    }

    const leftRank = rank.get(leftRoot) ?? 0
    const rightRank = rank.get(rightRoot) ?? 0

    if (leftRank < rightRank) {
      parent.set(leftRoot, rightRoot)
    } else if (leftRank > rightRank) {
      parent.set(rightRoot, leftRoot)
    } else {
      parent.set(rightRoot, leftRoot)
      rank.set(leftRoot, leftRank + 1)
    }

    return true
  }

  for (const edge of sortedEdges) {
    const accepted = union(edge.source, edge.target)

    steps.push(
      buildStep(
        accepted ? "Accept edge" : "Reject edge",
        accepted
          ? `Accepted ${edge.id} with weight ${roundMetric(edge.weight ?? 0)}.`
          : `Rejected ${edge.id} because it would close a cycle.`,
        {
          activeNodeIds: [edge.source, edge.target],
          activeEdgeIds: [edge.id],
          pathNodeIds: [...chosenNodes],
          pathEdgeIds: chosenEdges.map((candidate) => candidate.id),
        },
      ),
    )

    if (!accepted) {
      continue
    }

    chosenEdges.push(edge)
    chosenNodes.add(edge.source)
    chosenNodes.add(edge.target)

    if (chosenEdges.length === Math.max(0, graph.nodes.length - 1)) {
      break
    }
  }

  const treeGraph: AlgorithmGraph = {
    ...graph,
    edges: chosenEdges,
  }
  const totalWeight = chosenEdges.reduce((sum, edge) => sum + (edge.weight ?? 0), 0)

  steps.push(
    buildStep("Finalize tree", `Built an MST with total weight ${roundMetric(totalWeight)}.`, {
      pathNodeIds: [...chosenNodes],
      pathEdgeIds: chosenEdges.map((edge) => edge.id),
    }),
  )

  return {
    algorithm: "Minimum spanning tree",
    headline: `${chosenEdges.length} edges selected with total weight ${roundMetric(totalWeight)}`,
    detail:
      "Kruskal ran over the complete inter-atom distance graph and kept the cheapest acyclic scaffold.",
    order: chosenEdges.map((edge) => edge.id),
    steps,
    graph: treeGraph,
    metrics: {
      edgeCount: chosenEdges.length,
      totalWeight: roundMetric(totalWeight),
    },
  }
}

function buildAdjacency(graph: AlgorithmGraph): Map<string, Neighbor[]> {
  const adjacency = new Map<string, Neighbor[]>()

  for (const node of graph.nodes) {
    adjacency.set(node.id, [])
  }

  for (const edge of graph.edges) {
    adjacency.get(edge.source)?.push({
      nodeId: edge.target,
      edgeId: edge.id,
      weight: edge.weight ?? 1,
    })

    if (!graph.directed) {
      adjacency.get(edge.target)?.push({
        nodeId: edge.source,
        edgeId: edge.id,
        weight: edge.weight ?? 1,
      })
    }
  }

  for (const neighbors of adjacency.values()) {
    neighbors.sort((left, right) =>
      left.nodeId.localeCompare(right.nodeId, undefined, { numeric: true }),
    )
  }

  return adjacency
}

function buildStep(
  label: string,
  detail: string,
  state: Partial<Omit<GraphTraceStep, "label" | "detail">>,
): GraphTraceStep {
  return {
    label,
    detail,
    activeNodeIds: state.activeNodeIds ?? [],
    activeEdgeIds: state.activeEdgeIds ?? [],
    visitedNodeIds: state.visitedNodeIds ?? [],
    frontierNodeIds: state.frontierNodeIds ?? [],
    pathNodeIds: state.pathNodeIds ?? [],
    pathEdgeIds: state.pathEdgeIds ?? [],
  }
}

function grayNodes(color: Map<string, VisitColor>): string[] {
  return [...color.entries()].filter(([, value]) => value === 1).map(([key]) => key)
}

function blackNodes(color: Map<string, VisitColor>): string[] {
  return [...color.entries()].filter(([, value]) => value === 2).map(([key]) => key)
}

function roundMetric(value: number): number {
  return Number(value.toFixed(3))
}
