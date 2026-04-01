import { MoleculeGraph } from "../cid4/types"

export type RendererKind = "webgl" | "webgpu"

export interface RendererCapabilities {
  webgl: boolean
  webgpu: boolean
  preferredRenderer: RendererKind
  supportedRenderers: RendererKind[]
}

export interface RendererMetrics {
  lastRenderDurationMs: number | null
  renderedAtomCount: number
  renderedBondCount: number
}

export interface RendererStatus {
  phase: "idle" | "initializing" | "ready" | "fallback" | "error"
  message: string | null
}

export interface MoleculeRenderOptions {
  backgroundColor: string
  accentColor: string
}

export interface RendererSwitchOption {
  kind: RendererKind
  label: string
  supported: boolean
}

export interface RendererSnapshot {
  host: HTMLElement
  molecule: MoleculeGraph
  comparisonReference: MoleculeGraph | null
  options: MoleculeRenderOptions
}

export const DEFAULT_RENDER_OPTIONS: MoleculeRenderOptions = {
  backgroundColor: "#f4f7f8",
  accentColor: "#10233d",
}

export const EMPTY_RENDERER_METRICS: RendererMetrics = {
  lastRenderDurationMs: null,
  renderedAtomCount: 0,
  renderedBondCount: 0,
}

export const DEFAULT_RENDERER_STATUS: RendererStatus = {
  phase: "idle",
  message: null,
}
