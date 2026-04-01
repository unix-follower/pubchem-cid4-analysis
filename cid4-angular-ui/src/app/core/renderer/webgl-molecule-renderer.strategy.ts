import type { GLViewer } from "3dmol"

import { MoleculeGraph } from "../cid4/types"
import { MoleculeRendererStrategy } from "./renderer.strategy"
import { MoleculeRenderOptions, RendererMetrics } from "./renderer.types"

export class WebGlMoleculeRendererStrategy extends MoleculeRendererStrategy {
  readonly kind = "webgl" as const

  private host: HTMLElement | null = null
  private container: HTMLDivElement | null = null
  private viewer: GLViewer | null = null

  async initialize(host: HTMLElement, options: MoleculeRenderOptions): Promise<void> {
    if (typeof window === "undefined") {
      throw new Error("WebGL rendering is only available in the browser")
    }

    this.host = host
    this.host.innerHTML = ""
    this.container = document.createElement("div")
    this.container.className = "renderer-surface"
    this.container.style.width = "100%"
    this.container.style.minHeight = "420px"
    this.container.style.borderRadius = "24px"
    this.container.style.overflow = "hidden"
    this.host.appendChild(this.container)

    const library = await import("3dmol")
    this.viewer = library.createViewer(this.container, {
      backgroundColor: options.backgroundColor,
    })
  }

  async render(
    molecule: MoleculeGraph,
    options: MoleculeRenderOptions,
    _comparisonReference?: MoleculeGraph | null,
  ): Promise<RendererMetrics> {
    if (!this.viewer) {
      throw new Error("WebGL renderer is not initialized")
    }

    const renderStartedAt = performance.now()
    const modelData = buildMolBlock(molecule)

    this.viewer.clear()
    this.viewer.addModel(modelData, "mol")
    this.viewer.setBackgroundColor(options.backgroundColor, 1)
    this.viewer.setStyle({}, { stick: { radius: 0.16 }, sphere: { scale: 0.28 } })
    this.viewer.zoomTo()
    this.viewer.render()

    return {
      lastRenderDurationMs: performance.now() - renderStartedAt,
      renderedAtomCount: molecule.atoms.length,
      renderedBondCount: molecule.bonds.length,
    }
  }

  resetView(): void {
    this.viewer?.zoomTo()
    this.viewer?.render()
  }

  dispose(): void {
    this.viewer?.clear()
    this.host?.replaceChildren()
    this.viewer = null
    this.container = null
    this.host = null
  }
}

function buildMolBlock(molecule: MoleculeGraph): string {
  const header = [molecule.title, "CID4 Angular UI", ""]
  const counts = `${padNumber(molecule.atoms.length, 3)}${padNumber(molecule.bonds.length, 3)}  0  0  0  0            999 V2000`
  const atomLines = molecule.atoms.map((atom) => {
    const x = atom.x.toFixed(4).padStart(10, " ")
    const y = atom.y.toFixed(4).padStart(10, " ")
    const z = atom.z.toFixed(4).padStart(10, " ")
    const symbol = atom.elementSymbol.padEnd(3, " ")

    return `${x}${y}${z} ${symbol} 0  0  0  0  0  0  0  0  0  0  0  0`
  })
  const bondLines = molecule.bonds.map((bond) => {
    return `${padNumber(bond.source, 3)}${padNumber(bond.target, 3)}${padNumber(bond.order, 3)}  0  0  0  0`
  })

  return [...header, counts, ...atomLines, ...bondLines, "M  END"].join("\n")
}

function padNumber(value: number, width: number): string {
  return String(value).padStart(width, " ")
}
