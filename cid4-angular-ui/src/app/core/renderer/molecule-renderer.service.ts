import { Injectable, computed, inject, signal } from "@angular/core"

import { MoleculeGraph } from "../cid4/types"
import { RendererCapabilityService } from "./renderer-capability.service"
import { MoleculeRendererStrategy } from "./renderer.strategy"
import {
  DEFAULT_RENDERER_STATUS,
  DEFAULT_RENDER_OPTIONS,
  EMPTY_RENDERER_METRICS,
  MoleculeRenderOptions,
  RendererKind,
  RendererMetrics,
  RendererSnapshot,
  RendererStatus,
  RendererSwitchOption,
} from "./renderer.types"
import { WebGlMoleculeRendererStrategy } from "./webgl-molecule-renderer.strategy"
import { WebGpuMoleculeRendererStrategy } from "./webgpu-molecule-renderer.strategy"

@Injectable({ providedIn: "root" })
export class MoleculeRendererService {
  readonly currentRenderer = signal<RendererKind>("webgl")
  readonly status = signal<RendererStatus>(DEFAULT_RENDERER_STATUS)
  readonly metrics = signal<RendererMetrics>(EMPTY_RENDERER_METRICS)
  readonly options = signal<MoleculeRenderOptions>(DEFAULT_RENDER_OPTIONS)
  readonly capabilities = computed(() => this.capabilityService.capabilities())
  readonly switchOptions = computed<RendererSwitchOption[]>(() => {
    const capabilities = this.capabilities()

    return [
      { kind: "webgl", label: "WebGL", supported: capabilities.webgl },
      { kind: "webgpu", label: "WebGPU", supported: capabilities.webgpu },
    ]
  })

  private readonly capabilityService = inject(RendererCapabilityService)

  private host: HTMLElement | null = null
  private strategy: MoleculeRendererStrategy | null = null
  private snapshot: RendererSnapshot | null = null

  async attachHost(host: HTMLElement): Promise<void> {
    this.host = host

    const capabilities = await this.capabilityService.detectCapabilities()
    const requestedRenderer = capabilities.supportedRenderers.includes(this.currentRenderer())
      ? this.currentRenderer()
      : capabilities.preferredRenderer

    this.currentRenderer.set(requestedRenderer)
    await this.initializeRenderer(requestedRenderer)
  }

  async setMolecule(molecule: MoleculeGraph | null): Promise<void> {
    if (!this.host || !molecule) {
      return
    }

    this.snapshot = {
      host: this.host,
      molecule,
      comparisonReference: this.snapshot?.comparisonReference ?? null,
      options: this.options(),
    }

    await this.renderSnapshot()
  }

  async setComparisonReference(reference: MoleculeGraph | null): Promise<void> {
    if (!this.host || !this.snapshot?.molecule) {
      return
    }

    this.snapshot = {
      host: this.host,
      molecule: this.snapshot.molecule,
      comparisonReference: reference,
      options: this.options(),
    }

    await this.renderSnapshot()
  }

  async switchRenderer(kind: RendererKind): Promise<void> {
    if (!this.host) {
      return
    }

    const capabilities = await this.capabilityService.detectCapabilities()
    const nextRenderer = capabilities.supportedRenderers.includes(kind) ? kind : "webgl"

    this.currentRenderer.set(nextRenderer)

    if (nextRenderer !== kind) {
      this.status.set({
        phase: "fallback",
        message: "WebGPU is unavailable in this browser, so the viewer stayed on WebGL.",
      })
    }

    await this.initializeRenderer(nextRenderer)
    await this.renderSnapshot()
  }

  resetView(): void {
    this.strategy?.resetView()
  }

  dispose(): void {
    this.strategy?.dispose()
    this.strategy = null
    this.host = null
    this.snapshot = null
    this.status.set(DEFAULT_RENDERER_STATUS)
    this.metrics.set(EMPTY_RENDERER_METRICS)
  }

  private async initializeRenderer(kind: RendererKind): Promise<void> {
    if (!this.host) {
      return
    }

    this.status.set({
      phase: "initializing",
      message: `Initializing ${kind.toUpperCase()} renderer…`,
    })
    this.strategy?.dispose()
    this.strategy = null

    try {
      this.strategy =
        kind === "webgpu"
          ? new WebGpuMoleculeRendererStrategy()
          : new WebGlMoleculeRendererStrategy()
      await this.strategy.initialize(this.host, this.options())

      if (kind === "webgpu") {
        this.status.set({
          phase: "ready",
          message: "WebGPU is active. This renderer is still an experimental preview path.",
        })
      } else {
        this.status.set({
          phase: "ready",
          message: "WebGL is active and optimized for compatibility.",
        })
      }
    } catch (error) {
      if (kind === "webgpu") {
        this.currentRenderer.set("webgl")
        this.status.set({
          phase: "fallback",
          message: `${formatRendererError(error)} Falling back to WebGL.`,
        })
        this.strategy = new WebGlMoleculeRendererStrategy()
        await this.strategy.initialize(this.host, this.options())
        return
      }

      this.status.set({ phase: "error", message: formatRendererError(error) })
    }
  }

  private async renderSnapshot(): Promise<void> {
    if (!this.strategy || !this.snapshot) {
      return
    }

    try {
      const metrics = await this.strategy.render(
        this.snapshot.molecule,
        this.snapshot.options,
        this.snapshot.comparisonReference,
      )
      this.metrics.set(metrics)
    } catch (error) {
      this.status.set({ phase: "error", message: formatRendererError(error) })
    }
  }
}

function formatRendererError(error: unknown): string {
  return error instanceof Error ? error.message : "The renderer failed unexpectedly."
}
