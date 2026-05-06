import { ChangeDetectionStrategy, Component, computed, signal } from "@angular/core"
import { injectQuery } from "@tanstack/angular-query-experimental"

import {
  buildAdjacencyList,
  buildAdjacencyMatrix,
  buildLayoutPositions,
  findConnectedComponents,
  flattenSections,
} from "../../core/cid4/graph"
import { compareMolecules } from "../../core/cid4/comparison"
import {
  parseCompoundRecordPayload,
  parseConformerPayload,
  parseStructurePayload,
} from "../../core/cid4/parser"
import {
  CompoundRecord,
  FlatSectionNode,
  LayoutMode,
  MoleculeGraph,
  Point,
} from "../../core/cid4/types"
import { MoleculeRendererViewerComponent } from "./molecule-renderer-viewer.component"

const VIEWBOX_WIDTH = 720
const VIEWBOX_HEIGHT = 460
const VIEWBOX_PADDING = 68
const COMPONENT_COLORS = ["#1f6f8b", "#c45a1b", "#5f7c32", "#68458c", "#9b2948"]

interface DisplayAtom {
  id: number
  label: string
  elementSymbol: string
  degree: number
  mass: number
  x: number
  y: number
  componentIndex: number | null
}

interface DisplayBond {
  id: string
  source: number
  target: number
  x1: number
  y1: number
  x2: number
  y2: number
  disabled: boolean
}

interface BondControlRow {
  id: string
  label: string
  enabled: boolean
}

type MoleculeDatasetId =
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

const MOLECULE_DATASETS: MoleculeDatasetOption[] = [
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

async function fetchMoleculeDataset(datasetId: MoleculeDatasetId): Promise<MoleculeGraph> {
  const dataset = MOLECULE_DATASETS.find((option) => option.id === datasetId)

  if (!dataset) {
    throw new Error(`Unknown dataset ${datasetId}`)
  }

  return dataset.parser(await fetchJson(dataset.url))
}

async function fetchCompoundRecord(): Promise<CompoundRecord> {
  return parseCompoundRecordPayload(await fetchJson("/api/cid4/compound"))
}

@Component({
  selector: "app-data-structures-page",
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [MoleculeRendererViewerComponent],
  templateUrl: "./data-structures.page.html",
  styleUrl: "./data-structures.page.css",
})
export class DataStructuresPage {
  protected readonly viewboxWidth = VIEWBOX_WIDTH
  protected readonly viewboxHeight = VIEWBOX_HEIGHT
  protected readonly datasetOptions = MOLECULE_DATASETS

  protected readonly layoutMode = signal<LayoutMode>("source")
  protected readonly showLabels = signal(true)
  protected readonly selectedAtomId = signal<number | null>(1)
  protected readonly selectedDatasetId = signal<MoleculeDatasetId>("conformer-1")
  protected readonly comparisonEnabled = signal(false)
  protected readonly referenceDatasetId = signal<MoleculeDatasetId>("conformer-2")
  protected readonly disabledBondIds = signal<string[]>([])
  protected readonly localMolecule = signal<MoleculeGraph | null>(null)
  protected readonly localFileName = signal<string | null>(null)
  protected readonly uploadError = signal<string | null>(null)
  protected readonly dropzoneActive = signal(false)
  protected readonly draggedAtomId = signal<number | null>(null)
  protected readonly dragPositions = signal<Record<string, Point>>({})

  protected readonly moleculeQuery = injectQuery(() => ({
    queryKey: ["cid4", "molecule", this.selectedDatasetId()],
    queryFn: () => fetchMoleculeDataset(this.selectedDatasetId()),
  }))

  protected readonly compoundQuery = injectQuery(() => ({
    queryKey: ["cid4", "compound"],
    queryFn: fetchCompoundRecord,
  }))

  protected readonly comparisonReferenceQuery = injectQuery(() => ({
    queryKey: ["cid4", "molecule", "reference", this.referenceDatasetId()],
    queryFn: () => fetchMoleculeDataset(this.referenceDatasetId()),
  }))

  protected readonly activeMolecule = computed(
    () => this.localMolecule() ?? this.moleculeQuery.data() ?? null,
  )
  protected readonly activeBondIdSet = computed(
    () =>
      new Set(
        (this.activeMolecule()?.bonds ?? [])
          .filter((bond) => !new Set(this.disabledBondIds()).has(bond.id))
          .map((bond) => bond.id),
      ),
  )
  protected readonly activeBonds = computed(() => {
    const enabled = this.activeBondIdSet()
    return (this.activeMolecule()?.bonds ?? []).filter((bond) => enabled.has(bond.id))
  })
  protected readonly adjacencyRows = computed(() => {
    const molecule = this.activeMolecule()
    return molecule ? buildAdjacencyList(molecule, this.activeBondIdSet()) : []
  })
  protected readonly matrixRows = computed(() => {
    const molecule = this.activeMolecule()
    return molecule ? buildAdjacencyMatrix(molecule, this.activeBondIdSet()) : []
  })
  protected readonly connectedComponents = computed(() => {
    const molecule = this.activeMolecule()
    return molecule ? findConnectedComponents(molecule, this.activeBondIdSet()) : []
  })
  protected readonly sectionOutline = computed<FlatSectionNode[]>(() => {
    const record = this.compoundQuery.data()
    return record ? flattenSections(record.sections) : []
  })
  protected readonly dataSourceLabel = computed(() => {
    const fileName = this.localFileName()

    if (fileName) {
      return `Dropped file: ${fileName}`
    }

    return this.selectedDatasetOption()?.label ?? "Mock API dataset"
  })
  protected readonly selectedDatasetOption = computed(
    () =>
      MOLECULE_DATASETS.find((option) => option.id === this.selectedDatasetId()) ??
      MOLECULE_DATASETS[0],
  )
  protected readonly comparisonReferenceMolecule = computed(() => {
    if (!this.comparisonEnabled()) {
      return null
    }

    if (!this.localMolecule() && this.referenceDatasetId() === this.selectedDatasetId()) {
      return null
    }

    return this.comparisonReferenceQuery.data() ?? null
  })
  protected readonly comparisonSummary = computed(() => {
    const activeMolecule = this.activeMolecule()
    const referenceMolecule = this.comparisonReferenceMolecule()

    if (!activeMolecule || !referenceMolecule) {
      return null
    }

    return compareMolecules(activeMolecule, referenceMolecule)
  })
  protected readonly comparisonReferenceLabel = computed(() => {
    const reference = MOLECULE_DATASETS.find((option) => option.id === this.referenceDatasetId())
    return reference?.label ?? null
  })
  protected readonly atomHeaders = computed(
    () => this.activeMolecule()?.atoms.map((atom) => atom.id) ?? [],
  )
  protected readonly displayAtoms = computed<DisplayAtom[]>(() => {
    const molecule = this.activeMolecule()

    if (!molecule) {
      return []
    }

    const adjacencyByAtomId = new Map(
      this.adjacencyRows().map((row) => [row.atomId, row.neighbors.length]),
    )
    const componentByAtomId = new Map<number, number>()

    for (const [index, component] of this.connectedComponents().entries()) {
      for (const atomId of component.atomIds) {
        componentByAtomId.set(atomId, index)
      }
    }

    const basePositions = buildLayoutPositions(molecule, this.layoutMode())
    const projected = projectToViewbox(basePositions)
    const overrides = this.dragPositions()

    return molecule.atoms.map((atom) => {
      const override = overrides[String(atom.id)]
      const position = override ??
        projected.get(atom.id) ?? { x: VIEWBOX_WIDTH / 2, y: VIEWBOX_HEIGHT / 2 }

      return {
        id: atom.id,
        label: `${atom.elementSymbol}${atom.id}`,
        elementSymbol: atom.elementSymbol,
        degree: adjacencyByAtomId.get(atom.id) ?? 0,
        mass: atom.mass,
        x: position.x,
        y: position.y,
        componentIndex: componentByAtomId.get(atom.id) ?? null,
      }
    })
  })
  protected readonly displayBonds = computed<DisplayBond[]>(() => {
    const atomById = new Map(this.displayAtoms().map((atom) => [atom.id, atom]))
    const enabled = this.activeBondIdSet()

    return (this.activeMolecule()?.bonds ?? []).flatMap((bond) => {
      const source = atomById.get(bond.source)
      const target = atomById.get(bond.target)

      if (!source || !target) {
        return []
      }

      return [
        {
          id: bond.id,
          source: bond.source,
          target: bond.target,
          x1: source.x,
          y1: source.y,
          x2: target.x,
          y2: target.y,
          disabled: !enabled.has(bond.id),
        },
      ]
    })
  })
  protected readonly bondControls = computed<BondControlRow[]>(() => {
    const enabled = this.activeBondIdSet()

    return (this.activeMolecule()?.bonds ?? []).map((bond) => ({
      id: bond.id,
      label: `${bond.source} ↔ ${bond.target}`,
      enabled: enabled.has(bond.id),
    }))
  })
  protected readonly selectedAtom = computed(
    () => this.activeMolecule()?.atoms.find((atom) => atom.id === this.selectedAtomId()) ?? null,
  )
  protected readonly moleculeErrorMessage = computed(() => {
    const error = this.moleculeQuery.error()
    return error ? formatError(error) : null
  })
  protected readonly compoundErrorMessage = computed(() => {
    const error = this.compoundQuery.error()
    return error ? formatError(error) : null
  })
  protected readonly comparisonReferenceErrorMessage = computed(() => {
    const error = this.comparisonReferenceQuery.error()
    return error ? formatError(error) : null
  })

  protected atomFill(componentIndex: number | null): string {
    if (componentIndex === null) {
      return "#b8c8d6"
    }

    return COMPONENT_COLORS[componentIndex % COMPONENT_COLORS.length]
  }

  protected setLayoutMode(mode: LayoutMode): void {
    this.layoutMode.set(mode)
    this.dragPositions.set({})
  }

  protected resetLayout(): void {
    this.dragPositions.set({})
  }

  protected toggleLabels(): void {
    this.showLabels.update((current) => !current)
  }

  protected restoreApiData(): void {
    this.localMolecule.set(null)
    this.localFileName.set(null)
    this.uploadError.set(null)
    this.dragPositions.set({})
    this.disabledBondIds.set([])
  }

  protected selectAtom(atomId: number): void {
    this.selectedAtomId.set(atomId)
  }

  protected selectDataset(datasetId: MoleculeDatasetId): void {
    if (datasetId === this.selectedDatasetId() && !this.localMolecule()) {
      return
    }

    this.selectedDatasetId.set(datasetId)
    this.restoreApiData()
    this.selectedAtomId.set(1)
  }

  protected selectReferenceDataset(datasetId: MoleculeDatasetId): void {
    this.referenceDatasetId.set(datasetId)
  }

  protected setComparisonEnabled(enabled: boolean): void {
    this.comparisonEnabled.set(enabled)
  }

  protected async onFileSelected(event: Event): Promise<void> {
    const input = event.target

    if (!(input instanceof HTMLInputElement) || !input.files?.length) {
      return
    }

    await this.loadMoleculeFile(input.files[0])
    input.value = ""
  }

  protected onDragEnter(event: DragEvent): void {
    event.preventDefault()
    this.dropzoneActive.set(true)
  }

  protected onDragOver(event: DragEvent): void {
    event.preventDefault()
    this.dropzoneActive.set(true)

    if (event.dataTransfer) {
      event.dataTransfer.dropEffect = "copy"
    }
  }

  protected onDragLeave(event: DragEvent): void {
    event.preventDefault()
    this.dropzoneActive.set(false)
  }

  protected async onDrop(event: DragEvent): Promise<void> {
    event.preventDefault()
    this.dropzoneActive.set(false)

    const file = event.dataTransfer?.files?.[0]

    if (!file) {
      return
    }

    await this.loadMoleculeFile(file)
  }

  protected onNodePointerDown(event: PointerEvent, atomId: number): void {
    event.preventDefault()
    this.selectedAtomId.set(atomId)
    this.draggedAtomId.set(atomId)
  }

  protected onGraphPointerMove(event: PointerEvent, svg: Element): void {
    const atomId = this.draggedAtomId()

    if (atomId === null || !(svg instanceof SVGSVGElement)) {
      return
    }

    this.dragPositions.update((positions) => ({
      ...positions,
      [String(atomId)]: pointerToViewboxPoint(event, svg),
    }))
  }

  protected stopDragging(): void {
    this.draggedAtomId.set(null)
  }

  protected setBondEnabled(bondId: string, enabled: boolean): void {
    const next = new Set(this.disabledBondIds())

    if (enabled) {
      next.delete(bondId)
    } else {
      next.add(bondId)
    }

    this.disabledBondIds.set([...next])
  }

  private async loadMoleculeFile(file: File): Promise<void> {
    try {
      const payload = JSON.parse(await file.text()) as unknown
      const molecule = parseConformerPayload(payload)

      this.localMolecule.set(molecule)
      this.localFileName.set(file.name)
      this.uploadError.set(null)
      this.disabledBondIds.set([])
      this.dragPositions.set({})
      this.selectedAtomId.set(molecule.atoms[0]?.id ?? null)
    } catch (error) {
      this.uploadError.set(formatError(error))
    }
  }
}

function pointerToViewboxPoint(event: PointerEvent, svg: SVGSVGElement): Point {
  const rect = svg.getBoundingClientRect()
  const x = ((event.clientX - rect.left) / rect.width) * VIEWBOX_WIDTH
  const y = ((event.clientY - rect.top) / rect.height) * VIEWBOX_HEIGHT

  return {
    x: clamp(x, VIEWBOX_PADDING / 2, VIEWBOX_WIDTH - VIEWBOX_PADDING / 2),
    y: clamp(y, VIEWBOX_PADDING / 2, VIEWBOX_HEIGHT - VIEWBOX_PADDING / 2),
  }
}

function projectToViewbox(positions: Map<number, Point>): Map<number, Point> {
  const entries = [...positions.entries()]

  if (entries.length === 0) {
    return new Map()
  }

  const xValues = entries.map(([, point]) => point.x)
  const yValues = entries.map(([, point]) => point.y)
  const minX = Math.min(...xValues)
  const maxX = Math.max(...xValues)
  const minY = Math.min(...yValues)
  const maxY = Math.max(...yValues)
  const width = maxX - minX || 1
  const height = maxY - minY || 1
  const usableWidth = VIEWBOX_WIDTH - VIEWBOX_PADDING * 2
  const usableHeight = VIEWBOX_HEIGHT - VIEWBOX_PADDING * 2
  const scale = Math.min(usableWidth / width, usableHeight / height)
  const offsetX = (VIEWBOX_WIDTH - width * scale) / 2
  const offsetY = (VIEWBOX_HEIGHT - height * scale) / 2

  return new Map(
    entries.map(([atomId, point]) => [
      atomId,
      {
        x: offsetX + (point.x - minX) * scale,
        y: VIEWBOX_HEIGHT - (offsetY + (point.y - minY) * scale),
      },
    ]),
  )
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value))
}

function formatError(error: unknown): string {
  return error instanceof Error ? error.message : "Unexpected error"
}
