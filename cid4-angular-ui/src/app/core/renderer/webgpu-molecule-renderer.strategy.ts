import { MoleculeGraph } from "../cid4/types"
import { MoleculeRendererStrategy } from "./renderer.strategy"
import { MoleculeRenderOptions, RendererMetrics } from "./renderer.types"

const WEBGPU_SHADER = `
struct VertexIn {
  @location(0) position: vec2<f32>,
  @location(1) color: vec3<f32>,
}

struct VertexOut {
  @builtin(position) position: vec4<f32>,
  @location(0) color: vec3<f32>,
}

@vertex
fn vs_main(input: VertexIn) -> VertexOut {
  var output: VertexOut;
  output.position = vec4<f32>(input.position, 0.0, 1.0);
  output.color = input.color;
  return output;
}

@fragment
fn fs_main(input: VertexOut) -> @location(0) vec4<f32> {
  return vec4<f32>(input.color, 1.0);
}
`

type NavigatorWithGpu = Navigator & {
  gpu?: GpuNavigatorApi
}

interface GpuNavigatorApi {
  requestAdapter(): Promise<GpuAdapter | null>
  getPreferredCanvasFormat(): string
}

interface GpuAdapter {
  requestDevice(): Promise<GpuDevice>
}

interface GpuDevice {
  readonly queue: {
    submit(commandBuffers: unknown[]): void
  }

  createShaderModule(descriptor: { code: string }): GpuShaderModule
  createRenderPipeline(descriptor: unknown): GpuRenderPipeline
  createBuffer(descriptor: { size: number; usage: number; mappedAtCreation: boolean }): GpuBuffer
  createCommandEncoder(): GpuCommandEncoder
}

// eslint-disable-next-line @typescript-eslint/no-empty-object-type
interface GpuShaderModule {}

// eslint-disable-next-line @typescript-eslint/no-empty-object-type
interface GpuRenderPipeline {}

interface GpuBuffer {
  getMappedRange(): ArrayBuffer
  unmap(): void
}

interface GpuCommandEncoder {
  beginRenderPass(descriptor: unknown): GpuRenderPassEncoder
  finish(): unknown
}

interface GpuRenderPassEncoder {
  setPipeline(pipeline: GpuRenderPipeline): void
  setVertexBuffer(slot: number, buffer: GpuBuffer): void
  draw(vertexCount: number): void
  end(): void
}

interface GpuCanvasContext {
  configure(descriptor: { device: GpuDevice; format: string; alphaMode: "opaque" }): void

  getCurrentTexture(): {
    createView(): unknown
  }
}

interface GpuColor {
  r: number
  g: number
  b: number
  a: number
}

const GPU_BUFFER_USAGE_COPY_DST = 0x0008
const GPU_BUFFER_USAGE_VERTEX = 0x0020

export class WebGpuMoleculeRendererStrategy extends MoleculeRendererStrategy {
  readonly kind = "webgpu" as const

  private host: HTMLElement | null = null
  private canvas: HTMLCanvasElement | null = null
  private adapter: GpuAdapter | null = null
  private device: GpuDevice | null = null
  private context: GpuCanvasContext | null = null
  private pipeline: GpuRenderPipeline | null = null
  private format: string | null = null

  async initialize(host: HTMLElement): Promise<void> {
    if (typeof window === "undefined") {
      throw new Error("WebGPU rendering is only available in the browser")
    }

    const navigatorWithGpu = navigator as NavigatorWithGpu

    if (!navigatorWithGpu.gpu) {
      throw new Error("WebGPU is not supported in this browser")
    }

    this.adapter = await navigatorWithGpu.gpu.requestAdapter()

    if (!this.adapter) {
      throw new Error("No WebGPU adapter was available")
    }

    this.device = await this.adapter.requestDevice()
    this.host = host
    this.host.innerHTML = ""
    this.canvas = document.createElement("canvas")
    this.canvas.className = "renderer-surface"
    this.canvas.style.width = "100%"
    this.canvas.style.minHeight = "420px"
    this.canvas.style.borderRadius = "24px"
    this.host.appendChild(this.canvas)

    const context = this.canvas.getContext("webgpu") as GpuCanvasContext | null

    if (!context) {
      throw new Error("Unable to acquire a WebGPU canvas context")
    }

    this.context = context
    this.format = navigatorWithGpu.gpu.getPreferredCanvasFormat()
    this.configureContext()

    const shader = this.device.createShaderModule({
      code: WEBGPU_SHADER,
    })

    this.pipeline = this.device.createRenderPipeline({
      layout: "auto",
      vertex: {
        module: shader,
        entryPoint: "vs_main",
        buffers: [
          {
            arrayStride: 20,
            attributes: [
              { shaderLocation: 0, offset: 0, format: "float32x2" },
              { shaderLocation: 1, offset: 8, format: "float32x3" },
            ],
          },
        ],
      },
      fragment: {
        module: shader,
        entryPoint: "fs_main",
        targets: [{ format: this.format }],
      },
      primitive: {
        topology: "line-list",
      },
    })
  }

  async render(
    molecule: MoleculeGraph,
    options: MoleculeRenderOptions,
    comparisonReference: MoleculeGraph | null = null,
  ): Promise<RendererMetrics> {
    if (!this.device || !this.context || !this.pipeline || !this.canvas) {
      throw new Error("WebGPU renderer is not initialized")
    }

    this.configureContext()

    const renderStartedAt = performance.now()
    const vertices = buildWireframeVertices(molecule, comparisonReference)
    const vertexBuffer = this.device.createBuffer({
      size: vertices.byteLength,
      usage: GPU_BUFFER_USAGE_VERTEX | GPU_BUFFER_USAGE_COPY_DST,
      mappedAtCreation: true,
    })

    new Float32Array(vertexBuffer.getMappedRange()).set(vertices)
    vertexBuffer.unmap()

    const encoder = this.device.createCommandEncoder()
    const renderPass = encoder.beginRenderPass({
      colorAttachments: [
        {
          view: this.context.getCurrentTexture().createView(),
          clearValue: hexToGpuColor(options.backgroundColor),
          loadOp: "clear",
          storeOp: "store",
        },
      ],
    })

    renderPass.setPipeline(this.pipeline)
    renderPass.setVertexBuffer(0, vertexBuffer)
    renderPass.draw(vertices.length / 5)
    renderPass.end()

    this.device.queue.submit([encoder.finish()])

    return {
      lastRenderDurationMs: performance.now() - renderStartedAt,
      renderedAtomCount: molecule.atoms.length,
      renderedBondCount: molecule.bonds.length,
    }
  }

  resetView(): void {
    // The current MVP renderer uses a fixed projected camera, so reset is a no-op.
  }

  dispose(): void {
    this.host?.replaceChildren()
    this.pipeline = null
    this.context = null
    this.canvas = null
    this.device = null
    this.adapter = null
    this.host = null
  }

  private configureContext(): void {
    if (!this.device || !this.context || !this.canvas || !this.format) {
      return
    }

    const dpr = window.devicePixelRatio || 1
    const width = Math.max(1, Math.floor(this.host?.clientWidth ?? 720))
    const height = Math.max(420, Math.floor(this.host?.clientHeight ?? 420))
    this.canvas.width = Math.floor(width * dpr)
    this.canvas.height = Math.floor(height * dpr)
    this.context.configure({
      device: this.device,
      format: this.format,
      alphaMode: "opaque",
    })
  }
}

function buildWireframeVertices(
  molecule: MoleculeGraph,
  comparisonReference: MoleculeGraph | null,
): Float32Array {
  const comparisonProjection = comparisonReference
    ? projectComparisonPair(molecule, comparisonReference)
    : null
  const projectedAtoms = comparisonProjection?.currentAtoms ?? projectAtoms(molecule)
  const atomById = new Map(projectedAtoms.map((atom) => [atom.id, atom]))
  const vertices: number[] = []

  for (const bond of molecule.bonds) {
    const source = atomById.get(bond.source)
    const target = atomById.get(bond.target)

    if (!source || !target) {
      continue
    }

    vertices.push(source.x, source.y, 0.56, 0.63, 0.72)
    vertices.push(target.x, target.y, 0.56, 0.63, 0.72)
  }

  for (const atom of projectedAtoms) {
    const color = atom.color
    const size = atom.atomicNumber === 1 ? 0.018 : 0.028
    vertices.push(atom.x - size, atom.y, color[0], color[1], color[2])
    vertices.push(atom.x + size, atom.y, color[0], color[1], color[2])
    vertices.push(atom.x, atom.y - size, color[0], color[1], color[2])
    vertices.push(atom.x, atom.y + size, color[0], color[1], color[2])
  }

  if (comparisonProjection && comparisonReference) {
    addComparisonOverlayVertices(vertices, molecule, comparisonReference, comparisonProjection)
  }

  return new Float32Array(vertices)
}

function addComparisonOverlayVertices(
  vertices: number[],
  molecule: MoleculeGraph,
  comparisonReference: MoleculeGraph,
  projection: {
    currentAtoms: ProjectedAtom[]
    referenceAtoms: ProjectedAtom[]
  },
): void {
  const referenceAtomsById = new Map(comparisonReference.atoms.map((atom) => [atom.id, atom]))
  const currentAtomsById = new Map(molecule.atoms.map((atom) => [atom.id, atom]))
  const projectedCurrentById = new Map(projection.currentAtoms.map((atom) => [atom.id, atom]))
  const projectedReferenceById = new Map(projection.referenceAtoms.map((atom) => [atom.id, atom]))
  const referenceBondsById = new Map(comparisonReference.bonds.map((bond) => [bond.id, bond]))

  for (const atom of molecule.atoms) {
    const referenceAtom = referenceAtomsById.get(atom.id)
    const projectedCurrent = projectedCurrentById.get(atom.id)
    const projectedReference = projectedReferenceById.get(atom.id)

    if (!referenceAtom || !projectedCurrent || !projectedReference) {
      continue
    }

    const displacement = Math.hypot(
      atom.x - referenceAtom.x,
      atom.y - referenceAtom.y,
      atom.z - referenceAtom.z,
    )

    if (displacement < 0.04) {
      continue
    }

    const intensity = clamp01(displacement / 0.9)
    const red = 0.82
    const green = 0.34 + 0.36 * (1 - intensity)
    const blue = 0.18
    vertices.push(projectedReference.x, projectedReference.y, red, green, blue)
    vertices.push(projectedCurrent.x, projectedCurrent.y, red, green, blue)
  }

  for (const bond of molecule.bonds) {
    const referenceBond = referenceBondsById.get(bond.id)
    const source = currentAtomsById.get(bond.source)
    const target = currentAtomsById.get(bond.target)
    const projectedSource = projectedCurrentById.get(bond.source)
    const projectedTarget = projectedCurrentById.get(bond.target)

    if (!referenceBond || !source || !target || !projectedSource || !projectedTarget) {
      continue
    }

    const referenceSource = referenceAtomsById.get(referenceBond.source)
    const referenceTarget = referenceAtomsById.get(referenceBond.target)

    if (!referenceSource || !referenceTarget) {
      continue
    }

    const currentLength = Math.hypot(source.x - target.x, source.y - target.y, source.z - target.z)
    const referenceLength = Math.hypot(
      referenceSource.x - referenceTarget.x,
      referenceSource.y - referenceTarget.y,
      referenceSource.z - referenceTarget.z,
    )
    const delta = Math.abs(currentLength - referenceLength)

    if (delta < 0.025) {
      continue
    }

    const intensity = clamp01(delta / 0.4)
    const red = 0.92
    const green = 0.64 - 0.34 * intensity
    const blue = 0.12
    vertices.push(projectedSource.x, projectedSource.y, red, green, blue)
    vertices.push(projectedTarget.x, projectedTarget.y, red, green, blue)
  }
}

interface ProjectedAtom {
  id: number
  atomicNumber: number
  x: number
  y: number
  color: [number, number, number]
}

function projectAtoms(molecule: MoleculeGraph): ProjectedAtom[] {
  const projected = molecule.atoms.map((atom) => ({
    id: atom.id,
    atomicNumber: atom.atomicNumber,
    x: atom.x * 0.82 - atom.z * 0.35,
    y: atom.y * 0.82 + atom.z * 0.22,
  }))

  return normalizeProjectedAtoms(projected)
}

function projectComparisonPair(
  molecule: MoleculeGraph,
  comparisonReference: MoleculeGraph,
): {
  currentAtoms: ProjectedAtom[]
  referenceAtoms: ProjectedAtom[]
} {
  const currentProjected = molecule.atoms.map((atom) => ({
    id: atom.id,
    atomicNumber: atom.atomicNumber,
    x: atom.x * 0.82 - atom.z * 0.35,
    y: atom.y * 0.82 + atom.z * 0.22,
  }))
  const referenceProjected = comparisonReference.atoms.map((atom) => ({
    id: atom.id,
    atomicNumber: atom.atomicNumber,
    x: atom.x * 0.82 - atom.z * 0.35,
    y: atom.y * 0.82 + atom.z * 0.22,
  }))
  const bounds = [...currentProjected, ...referenceProjected]

  return {
    currentAtoms: normalizeProjectedAtoms(currentProjected, bounds),
    referenceAtoms: normalizeProjectedAtoms(referenceProjected, bounds),
  }
}

function normalizeProjectedAtoms(
  projected: Array<{ id: number; atomicNumber: number; x: number; y: number }>,
  boundsSource: Array<{ x: number; y: number }> = projected,
): ProjectedAtom[] {
  const xValues = boundsSource.map((atom) => atom.x)
  const yValues = boundsSource.map((atom) => atom.y)
  const minX = Math.min(...xValues)
  const maxX = Math.max(...xValues)
  const minY = Math.min(...yValues)
  const maxY = Math.max(...yValues)
  const width = maxX - minX || 1
  const height = maxY - minY || 1
  const scale = 1.65 / Math.max(width, height)

  return projected.map((atom) => ({
    ...atom,
    x: (atom.x - minX) * scale - 0.825,
    y: 1 - (atom.y - minY) * scale - 0.825,
    color: colorForAtomicNumber(atom.atomicNumber),
  }))
}

function clamp01(value: number): number {
  return Math.min(1, Math.max(0, value))
}

function colorForAtomicNumber(atomicNumber: number): [number, number, number] {
  switch (atomicNumber) {
    case 8:
      return [0.77, 0.22, 0.21]
    case 7:
      return [0.12, 0.35, 0.72]
    case 6:
      return [0.19, 0.21, 0.24]
    default:
      return [0.73, 0.75, 0.8]
  }
}

function hexToGpuColor(hexColor: string): GpuColor {
  const sanitized = hexColor.replace("#", "")
  const normalized =
    sanitized.length === 3
      ? sanitized
          .split("")
          .map((value) => value + value)
          .join("")
      : sanitized
  const red = Number.parseInt(normalized.slice(0, 2), 16) / 255
  const green = Number.parseInt(normalized.slice(2, 4), 16) / 255
  const blue = Number.parseInt(normalized.slice(4, 6), 16) / 255

  return { r: red, g: green, b: blue, a: 1 }
}
