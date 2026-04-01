import { MoleculeGraph } from "../cid4/types"
import { MoleculeRenderOptions, RendererKind, RendererMetrics } from "./renderer.types"

export abstract class MoleculeRendererStrategy {
  abstract readonly kind: RendererKind

  abstract initialize(host: HTMLElement, options: MoleculeRenderOptions): Promise<void>
  abstract render(
    molecule: MoleculeGraph,
    options: MoleculeRenderOptions,
    comparisonReference?: MoleculeGraph | null,
  ): Promise<RendererMetrics>
  abstract resetView(): void
  abstract dispose(): void
}
