import { Injectable, signal } from "@angular/core"

import { RendererCapabilities } from "./renderer.types"

const DEFAULT_CAPABILITIES: RendererCapabilities = {
  webgl: false,
  webgpu: false,
  preferredRenderer: "webgl",
  supportedRenderers: [],
}

type NavigatorWithGpu = Navigator & {
  gpu?: {
    requestAdapter?: () => Promise<unknown>
  }
}

@Injectable({ providedIn: "root" })
export class RendererCapabilityService {
  readonly capabilities = signal<RendererCapabilities>(DEFAULT_CAPABILITIES)

  private detectionPromise: Promise<RendererCapabilities> | null = null

  detectCapabilities(): Promise<RendererCapabilities> {
    if (this.detectionPromise !== null) {
      return this.detectionPromise
    }

    this.detectionPromise = this.detectInternal()
    return this.detectionPromise
  }

  private async detectInternal(): Promise<RendererCapabilities> {
    if (typeof window === "undefined") {
      this.capabilities.set(DEFAULT_CAPABILITIES)
      return DEFAULT_CAPABILITIES
    }

    const probeCanvas = document.createElement("canvas")
    const webgl = Boolean(
      probeCanvas.getContext("webgl2") ??
      probeCanvas.getContext("webgl") ??
      probeCanvas.getContext("experimental-webgl"),
    )

    const navigatorWithGpu = navigator as NavigatorWithGpu
    const adapter = await navigatorWithGpu.gpu?.requestAdapter?.()
    const webgpu = adapter !== null && adapter !== undefined
    const supportedRenderers = [
      ...(webgl ? (["webgl"] as const) : []),
      ...(webgpu ? (["webgpu"] as const) : []),
    ]

    const capabilities: RendererCapabilities = {
      webgl,
      webgpu,
      preferredRenderer: webgpu ? "webgpu" : "webgl",
      supportedRenderers,
    }

    this.capabilities.set(capabilities)
    return capabilities
  }
}
