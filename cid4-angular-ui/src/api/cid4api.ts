import { AlgorithmGraph } from "@/app/core/algorithms/types"
import {
  parseCompoundRecordPayload,
  parseStructurePayload,
  parseConformerPayload,
} from "@/app/core/cid4/parser"
import { CompoundRecord, MoleculeGraph } from "@/app/core/cid4/types"

import {
  PathwayResponse,
  ReactionNetworkResponse,
  BioactivityResponse,
  TaxonomyResponse,
} from "./cid4model"

export type MoleculeDatasetId =
  | "structure-2d"
  | "conformer-1"
  | "conformer-2"
  | "conformer-3"
  | "conformer-4"
  | "conformer-5"
  | "conformer-6"

interface MoleculeDatasetOption {
  id: MoleculeDatasetId
  label: string
  url: string
  parser: (payload: unknown) => MoleculeGraph
}

export const MOLECULE_DATASETS: MoleculeDatasetOption[] = [
  {
    id: "structure-2d",
    label: "Structure2D",
    url: "/api/cid4/structure/2d",
    parser: parseStructurePayload,
  },
  {
    id: "conformer-1",
    label: "Conformer 1",
    url: "/api/cid4/conformer/1",
    parser: parseConformerPayload,
  },
  {
    id: "conformer-2",
    label: "Conformer 2",
    url: "/api/cid4/conformer/2",
    parser: parseConformerPayload,
  },
  {
    id: "conformer-3",
    label: "Conformer 3",
    url: "/api/cid4/conformer/3",
    parser: parseConformerPayload,
  },
  {
    id: "conformer-4",
    label: "Conformer 4",
    url: "/api/cid4/conformer/4",
    parser: parseConformerPayload,
  },
  {
    id: "conformer-5",
    label: "Conformer 5",
    url: "/api/cid4/conformer/5",
    parser: parseConformerPayload,
  },
  {
    id: "conformer-6",
    label: "Conformer 6",
    url: "/api/cid4/conformer/6",
    parser: parseConformerPayload,
  },
]

async function fetchJson(url: string): Promise<unknown> {
  const response = await fetch(url)

  if (!response.ok) {
    throw new Error(`Request failed with status ${response.status}`)
  }

  return response.json() as Promise<unknown>
}

export async function fetchPathway(): Promise<AlgorithmGraph> {
  const payload = (await fetchJson("/api/algorithms/pathway")) as PathwayResponse
  return payload.graph
}

export async function fetchReactionNetwork(): Promise<ReactionNetworkResponse> {
  return (await fetchJson("/api/algorithms/reaction-network")) as ReactionNetworkResponse
}

export async function fetchBioactivity(): Promise<BioactivityResponse> {
  return (await fetchJson("/api/algorithms/bioactivity")) as BioactivityResponse
}

export async function fetchTaxonomy(): Promise<TaxonomyResponse> {
  return (await fetchJson("/api/algorithms/taxonomy")) as TaxonomyResponse
}

export async function fetchMoleculeDataset(datasetId: MoleculeDatasetId): Promise<MoleculeGraph> {
  const dataset = MOLECULE_DATASETS.find((option) => option.id === datasetId)

  if (!dataset) {
    throw new Error(`Unknown dataset ${datasetId}`)
  }

  return dataset.parser(await fetchJson(dataset.url))
}

export async function fetchCompoundRecord(): Promise<CompoundRecord> {
  return parseCompoundRecordPayload(await fetchJson("/api/cid4/compound"))
}

export async function fetchMolecule(): Promise<MoleculeGraph> {
  return parseConformerPayload(await fetchJson("/api/cid4/conformer/1"))
}
