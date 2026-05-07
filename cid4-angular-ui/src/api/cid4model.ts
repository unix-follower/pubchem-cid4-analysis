import { AlgorithmGraph } from "@/app/core/algorithms/types"

export interface PathwayResponse {
  graph: AlgorithmGraph
}

export interface ReactionNetworkSummary {
  pathwayCount: number
  reactionCount: number
  compoundCount: number
  taxonomyCount: number
  edgeCount: number
  cid4ParticipationEdgeCount: number
}

export interface ReactionNetworkResponse {
  graph: AlgorithmGraph
  summary: ReactionNetworkSummary
}

export interface BioactivityRecord {
  aid: number
  assay: string
  activityValue: number
}

export interface BioactivityResponse {
  records: BioactivityRecord[]
}

export interface TaxonomyRecord {
  taxonomyId: number
  sourceOrganism: string
}

export interface TaxonomyResponse {
  organisms: TaxonomyRecord[]
}
