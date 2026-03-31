import { ChangeDetectionStrategy, Component, computed, signal } from "@angular/core"
import { injectQuery } from "@tanstack/angular-query-experimental"

import {
  buildAdjacencyList,
  buildAdjacencyMatrix,
  buildLayoutPositions,
  findConnectedComponents,
  flattenSections,
} from "../../core/cid4/graph"
import { parseCompoundRecordPayload, parseConformerPayload } from "../../core/cid4/parser"
import {
  CompoundRecord,
  FlatSectionNode,
  LayoutMode,
  MoleculeGraph,
  Point,
} from "../../core/cid4/types"

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

async function fetchJson(url: string): Promise<unknown> {
  const response = await fetch(url)

  if (!response.ok) {
    throw new Error(`Request failed with status ${response.status}`)
  }

  return response.json() as Promise<unknown>
}

async function fetchConformer(): Promise<MoleculeGraph> {
  return parseConformerPayload(await fetchJson("/api/cid4/conformer/1"))
}

async function fetchCompoundRecord(): Promise<CompoundRecord> {
  return parseCompoundRecordPayload(await fetchJson("/api/cid4/compound"))
}

@Component({
  selector: "app-data-structures-page",
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <section class="hero card" aria-labelledby="page-title">
      <div>
        <p class="eyebrow">Data Structures</p>
        <h1 id="page-title">Interactive Molecular Graph Workbench</h1>
        <p class="lede">
          Fetch CID 4 through mocked API routes, drop in a PubChem conformer JSON file, and inspect
          the same molecule as an adjacency list, adjacency matrix, atom property map, and
          union-find component model.
        </p>
      </div>

      <dl class="hero-meta">
        <div>
          <dt>Source</dt>
          <dd>{{ dataSourceLabel() }}</dd>
        </div>
        <div>
          <dt>Atoms</dt>
          <dd>{{ activeMolecule()?.atoms?.length ?? 0 }}</dd>
        </div>
        <div>
          <dt>Active Bonds</dt>
          <dd>{{ activeBonds().length }}</dd>
        </div>
        <div>
          <dt>Components</dt>
          <dd>{{ connectedComponents().length }}</dd>
        </div>
      </dl>
    </section>

    <section class="workspace-grid">
      <article class="card viewer-card">
        <div class="card-header">
          <div>
            <p class="eyebrow">Graph Canvas</p>
            <h2>Rearrangeable molecule view</h2>
          </div>
          <div class="toolbar" aria-label="Graph controls">
            <button
              type="button"
              class="chip"
              [class.active]="layoutMode() === 'source'"
              (click)="setLayoutMode('source')"
            >
              Conformer layout
            </button>
            <button
              type="button"
              class="chip"
              [class.active]="layoutMode() === 'circle'"
              (click)="setLayoutMode('circle')"
            >
              Circle layout
            </button>
            <button type="button" class="chip ghost" (click)="resetLayout()">Reset nodes</button>
            <button type="button" class="chip ghost" (click)="toggleLabels()">
              {{ showLabels() ? "Hide labels" : "Show labels" }}
            </button>
            <button
              type="button"
              class="chip ghost"
              [disabled]="!localMolecule()"
              (click)="restoreApiData()"
            >
              Use API data
            </button>
          </div>
        </div>

        <div
          class="dropzone"
          [class.dropzone-active]="dropzoneActive()"
          (dragenter)="onDragEnter($event)"
          (dragover)="onDragOver($event)"
          (dragleave)="onDragLeave($event)"
          (drop)="onDrop($event)"
        >
          <div>
            <p class="drop-title">Drop a PubChem conformer JSON file here</p>
            <p class="drop-copy">
              The parser reads the PC_Compounds[0] entry, bonds, and the first conformer coordinate
              set.
            </p>
          </div>
          <label class="upload-button">
            <span>Choose file</span>
            <input type="file" accept="application/json,.json" (change)="onFileSelected($event)" />
          </label>
        </div>

        @if (uploadError()) {
          <p class="error-banner" aria-live="assertive">{{ uploadError() }}</p>
        }

        @if (moleculeQuery.isPending() && !activeMolecule()) {
          <p class="status-text">Loading mocked molecule payload...</p>
        } @else if (moleculeQuery.isError() && !activeMolecule()) {
          <p class="error-banner" aria-live="assertive">{{ moleculeErrorMessage() }}</p>
        } @else if (activeMolecule(); as molecule) {
          <svg
            #graphSvg
            class="graph-canvas"
            [attr.viewBox]="'0 0 ' + viewboxWidth + ' ' + viewboxHeight"
            role="img"
            aria-label="CID 4 molecular graph"
            (pointermove)="onGraphPointerMove($event, graphSvg)"
            (pointerup)="stopDragging()"
            (pointercancel)="stopDragging()"
            (pointerleave)="stopDragging()"
          >
            <rect x="0" y="0" [attr.width]="viewboxWidth" [attr.height]="viewboxHeight" rx="28" />

            @for (bond of displayBonds(); track bond.id) {
              <line
                class="bond"
                [class.bond-disabled]="bond.disabled"
                [attr.x1]="bond.x1"
                [attr.y1]="bond.y1"
                [attr.x2]="bond.x2"
                [attr.y2]="bond.y2"
              />
            }

            @for (atom of displayAtoms(); track atom.id) {
              <g class="atom-group" [class.atom-selected]="selectedAtomId() === atom.id">
                <circle
                  class="atom-hit"
                  [attr.cx]="atom.x"
                  [attr.cy]="atom.y"
                  r="24"
                  (click)="selectAtom(atom.id)"
                  (pointerdown)="onNodePointerDown($event, atom.id)"
                />
                <circle
                  class="atom-core"
                  [attr.cx]="atom.x"
                  [attr.cy]="atom.y"
                  r="18"
                  [attr.fill]="atomFill(atom.componentIndex)"
                />
                <text class="atom-text" [attr.x]="atom.x" [attr.y]="atom.y + 1">
                  {{ atom.elementSymbol }}
                </text>
                @if (showLabels()) {
                  <text class="atom-label" [attr.x]="atom.x" [attr.y]="atom.y - 28">
                    #{{ atom.id }}
                  </text>
                }
              </g>
            }
          </svg>

          <div class="legend-row" aria-label="Connected component legend">
            @for (component of connectedComponents(); track component.id; let index = $index) {
              <div class="legend-pill">
                <span class="legend-dot" [style.background]="atomFill(index)"></span>
                <span>Component {{ index + 1 }}: {{ component.atomIds.join(", ") }}</span>
              </div>
            }
          </div>
        }
      </article>

      <article class="card aside-card">
        <div class="card-header">
          <div>
            <p class="eyebrow">Compound Tree</p>
            <h2>Mocked record outline</h2>
          </div>
        </div>

        @if (compoundQuery.isPending()) {
          <p class="status-text">Loading mocked compound outline...</p>
        } @else if (compoundQuery.isError()) {
          <p class="error-banner" aria-live="assertive">{{ compoundErrorMessage() }}</p>
        } @else {
          <p class="aside-title">{{ compoundQuery.data()?.title }}</p>
          <p class="aside-copy">
            Recursive traversal flattens the Section tree into an indented outline for quick
            inspection.
          </p>

          <ol class="section-outline">
            @for (item of sectionOutline(); track item.id) {
              <li [style.padding-inline-start.px]="item.depth * 16">
                <span class="section-heading">{{ item.heading }}</span>
                <span class="section-meta">{{ item.childCount }} children</span>
                @if (item.description) {
                  <p>{{ item.description }}</p>
                }
              </li>
            }
          </ol>
        }
      </article>
    </section>

    <section class="panel-grid">
      <article class="card data-card">
        <div class="card-header compact">
          <div>
            <p class="eyebrow">Adjacency List</p>
            <h2>Bonded neighbors by atom</h2>
          </div>
        </div>

        <div class="table-frame">
          <table>
            <thead>
              <tr>
                <th scope="col">Atom</th>
                <th scope="col">Neighbors</th>
              </tr>
            </thead>
            <tbody>
              @for (row of adjacencyRows(); track row.atomId) {
                <tr
                  [class.row-selected]="selectedAtomId() === row.atomId"
                  (click)="selectAtom(row.atomId)"
                >
                  <th scope="row">{{ row.atomId }}</th>
                  <td>{{ row.neighbors.join(", ") || "None" }}</td>
                </tr>
              }
            </tbody>
          </table>
        </div>
      </article>

      <article class="card data-card">
        <div class="card-header compact">
          <div>
            <p class="eyebrow">Atom Property Map</p>
            <h2>Hash-map style inspector</h2>
          </div>
        </div>

        @if (selectedAtom(); as atom) {
          <div class="selected-atom">
            <p class="selected-kicker">Selected atom #{{ atom.id }}</p>
            <p>
              {{ atom.elementSymbol }} · atomic number {{ atom.atomicNumber }} · mass
              {{ atom.mass }}
            </p>
          </div>
        }

        <div class="table-frame">
          <table>
            <thead>
              <tr>
                <th scope="col">Atom</th>
                <th scope="col">Element</th>
                <th scope="col">Mass</th>
                <th scope="col">Degree</th>
                <th scope="col">Hybridization</th>
              </tr>
            </thead>
            <tbody>
              @for (atom of displayAtoms(); track atom.id) {
                <tr
                  [class.row-selected]="selectedAtomId() === atom.id"
                  (click)="selectAtom(atom.id)"
                >
                  <th scope="row">{{ atom.id }}</th>
                  <td>{{ atom.elementSymbol }}</td>
                  <td>{{ atom.mass }}</td>
                  <td>{{ atom.degree }}</td>
                  <td>{{ activeMolecule()?.atoms?.[atom.id - 1]?.hybridization ?? "n/a" }}</td>
                </tr>
              }
            </tbody>
          </table>
        </div>
      </article>

      <article class="card data-card matrix-card">
        <div class="card-header compact">
          <div>
            <p class="eyebrow">Adjacency Matrix</p>
            <h2>Space-time trade-off view</h2>
          </div>
          <p class="tradeoff-copy">
            Dense lookup is constant-time, but this 14×14 matrix carries many zeros compared with
            the sparse adjacency list.
          </p>
        </div>

        <div class="table-frame matrix-frame">
          <table class="matrix-table">
            <thead>
              <tr>
                <th scope="col">Atom</th>
                @for (header of atomHeaders(); track header) {
                  <th scope="col">{{ header }}</th>
                }
              </tr>
            </thead>
            <tbody>
              @for (row of matrixRows(); track row.atomId) {
                <tr
                  [class.row-selected]="selectedAtomId() === row.atomId"
                  (click)="selectAtom(row.atomId)"
                >
                  <th scope="row">{{ row.atomId }}</th>
                  @for (value of row.values; track $index) {
                    <td [class.matrix-live]="value > 0">{{ value }}</td>
                  }
                </tr>
              }
            </tbody>
          </table>
        </div>
      </article>

      <article class="card data-card">
        <div class="card-header compact">
          <div>
            <p class="eyebrow">Union-Find</p>
            <h2>Connected components with bond toggles</h2>
          </div>
        </div>

        <p class="aside-copy">
          Disable bonds to simulate zeroed edges and watch the component partition update.
        </p>

        <div class="bond-toggle-list">
          @for (bond of bondControls(); track bond.id) {
            <label class="bond-toggle">
              <input
                type="checkbox"
                [checked]="bond.enabled"
                (change)="setBondEnabled(bond.id, $any($event.target).checked)"
              />
              <span>{{ bond.label }}</span>
            </label>
          }
        </div>

        <ul class="component-list">
          @for (component of connectedComponents(); track component.id; let index = $index) {
            <li>
              <span class="legend-dot" [style.background]="atomFill(index)"></span>
              Component {{ index + 1 }} → {{ component.atomIds.join(", ") }}
            </li>
          }
        </ul>
      </article>
    </section>
  `,
  styles: [
    `
      :host {
        display: block;
      }

      .card {
        border-radius: 28px;
        padding: clamp(18px, 3vw, 28px);
        background: rgba(255, 252, 247, 0.84);
        border: 1px solid rgba(16, 35, 61, 0.1);
        box-shadow: 0 18px 42px rgba(16, 35, 61, 0.1);
        backdrop-filter: blur(10px);
      }

      .hero {
        display: grid;
        grid-template-columns: minmax(0, 1.6fr) minmax(280px, 0.9fr);
        gap: 20px;
        margin-bottom: 20px;
      }

      .hero-meta {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 12px;
        margin: 0;
      }

      .hero-meta div {
        padding: 14px;
        border-radius: 18px;
        background: rgba(16, 35, 61, 0.05);
      }

      dt {
        font-size: 0.74rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: #6d7f94;
      }

      dd {
        margin: 8px 0 0;
        font-size: 1rem;
        font-weight: 700;
      }

      .eyebrow {
        margin: 0 0 8px;
        font-size: 0.76rem;
        font-weight: 700;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        color: #8b6325;
      }

      h1,
      h2 {
        margin: 0;
      }

      h1 {
        font-size: clamp(2rem, 5vw, 3.2rem);
        line-height: 0.96;
      }

      h2 {
        font-size: 1.35rem;
      }

      .lede {
        margin: 14px 0 0;
        max-width: 62ch;
        line-height: 1.65;
        color: #38516f;
      }

      .workspace-grid,
      .panel-grid {
        display: grid;
        gap: 20px;
      }

      .workspace-grid {
        grid-template-columns: minmax(0, 1.65fr) minmax(280px, 0.95fr);
      }

      .panel-grid {
        grid-template-columns: repeat(2, minmax(0, 1fr));
        margin-top: 20px;
      }

      .matrix-card {
        grid-column: 1 / -1;
      }

      .card-header {
        display: flex;
        align-items: start;
        justify-content: space-between;
        gap: 16px;
        margin-bottom: 18px;
      }

      .card-header.compact {
        margin-bottom: 14px;
      }

      .toolbar {
        display: flex;
        flex-wrap: wrap;
        justify-content: end;
        gap: 10px;
      }

      .chip,
      .upload-button {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        gap: 8px;
        border: 0;
        border-radius: 999px;
        padding: 11px 16px;
        font: inherit;
        font-weight: 700;
        color: #10233d;
        background: #dbeaf1;
        cursor: pointer;
        text-decoration: none;
      }

      .chip.active {
        background: #10233d;
        color: #f8fbfc;
      }

      .chip.ghost,
      .upload-button {
        background: #f2e8da;
      }

      .chip:disabled {
        opacity: 0.55;
        cursor: not-allowed;
      }

      .chip:focus-visible,
      .upload-button:focus-within,
      .bond-toggle input:focus-visible {
        outline: 3px solid #c45a1b;
        outline-offset: 3px;
      }

      .dropzone {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 16px;
        margin-bottom: 16px;
        padding: 18px 20px;
        border-radius: 22px;
        border: 2px dashed rgba(16, 35, 61, 0.18);
        background: rgba(255, 255, 255, 0.42);
      }

      .dropzone-active {
        border-color: #1f6f8b;
        background: rgba(31, 111, 139, 0.08);
      }

      .drop-title,
      .aside-title,
      .selected-kicker {
        margin: 0;
        font-weight: 800;
      }

      .drop-copy,
      .aside-copy,
      .tradeoff-copy,
      .section-outline p {
        margin: 8px 0 0;
        line-height: 1.55;
        color: #45607e;
      }

      .upload-button input {
        position: absolute;
        width: 1px;
        height: 1px;
        opacity: 0;
        pointer-events: none;
      }

      .graph-canvas {
        width: 100%;
        border-radius: 26px;
        background: linear-gradient(180deg, #fbf8f2 0%, #f2f7f7 100%);
        box-shadow: inset 0 0 0 1px rgba(16, 35, 61, 0.06);
      }

      .graph-canvas rect {
        fill: transparent;
      }

      .bond {
        stroke: #8fa0b8;
        stroke-width: 3.5;
        stroke-linecap: round;
      }

      .bond-disabled {
        stroke: #d9c8b5;
        stroke-dasharray: 8 8;
      }

      .atom-hit {
        fill: transparent;
        cursor: grab;
      }

      .atom-core {
        stroke: rgba(16, 35, 61, 0.12);
        stroke-width: 2;
      }

      .atom-selected .atom-core {
        stroke: #10233d;
        stroke-width: 3;
      }

      .atom-text,
      .atom-label {
        fill: #10233d;
        text-anchor: middle;
        dominant-baseline: middle;
        pointer-events: none;
      }

      .atom-text {
        font-size: 0.95rem;
        font-weight: 800;
      }

      .atom-label {
        font-size: 0.8rem;
        font-weight: 700;
      }

      .legend-row {
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
        margin-top: 14px;
      }

      .legend-pill,
      .component-list li {
        display: inline-flex;
        align-items: center;
        gap: 10px;
      }

      .legend-pill {
        padding: 9px 12px;
        border-radius: 999px;
        background: rgba(16, 35, 61, 0.05);
      }

      .legend-dot {
        width: 12px;
        height: 12px;
        border-radius: 999px;
        flex: none;
      }

      .status-text,
      .error-banner {
        margin: 0;
        padding: 14px 16px;
        border-radius: 18px;
      }

      .status-text {
        background: #fff3cf;
      }

      .error-banner {
        background: #fce3df;
        color: #7d2418;
      }

      .section-outline,
      .component-list {
        margin: 16px 0 0;
        padding: 0;
        list-style: none;
      }

      .section-outline li,
      .component-list li {
        padding: 10px 0;
        border-bottom: 1px solid rgba(16, 35, 61, 0.08);
      }

      .section-heading {
        font-weight: 700;
      }

      .section-meta {
        margin-inline-start: 10px;
        color: #6b7b90;
        font-size: 0.9rem;
      }

      .table-frame {
        overflow: auto;
        border-radius: 18px;
        border: 1px solid rgba(16, 35, 61, 0.08);
        background: rgba(255, 255, 255, 0.56);
      }

      table {
        width: 100%;
        border-collapse: collapse;
        min-width: 420px;
      }

      th,
      td {
        padding: 10px 12px;
        border-bottom: 1px solid rgba(16, 35, 61, 0.06);
        text-align: left;
        font-size: 0.95rem;
      }

      tbody tr {
        cursor: pointer;
      }

      .row-selected {
        background: rgba(31, 111, 139, 0.1);
      }

      .selected-atom {
        margin-bottom: 14px;
        padding: 14px 16px;
        border-radius: 18px;
        background: rgba(16, 35, 61, 0.05);
      }

      .matrix-frame {
        max-height: 420px;
      }

      .matrix-table {
        min-width: 900px;
      }

      .matrix-table th,
      .matrix-table td {
        text-align: center;
      }

      .matrix-table tbody th {
        text-align: left;
        position: sticky;
        left: 0;
        background: rgba(248, 251, 252, 0.98);
      }

      .matrix-live {
        background: rgba(196, 90, 27, 0.12);
        font-weight: 800;
      }

      .bond-toggle-list {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 10px;
        margin-top: 16px;
      }

      .bond-toggle {
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 10px 12px;
        border-radius: 16px;
        background: rgba(16, 35, 61, 0.05);
      }

      @media (max-width: 1100px) {
        .hero,
        .workspace-grid,
        .panel-grid {
          grid-template-columns: 1fr;
        }

        .card-header {
          flex-direction: column;
        }

        .toolbar {
          justify-content: start;
        }
      }

      @media (max-width: 720px) {
        .dropzone,
        .bond-toggle-list,
        .hero-meta {
          grid-template-columns: 1fr;
          flex-direction: column;
        }

        .dropzone {
          align-items: start;
        }

        .bond-toggle-list {
          display: grid;
        }
      }
    `,
  ],
})
export class DataStructuresPage {
  protected readonly viewboxWidth = VIEWBOX_WIDTH
  protected readonly viewboxHeight = VIEWBOX_HEIGHT

  protected readonly layoutMode = signal<LayoutMode>("source")
  protected readonly showLabels = signal(true)
  protected readonly selectedAtomId = signal<number | null>(1)
  protected readonly disabledBondIds = signal<string[]>([])
  protected readonly localMolecule = signal<MoleculeGraph | null>(null)
  protected readonly localFileName = signal<string | null>(null)
  protected readonly uploadError = signal<string | null>(null)
  protected readonly dropzoneActive = signal(false)
  protected readonly draggedAtomId = signal<number | null>(null)
  protected readonly dragPositions = signal<Record<string, Point>>({})

  protected readonly moleculeQuery = injectQuery(() => ({
    queryKey: ["cid4", "conformer", 1],
    queryFn: fetchConformer,
  }))

  protected readonly compoundQuery = injectQuery(() => ({
    queryKey: ["cid4", "compound"],
    queryFn: fetchCompoundRecord,
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
    return fileName ? `Dropped file: ${fileName}` : "Mock API /api/cid4/conformer/1"
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
  protected readonly moleculeErrorMessage = computed(() => formatError(this.moleculeQuery.error()))
  protected readonly compoundErrorMessage = computed(() => formatError(this.compoundQuery.error()))

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
