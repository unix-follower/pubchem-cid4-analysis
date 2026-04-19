import { ChangeDetectionStrategy, Component, computed, effect, signal } from "@angular/core"
import { injectQuery } from "@tanstack/angular-query-experimental"

import {
  buildMergeSortTrace,
  buildQuickSortTrace,
  buildThresholdBinarySearchTrace,
  deduplicateByKey,
} from "../../core/algorithms/array-algorithms"
import {
  buildBfsTrace,
  buildCycleDetectionTrace,
  buildDfsTrace,
  buildLaplacianAnalysis,
  buildMinimumSpanningTreeTrace,
  buildMolecularGraphMetrics,
  buildMorganAnalysis,
  buildShortestPathTrace,
  buildTopologicalSortTrace,
} from "../../core/algorithms/graph-algorithms"
import {
  AlgorithmGraph,
  BinarySearchTraceResult,
  DeduplicationResult,
  GraphTraceResult,
  MatrixAnalysis,
  MolecularGraphMetrics,
  MorganAnalysisResult,
} from "../../core/algorithms/types"
import { buildLayoutPositions } from "../../core/cid4/graph"
import { parseConformerPayload } from "../../core/cid4/parser"
import { MoleculeGraph, Point } from "../../core/cid4/types"
import { CytoscapeGraphComponent } from "./cytoscape-graph.component"

const GRAPH_SCENARIOS = [
  "bfs",
  "dfs",
  "weighted-shortest-path",
  "shortest-path",
  "morgan-labeling",
  "cycle-detection",
  "minimum-spanning-tree",
  "topological-sort",
] as const

const SORT_ALGORITHMS = ["merge-sort", "quick-sort"] as const

type GraphScenario = (typeof GRAPH_SCENARIOS)[number]
type SortAlgorithm = (typeof SORT_ALGORITHMS)[number]

interface PathwayResponse {
  graph: AlgorithmGraph
}

interface ReactionNetworkSummary {
  pathwayCount: number
  reactionCount: number
  compoundCount: number
  taxonomyCount: number
  edgeCount: number
  cid4ParticipationEdgeCount: number
}

interface ReactionNetworkResponse {
  graph: AlgorithmGraph
  summary: ReactionNetworkSummary
}

interface BioactivityRecord {
  aid: number
  assay: string
  activityValue: number
}

interface BioactivityResponse {
  records: BioactivityRecord[]
}

interface TaxonomyRecord {
  taxonomyId: number
  sourceOrganism: string
}

interface TaxonomyResponse {
  organisms: TaxonomyRecord[]
}

@Component({
  selector: "app-algorithms-page",
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [CytoscapeGraphComponent],
  template: `
    <section class="hero card" aria-labelledby="algorithms-title">
      <div>
        <p class="eyebrow">Algorithms</p>
        <h1 id="algorithms-title">CID 4 Algorithm Studio</h1>
        <p class="lede">
          Graph-centric exercises run in Cytoscape on a lazy route, while sorting, threshold search,
          and hash-based dedup stay in table-first views with explicit step traces.
        </p>
      </div>

      <dl class="hero-meta">
        <div>
          <dt>Graph scenario</dt>
          <dd>{{ graphScenarioLabel() }}</dd>
        </div>
        <div>
          <dt>Trace steps</dt>
          <dd>{{ activeGraphTrace()?.steps?.length ?? 0 }}</dd>
        </div>
        <div>
          <dt>Bioactivity rows</dt>
          <dd>{{ bioactivityValues().length }}</dd>
        </div>
        <div>
          <dt>Unique organisms</dt>
          <dd>{{ deduplicationResult()?.uniqueItems?.length ?? 0 }}</dd>
        </div>
        <div>
          <dt>Fiedler value</dt>
          <dd>{{ laplacianAnalysis()?.fiedlerValue ?? "Pending" }}</dd>
        </div>
      </dl>
    </section>

    <section class="graph-grid">
      <article class="card graph-card">
        <div class="card-header">
          <div>
            <p class="eyebrow">Graph Lab</p>
            <h2>Traversal, path, cycle, MST, and topological ordering</h2>
          </div>
          <div class="scenario-grid" aria-label="Graph algorithm selector">
            @for (scenario of graphScenarios; track scenario) {
              <button
                type="button"
                class="chip"
                [class.active]="graphScenario() === scenario"
                (click)="selectGraphScenario(scenario)"
              >
                {{ formatScenarioLabel(scenario) }}
              </button>
            }
          </div>
        </div>

        @if (activeGraphTrace(); as trace) {
          <app-cytoscape-graph
            [graph]="activeGraphDisplayGraph()"
            [state]="activeGraphStep()"
            [ariaLabel]="trace.algorithm + ' graph view'"
          />

          <div class="step-toolbar">
            <div>
              <p class="trace-title">{{ trace.algorithm }}</p>
              <p class="trace-copy">{{ trace.headline }}</p>
            </div>
            <div class="step-controls">
              <button
                type="button"
                class="chip ghost"
                (click)="stepGraphBackward()"
                [disabled]="graphStepIndex() === 0"
              >
                Previous
              </button>
              <span class="step-counter"
                >Step {{ graphStepIndex() + 1 }} / {{ trace.steps.length }}</span
              >
              <button
                type="button"
                class="chip ghost"
                (click)="stepGraphForward()"
                [disabled]="graphStepIndex() >= trace.steps.length - 1"
              >
                Next
              </button>
            </div>
          </div>

          @if (activeGraphStep(); as step) {
            <div class="step-callout">
              <p class="step-label">{{ step.label }}</p>
              <p>{{ step.detail }}</p>
            </div>
          }
        } @else {
          <p class="status-text">Loading graph fixtures...</p>
        }
      </article>

      <article class="card summary-card">
        <div class="card-header compact">
          <div>
            <p class="eyebrow">Trace Summary</p>
            <h2>Text fallback for every graph step</h2>
          </div>
        </div>

        @if (activeGraphTrace(); as trace) {
          <p class="summary-copy">{{ trace.detail }}</p>

          <dl class="metric-grid">
            @for (metric of graphMetrics(); track metric.label) {
              <div>
                <dt>{{ metric.label }}</dt>
                <dd>{{ metric.value }}</dd>
              </div>
            }
          </dl>

          @if (trace.order.length > 0) {
            <p class="sequence-title">Derived order</p>
            <ol class="sequence-list">
              @for (item of trace.order; track item) {
                <li>{{ item }}</li>
              }
            </ol>
          }

          <ol class="step-list">
            @for (step of trace.steps; track $index; let index = $index) {
              <li
                [class.current-step]="index === graphStepIndex()"
                (click)="graphStepIndex.set(index)"
              >
                <span class="step-index">{{ index + 1 }}</span>
                <div>
                  <p class="step-label">{{ step.label }}</p>
                  <p>{{ step.detail }}</p>
                </div>
              </li>
            }
          </ol>
        }
      </article>
    </section>

    <section class="analysis-grid graph-theory-grid">
      <article class="card analysis-card">
        <div class="card-header compact">
          <div>
            <p class="eyebrow">Molecular Metrics</p>
            <h2>Degree sequence, density, radius, and diameter</h2>
          </div>
        </div>

        @if (molecularMetrics(); as metrics) {
          <div class="sort-stats metric-triptych">
            <div>
              <span>Degree sequence</span>
              <strong>{{ metrics.degreeSequence.join(", ") }}</strong>
            </div>
            <div>
              <span>Graph density</span>
              <strong>{{ metrics.density }}</strong>
            </div>
            <div>
              <span>Diameter / radius</span>
              <strong>{{ metrics.diameter }} / {{ metrics.radius }}</strong>
            </div>
            <div>
              <span>Center atoms</span>
              <strong>{{ metrics.centerNodeIds.join(", ") }}</strong>
            </div>
          </div>

          <div class="table-frame">
            <table>
              <thead>
                <tr>
                  <th scope="col">Atom</th>
                  <th scope="col">Degree</th>
                  <th scope="col">Eccentricity</th>
                </tr>
              </thead>
              <tbody>
                @for (metric of metrics.nodeMetrics; track metric.nodeId) {
                  <tr>
                    <td>{{ metric.label }}</td>
                    <td>{{ metric.degree }}</td>
                    <td>{{ metric.eccentricity }}</td>
                  </tr>
                }
              </tbody>
            </table>
          </div>
        }
      </article>

      <article class="card analysis-card">
        <div class="card-header compact">
          <div>
            <p class="eyebrow">Spectral View</p>
            <h2>Laplacian and connectivity summary</h2>
          </div>
        </div>

        @if (laplacianAnalysis(); as analysis) {
          <p class="summary-copy">
            The second-smallest Laplacian eigenvalue is
            <strong>{{ analysis.fiedlerValue ?? 0 }}</strong
            >, which stays positive for this connected molecular graph.
          </p>

          <div class="sort-stats metric-triptych">
            <div>
              <span>Eigenvalues</span>
              <strong>{{ analysis.eigenvalues.join(", ") }}</strong>
            </div>
          </div>

          <div class="table-frame matrix-frame">
            <table>
              <thead>
                <tr>
                  <th scope="col">Row</th>
                  @for (column of matrixHeader(); track column) {
                    <th scope="col">{{ column }}</th>
                  }
                </tr>
              </thead>
              <tbody>
                @for (row of laplacianRows(); track row.label) {
                  <tr>
                    <td>{{ row.label }}</td>
                    @for (value of row.values; track $index) {
                      <td>{{ value }}</td>
                    }
                  </tr>
                }
              </tbody>
            </table>
          </div>
        }
      </article>

      <article class="card analysis-card dedup-card">
        <div class="card-header compact">
          <div>
            <p class="eyebrow">Morgan Propagation</p>
            <h2>Iterative node labels for circular-fingerprint intuition</h2>
          </div>
        </div>

        @if (morganAnalysis(); as analysis) {
          <p class="summary-copy">
            Label propagation stabilized after round {{ analysis.stabilizedAfterRound }}.
          </p>

          <ol class="step-list compact-list">
            @for (round of analysis.rounds; track round.round) {
              <li>
                <span class="step-index">{{ round.round }}</span>
                <div>
                  <p class="step-label">Round {{ round.round }}</p>
                  <p>{{ formatMorganLabels(round.labels) }}</p>
                  <p class="probe-copy">
                    Changed nodes: {{ round.changedNodeIds.join(", ") || "None" }}
                  </p>
                </div>
              </li>
            }
          </ol>
        }
      </article>
    </section>

    <section class="analysis-grid graph-theory-grid">
      <article class="card graph-card">
        <div class="card-header compact">
          <div>
            <p class="eyebrow">Reaction Networks</p>
            <h2>Pathway, reaction, taxonomy, and compound flow</h2>
          </div>
        </div>

        @if (reactionNetworkGraph(); as graph) {
          <app-cytoscape-graph [graph]="graph" ariaLabel="Reaction network graph" />

          @if (reactionNetworkSummary(); as summary) {
            <dl class="metric-grid">
              <div>
                <dt>Pathways</dt>
                <dd>{{ summary.pathwayCount }}</dd>
              </div>
              <div>
                <dt>Reactions</dt>
                <dd>{{ summary.reactionCount }}</dd>
              </div>
              <div>
                <dt>Compounds</dt>
                <dd>{{ summary.compoundCount }}</dd>
              </div>
              <div>
                <dt>Taxa</dt>
                <dd>{{ summary.taxonomyCount }}</dd>
              </div>
              <div>
                <dt>Edges</dt>
                <dd>{{ summary.edgeCount }}</dd>
              </div>
              <div>
                <dt>CID 4 links</dt>
                <dd>{{ summary.cid4ParticipationEdgeCount }}</dd>
              </div>
            </dl>
          }

          @if (reactionNetworkTopologicalTrace(); as trace) {
            <p class="summary-copy">{{ trace.detail }}</p>

            <p class="sequence-title">Topological order</p>
            <ol class="sequence-list">
              @for (item of reactionNetworkOrderLabels(); track item) {
                <li>{{ item }}</li>
              }
            </ol>
          }
        } @else {
          <p class="status-text">Loading reaction-network graph...</p>
        }
      </article>

      <article class="card analysis-card">
        <div class="card-header compact">
          <div>
            <p class="eyebrow">Reaction Spectral View</p>
            <h2>Undirected projection for Laplacian connectivity</h2>
          </div>
        </div>

        @if (reactionNetworkLaplacianAnalysis(); as analysis) {
          <p class="summary-copy">
            The directed reaction network is projected to an undirected graph so the Laplacian stays
            symmetric. The smallest non-zero eigenvalue is
            <strong>{{ analysis.fiedlerValue ?? 0 }}</strong
            >.
          </p>

          @if (reactionNetworkMetrics(); as metrics) {
            <div class="sort-stats metric-triptych">
              <div>
                <span>Connected components</span>
                <strong>{{ metrics.connectedComponentCount }}</strong>
              </div>
              <div>
                <span>Density</span>
                <strong>{{ metrics.density }}</strong>
              </div>
              <div>
                <span>Diameter / radius</span>
                <strong>{{ metrics.diameter }} / {{ metrics.radius }}</strong>
              </div>
            </div>
          }

          <div class="table-frame matrix-frame">
            <table>
              <thead>
                <tr>
                  <th scope="col">Row</th>
                  @for (column of reactionNetworkMatrixHeader(); track column) {
                    <th scope="col">{{ column }}</th>
                  }
                </tr>
              </thead>
              <tbody>
                @for (row of reactionNetworkLaplacianRows(); track row.label) {
                  <tr>
                    <td>{{ row.label }}</td>
                    @for (value of row.values; track $index) {
                      <td>{{ value }}</td>
                    }
                  </tr>
                }
              </tbody>
            </table>
          </div>
        } @else {
          <p class="status-text">Loading reaction-network matrices...</p>
        }
      </article>
    </section>

    <section class="analysis-grid">
      <article class="card analysis-card">
        <div class="card-header compact">
          <div>
            <p class="eyebrow">Sorting</p>
            <h2>Merge sort versus quicksort</h2>
          </div>
          <div class="scenario-grid">
            @for (algorithm of sortAlgorithms; track algorithm) {
              <button
                type="button"
                class="chip"
                [class.active]="sortAlgorithm() === algorithm"
                (click)="selectSortAlgorithm(algorithm)"
              >
                {{ formatSortLabel(algorithm) }}
              </button>
            }
          </div>
        </div>

        @if (activeSortTrace(); as trace) {
          <div class="sort-stats">
            <div>
              <span>Comparisons</span>
              <strong>{{ trace.comparisons }}</strong>
            </div>
            <div>
              <span>Writes</span>
              <strong>{{ trace.writes }}</strong>
            </div>
            <div>
              <span>Sorted output</span>
              <strong>{{ trace.sortedValues.join(", ") }}</strong>
            </div>
          </div>

          <div class="step-toolbar compact-toolbar">
            <span class="step-counter"
              >Step {{ sortStepIndex() + 1 }} / {{ trace.steps.length }}</span
            >
            <div class="step-controls">
              <button
                type="button"
                class="chip ghost"
                (click)="stepSortBackward()"
                [disabled]="sortStepIndex() === 0"
              >
                Previous
              </button>
              <button
                type="button"
                class="chip ghost"
                (click)="stepSortForward()"
                [disabled]="sortStepIndex() >= trace.steps.length - 1"
              >
                Next
              </button>
            </div>
          </div>

          @if (activeSortStep(); as step) {
            <div class="step-callout">
              <p class="step-label">{{ step.label }}</p>
              <p>{{ step.detail }}</p>
            </div>
            <div class="value-bar-grid" aria-label="Sorting trace bars">
              @for (value of step.values; track $index; let index = $index) {
                <div
                  class="value-bar"
                  [class.active-bar]="step.activeIndices.includes(index)"
                  [style.height.%]="sortBarHeight(value)"
                >
                  <span>{{ value }}</span>
                </div>
              }
            </div>
          }
        }
      </article>

      <article class="card analysis-card">
        <div class="card-header compact">
          <div>
            <p class="eyebrow">Binary Search</p>
            <h2>Find the first IC50 at or below 100 µM</h2>
          </div>
        </div>

        @if (binarySearchTrace(); as trace) {
          <p class="summary-copy">
            {{
              trace.index >= 0
                ? "First qualifying value is " +
                  trace.value +
                  " at sorted index " +
                  trace.index +
                  "."
                : "No values met the threshold."
            }}
          </p>

          <ol class="step-list compact-list">
            @for (step of trace.steps; track $index) {
              <li>
                <span class="step-index">{{ $index + 1 }}</span>
                <div>
                  <p class="step-label">{{ step.label }}</p>
                  <p>{{ step.detail }}</p>
                  <p class="probe-copy">
                    low={{ step.low }}, mid={{ step.middle }}, high={{ step.high }}
                  </p>
                </div>
              </li>
            }
          </ol>
        }
      </article>

      <article class="card analysis-card dedup-card">
        <div class="card-header compact">
          <div>
            <p class="eyebrow">Hash-based Dedup</p>
            <h2>Source organism uniqueness via map semantics</h2>
          </div>
        </div>

        @if (deduplicationResult(); as result) {
          <div class="sort-stats">
            <div>
              <span>Total rows</span>
              <strong>{{ taxonomyRows().length }}</strong>
            </div>
            <div>
              <span>Unique rows</span>
              <strong>{{ result.uniqueItems.length }}</strong>
            </div>
            <div>
              <span>Duplicate keys</span>
              <strong>{{ result.duplicateKeys.join(", ") || "None" }}</strong>
            </div>
          </div>

          <div class="table-frame">
            <table>
              <thead>
                <tr>
                  <th scope="col">Status</th>
                  <th scope="col">Organism</th>
                  <th scope="col">Taxonomy ID</th>
                </tr>
              </thead>
              <tbody>
                @for (row of taxonomyRows(); track $index) {
                  <tr [class.row-duplicate]="result.duplicateKeys.includes(row.sourceOrganism)">
                    <td>
                      {{
                        result.duplicateKeys.includes(row.sourceOrganism) ? "Duplicate" : "Unique"
                      }}
                    </td>
                    <td>{{ row.sourceOrganism }}</td>
                    <td>{{ row.taxonomyId }}</td>
                  </tr>
                }
              </tbody>
            </table>
          </div>
        }
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

      .hero,
      .graph-grid,
      .analysis-grid {
        display: grid;
        gap: 20px;
      }

      .hero {
        grid-template-columns: minmax(0, 1.6fr) minmax(280px, 0.9fr);
        margin-bottom: 20px;
      }

      .graph-grid {
        grid-template-columns: minmax(0, 1.65fr) minmax(320px, 0.95fr);
      }

      .analysis-grid {
        grid-template-columns: repeat(2, minmax(0, 1fr));
        margin-top: 20px;
      }

      .dedup-card {
        grid-column: 1 / -1;
      }

      .graph-theory-grid {
        margin-top: 20px;
      }

      .hero-meta,
      .metric-grid {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 12px;
        margin: 0;
      }

      .hero-meta div,
      .metric-grid div,
      .sort-stats div {
        padding: 14px;
        border-radius: 18px;
        background: rgba(16, 35, 61, 0.05);
      }

      dt,
      .sort-stats span {
        font-size: 0.74rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: #6d7f94;
      }

      dd,
      .sort-stats strong {
        margin: 8px 0 0;
        display: block;
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
      h2,
      p {
        margin: 0;
      }

      h1 {
        font-size: clamp(2rem, 5vw, 3.2rem);
        line-height: 0.96;
      }

      h2 {
        font-size: 1.35rem;
      }

      .lede,
      .summary-copy,
      .trace-copy,
      .probe-copy,
      .step-list p,
      .step-callout p:last-child {
        line-height: 1.6;
        color: #38516f;
      }

      .lede {
        margin-top: 14px;
        max-width: 62ch;
      }

      .card-header,
      .step-toolbar,
      .step-controls,
      .scenario-grid {
        display: flex;
        gap: 12px;
      }

      .card-header,
      .step-toolbar {
        align-items: start;
        justify-content: space-between;
      }

      .card-header {
        margin-bottom: 18px;
      }

      .card-header.compact {
        margin-bottom: 14px;
      }

      .scenario-grid {
        flex-wrap: wrap;
        justify-content: end;
      }

      .chip {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        border: 0;
        border-radius: 999px;
        padding: 11px 16px;
        font: inherit;
        font-weight: 700;
        color: #10233d;
        background: #dbeaf1;
        cursor: pointer;
      }

      .chip.active {
        background: #10233d;
        color: #f8fbfc;
      }

      .chip.ghost {
        background: #f2e8da;
      }

      .chip:disabled {
        opacity: 0.55;
        cursor: not-allowed;
      }

      .chip:focus-visible,
      .step-list li:focus-visible {
        outline: 3px solid #c45a1b;
        outline-offset: 3px;
      }

      .step-toolbar,
      .sort-stats,
      .value-bar-grid {
        margin-top: 16px;
      }

      .compact-toolbar {
        align-items: center;
      }

      .trace-title,
      .step-label,
      .sequence-title {
        font-weight: 800;
      }

      .step-counter {
        align-self: center;
        font-weight: 700;
        color: #38516f;
      }

      .step-callout {
        margin-top: 14px;
        padding: 14px 16px;
        border-radius: 18px;
        background: rgba(16, 35, 61, 0.05);
      }

      .metric-grid,
      .sort-stats {
        margin-top: 14px;
      }

      .sequence-list,
      .step-list {
        list-style: none;
        padding: 0;
      }

      .sequence-list {
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
        margin: 12px 0 0;
      }

      .sequence-list li {
        padding: 8px 12px;
        border-radius: 999px;
        background: rgba(16, 35, 61, 0.05);
        font-weight: 700;
      }

      .step-list {
        margin: 18px 0 0;
        display: grid;
        gap: 10px;
        max-height: 560px;
        overflow: auto;
      }

      .step-list.compact-list {
        max-height: none;
      }

      .step-list li {
        display: grid;
        grid-template-columns: auto 1fr;
        gap: 14px;
        align-items: start;
        padding: 12px 14px;
        border-radius: 18px;
        background: rgba(16, 35, 61, 0.04);
        cursor: pointer;
      }

      .current-step {
        background: rgba(31, 111, 139, 0.12) !important;
      }

      .step-index {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 30px;
        height: 30px;
        border-radius: 999px;
        background: #10233d;
        color: #f8fbfc;
        font-weight: 800;
        flex: none;
      }

      .value-bar-grid {
        display: grid;
        grid-template-columns: repeat(10, minmax(0, 1fr));
        align-items: end;
        gap: 10px;
        min-height: 220px;
      }

      .value-bar {
        display: flex;
        align-items: end;
        justify-content: center;
        padding: 10px 6px;
        border-radius: 18px 18px 10px 10px;
        background: linear-gradient(180deg, #b9d2d8 0%, #7ca7b1 100%);
        color: #10233d;
        font-weight: 800;
      }

      .value-bar span {
        writing-mode: vertical-rl;
        transform: rotate(180deg);
      }

      .active-bar {
        background: linear-gradient(180deg, #f0c589 0%, #c45a1b 100%);
        color: #fffaf4;
      }

      .table-frame {
        overflow: auto;
        border-radius: 18px;
        border: 1px solid rgba(16, 35, 61, 0.08);
        background: rgba(255, 255, 255, 0.56);
        margin-top: 16px;
      }

      table {
        width: 100%;
        border-collapse: collapse;
        min-width: 420px;
      }

      .matrix-frame table {
        min-width: 760px;
      }

      th,
      td {
        padding: 10px 12px;
        border-bottom: 1px solid rgba(16, 35, 61, 0.06);
        text-align: left;
        font-size: 0.95rem;
      }

      .row-duplicate {
        background: rgba(196, 90, 27, 0.08);
      }

      .status-text {
        padding: 14px 16px;
        border-radius: 18px;
        background: #fff3cf;
      }

      @media (max-width: 1120px) {
        .hero,
        .graph-grid,
        .analysis-grid {
          grid-template-columns: 1fr;
        }

        .card-header,
        .step-toolbar {
          flex-direction: column;
        }

        .scenario-grid {
          justify-content: start;
        }
      }

      @media (max-width: 720px) {
        .hero-meta,
        .metric-grid {
          grid-template-columns: 1fr;
        }

        .value-bar-grid {
          gap: 6px;
        }
      }
    `,
  ],
})
export class AlgorithmsPage {
  protected readonly graphScenarios = GRAPH_SCENARIOS
  protected readonly sortAlgorithms = SORT_ALGORITHMS

  protected readonly graphScenario = signal<GraphScenario>("bfs")
  protected readonly graphStepIndex = signal(0)
  protected readonly sortAlgorithm = signal<SortAlgorithm>("merge-sort")
  protected readonly sortStepIndex = signal(0)

  protected readonly moleculeQuery = injectQuery(() => ({
    queryKey: ["algorithms", "cid4", "conformer"],
    queryFn: fetchMolecule,
  }))

  protected readonly pathwayQuery = injectQuery(() => ({
    queryKey: ["algorithms", "pathway"],
    queryFn: fetchPathway,
  }))

  protected readonly reactionNetworkQuery = injectQuery(() => ({
    queryKey: ["algorithms", "reaction-network"],
    queryFn: fetchReactionNetwork,
  }))

  protected readonly bioactivityQuery = injectQuery(() => ({
    queryKey: ["algorithms", "bioactivity"],
    queryFn: fetchBioactivity,
  }))

  protected readonly taxonomyQuery = injectQuery(() => ({
    queryKey: ["algorithms", "taxonomy"],
    queryFn: fetchTaxonomy,
  }))

  protected readonly moleculeGraph = computed(() => {
    const molecule = this.moleculeQuery.data()
    return molecule ? mapMoleculeToAlgorithmGraph(molecule) : null
  })

  protected readonly weightedBondGraph = computed(() => {
    const molecule = this.moleculeQuery.data()
    return molecule ? buildWeightedBondGraph(molecule) : null
  })

  protected readonly completeDistanceGraph = computed(() => {
    const molecule = this.moleculeQuery.data()
    return molecule ? buildCompleteDistanceGraph(molecule) : null
  })

  protected readonly activeGraphTrace = computed<GraphTraceResult | null>(() => {
    const scenario = this.graphScenario()

    if (scenario === "topological-sort") {
      const pathway = this.pathwayQuery.data()
      return pathway ? buildTopologicalSortTrace(pathway) : null
    }

    const moleculeGraph = this.moleculeGraph()
    const weightedBondGraph = this.weightedBondGraph()

    if (!moleculeGraph) {
      return null
    }

    switch (scenario) {
      case "bfs":
        return buildBfsTrace(moleculeGraph, "1")
      case "dfs":
        return buildDfsTrace(moleculeGraph, "1")
      case "weighted-shortest-path":
        return weightedBondGraph ? buildShortestPathTrace(weightedBondGraph, "1", "2") : null
      case "shortest-path":
        return buildShortestPathTrace(moleculeGraph, "1", "2")
      case "morgan-labeling":
        return buildMorganTrace(moleculeGraph)
      case "cycle-detection":
        return buildCycleDetectionTrace(moleculeGraph, "1")
      case "minimum-spanning-tree": {
        const completeGraph = this.completeDistanceGraph()
        return completeGraph ? buildMinimumSpanningTreeTrace(completeGraph) : null
      }
      default:
        return null
    }
  })

  protected readonly activeGraphDisplayGraph = computed(() => {
    const trace = this.activeGraphTrace()
    const scenario = this.graphScenario()

    if (scenario === "minimum-spanning-tree") {
      return trace?.graph ?? emptyGraph("mst")
    }

    if (scenario === "weighted-shortest-path") {
      return this.weightedBondGraph() ?? emptyGraph("weighted-bonds")
    }

    if (scenario === "topological-sort") {
      return this.pathwayQuery.data() ?? emptyGraph("pathway")
    }

    return this.moleculeGraph() ?? emptyGraph("molecule")
  })

  protected readonly activeGraphStep = computed(() => {
    const trace = this.activeGraphTrace()
    const index = this.graphStepIndex()
    return trace?.steps[index] ?? null
  })

  protected readonly graphScenarioLabel = computed(() =>
    this.formatScenarioLabel(this.graphScenario()),
  )
  protected readonly graphMetrics = computed(() => {
    const metrics = this.activeGraphTrace()?.metrics ?? {}
    return Object.entries(metrics).map(([label, value]) => ({
      label: humanizeMetricLabel(label),
      value: String(value),
    }))
  })
  protected readonly molecularMetrics = computed<MolecularGraphMetrics | null>(() => {
    const graph = this.moleculeGraph()
    return graph ? buildMolecularGraphMetrics(graph) : null
  })
  protected readonly reactionNetworkGraph = computed(
    () => this.reactionNetworkQuery.data()?.graph ?? null,
  )
  protected readonly reactionNetworkSummary = computed(
    () => this.reactionNetworkQuery.data()?.summary ?? null,
  )
  protected readonly reactionNetworkUndirectedGraph = computed<AlgorithmGraph | null>(() => {
    const graph = this.reactionNetworkGraph()
    return graph ? asUndirectedGraph(graph) : null
  })
  protected readonly reactionNetworkTopologicalTrace = computed<GraphTraceResult | null>(() => {
    const graph = this.reactionNetworkGraph()
    return graph ? buildTopologicalSortTrace(graph) : null
  })
  protected readonly reactionNetworkMetrics = computed<MolecularGraphMetrics | null>(() => {
    const graph = this.reactionNetworkUndirectedGraph()
    return graph ? buildMolecularGraphMetrics(graph) : null
  })
  protected readonly reactionNetworkLaplacianAnalysis = computed<MatrixAnalysis | null>(() => {
    const graph = this.reactionNetworkUndirectedGraph()
    return graph ? buildLaplacianAnalysis(graph) : null
  })
  protected readonly reactionNetworkMatrixHeader = computed(() => {
    return this.reactionNetworkUndirectedGraph()?.nodes.map((node) => node.label) ?? []
  })
  protected readonly reactionNetworkLaplacianRows = computed(() => {
    const header = this.reactionNetworkMatrixHeader()
    const matrix = this.reactionNetworkLaplacianAnalysis()?.laplacianMatrix ?? []
    return matrix.map((values, index) => ({
      label: header[index] ?? String(index + 1),
      values,
    }))
  })
  protected readonly reactionNetworkOrderLabels = computed(() => {
    const trace = this.reactionNetworkTopologicalTrace()
    const graph = this.reactionNetworkGraph()
    if (!trace || !graph) {
      return []
    }

    const labelById = new Map(graph.nodes.map((node) => [node.id, node.label]))
    return trace.order.map((nodeId) => labelById.get(nodeId) ?? nodeId)
  })
  protected readonly laplacianAnalysis = computed<MatrixAnalysis | null>(() => {
    const graph = this.moleculeGraph()
    return graph ? buildLaplacianAnalysis(graph) : null
  })
  protected readonly morganAnalysis = computed<MorganAnalysisResult | null>(() => {
    const graph = this.moleculeGraph()
    return graph ? buildMorganAnalysis(graph, 4) : null
  })
  protected readonly matrixHeader = computed(() => {
    return this.moleculeGraph()?.nodes.map((node) => node.label) ?? []
  })
  protected readonly laplacianRows = computed(() => {
    const header = this.matrixHeader()
    const matrix = this.laplacianAnalysis()?.laplacianMatrix ?? []
    return matrix.map((values, index) => ({
      label: header[index] ?? String(index + 1),
      values,
    }))
  })

  protected readonly bioactivityValues = computed(
    () => this.bioactivityQuery.data()?.records.map((record) => record.activityValue) ?? [],
  )
  protected readonly mergeSortTrace = computed(() => buildMergeSortTrace(this.bioactivityValues()))
  protected readonly quickSortTrace = computed(() => buildQuickSortTrace(this.bioactivityValues()))
  protected readonly activeSortTrace = computed(() =>
    this.sortAlgorithm() === "merge-sort" ? this.mergeSortTrace() : this.quickSortTrace(),
  )
  protected readonly activeSortStep = computed(() => {
    const trace = this.activeSortTrace()
    return trace.steps[this.sortStepIndex()] ?? null
  })
  protected readonly binarySearchTrace = computed<BinarySearchTraceResult>(() => {
    return buildThresholdBinarySearchTrace(this.mergeSortTrace().sortedValues, 100)
  })
  protected readonly taxonomyRows = computed(() => this.taxonomyQuery.data()?.organisms ?? [])
  protected readonly deduplicationResult = computed<DeduplicationResult<TaxonomyRecord> | null>(
    () => {
      const rows = this.taxonomyRows()
      return rows.length > 0 ? deduplicateByKey(rows, (row) => row.sourceOrganism) : null
    },
  )

  constructor() {
    effect(
      () => {
        const steps = this.activeGraphTrace()?.steps.length ?? 0
        const maxIndex = Math.max(0, steps - 1)

        if (this.graphStepIndex() > maxIndex) {
          this.graphStepIndex.set(maxIndex)
        }
      },
      { allowSignalWrites: true },
    )

    effect(
      () => {
        const steps = this.activeSortTrace().steps.length
        const maxIndex = Math.max(0, steps - 1)

        if (this.sortStepIndex() > maxIndex) {
          this.sortStepIndex.set(maxIndex)
        }
      },
      { allowSignalWrites: true },
    )
  }

  protected selectGraphScenario(scenario: GraphScenario): void {
    this.graphScenario.set(scenario)
    this.graphStepIndex.set(0)
  }

  protected stepGraphBackward(): void {
    this.graphStepIndex.update((value) => Math.max(0, value - 1))
  }

  protected stepGraphForward(): void {
    const stepCount = this.activeGraphTrace()?.steps.length ?? 0
    this.graphStepIndex.update((value) => Math.min(Math.max(0, stepCount - 1), value + 1))
  }

  protected selectSortAlgorithm(algorithm: SortAlgorithm): void {
    this.sortAlgorithm.set(algorithm)
    this.sortStepIndex.set(0)
  }

  protected stepSortBackward(): void {
    this.sortStepIndex.update((value) => Math.max(0, value - 1))
  }

  protected stepSortForward(): void {
    const stepCount = this.activeSortTrace().steps.length
    this.sortStepIndex.update((value) => Math.min(Math.max(0, stepCount - 1), value + 1))
  }

  protected formatScenarioLabel(scenario: GraphScenario): string {
    switch (scenario) {
      case "bfs":
        return "BFS"
      case "dfs":
        return "DFS"
      case "weighted-shortest-path":
        return "Weighted path"
      case "shortest-path":
        return "Shortest path"
      case "morgan-labeling":
        return "Morgan labels"
      case "cycle-detection":
        return "Cycle detection"
      case "minimum-spanning-tree":
        return "MST"
      case "topological-sort":
        return "Topological sort"
    }
  }

  protected formatSortLabel(algorithm: SortAlgorithm): string {
    return algorithm === "merge-sort" ? "Merge sort" : "Quick sort"
  }

  protected sortBarHeight(value: number): number {
    const values = this.bioactivityValues()
    const max = Math.max(...values, 1)
    return (value / max) * 100
  }

  protected formatMorganLabels(labels: Record<string, number>): string {
    return Object.entries(labels)
      .map(([nodeId, value]) => `${nodeId}:${value}`)
      .join(" · ")
  }
}

async function fetchJson(url: string): Promise<unknown> {
  const response = await fetch(url)

  if (!response.ok) {
    throw new Error(`Request failed with status ${response.status}`)
  }

  return response.json() as Promise<unknown>
}

async function fetchMolecule(): Promise<MoleculeGraph> {
  return parseConformerPayload(await fetchJson("/api/cid4/conformer/1"))
}

async function fetchPathway(): Promise<AlgorithmGraph> {
  const payload = (await fetchJson("/api/algorithms/pathway")) as PathwayResponse
  return payload.graph
}

async function fetchReactionNetwork(): Promise<ReactionNetworkResponse> {
  return (await fetchJson("/api/algorithms/reaction-network")) as ReactionNetworkResponse
}

async function fetchBioactivity(): Promise<BioactivityResponse> {
  return (await fetchJson("/api/algorithms/bioactivity")) as BioactivityResponse
}

async function fetchTaxonomy(): Promise<TaxonomyResponse> {
  return (await fetchJson("/api/algorithms/taxonomy")) as TaxonomyResponse
}

function mapMoleculeToAlgorithmGraph(molecule: MoleculeGraph): AlgorithmGraph {
  const positions = normalizePositions(buildLayoutPositions(molecule, "source"))

  return {
    id: `molecule-${molecule.cid}`,
    title: molecule.title,
    directed: false,
    nodes: molecule.atoms.map((atom) => ({
      id: String(atom.id),
      label: `${atom.elementSymbol}${atom.id}`,
      x: positions.get(atom.id)?.x,
      y: positions.get(atom.id)?.y,
    })),
    edges: molecule.bonds.map((bond) => ({
      id: bond.id,
      label: String(bond.order),
      source: String(bond.source),
      target: String(bond.target),
      weight: 1,
    })),
  }
}

function buildCompleteDistanceGraph(molecule: MoleculeGraph): AlgorithmGraph {
  const positions = normalizePositions(buildLayoutPositions(molecule, "source"))
  const nodes = molecule.atoms.map((atom) => ({
    id: String(atom.id),
    label: `${atom.elementSymbol}${atom.id}`,
    x: positions.get(atom.id)?.x,
    y: positions.get(atom.id)?.y,
  }))
  const edges = molecule.atoms.flatMap((sourceAtom, sourceIndex) => {
    return molecule.atoms.slice(sourceIndex + 1).map((targetAtom) => ({
      id: `${sourceAtom.id}-${targetAtom.id}`,
      source: String(sourceAtom.id),
      target: String(targetAtom.id),
      label: euclideanDistance(sourceAtom, targetAtom).toFixed(2),
      weight: euclideanDistance(sourceAtom, targetAtom),
    }))
  })

  return {
    id: `complete-${molecule.cid}`,
    title: `${molecule.title} complete distance graph`,
    directed: false,
    nodes,
    edges,
  }
}

function buildWeightedBondGraph(molecule: MoleculeGraph): AlgorithmGraph {
  const positions = normalizePositions(buildLayoutPositions(molecule, "source"))
  const atomsById = new Map(molecule.atoms.map((atom) => [atom.id, atom]))

  return {
    id: `weighted-bonds-${molecule.cid}`,
    title: `${molecule.title} weighted bond graph`,
    directed: false,
    nodes: molecule.atoms.map((atom) => ({
      id: String(atom.id),
      label: `${atom.elementSymbol}${atom.id}`,
      x: positions.get(atom.id)?.x,
      y: positions.get(atom.id)?.y,
    })),
    edges: molecule.bonds.map((bond) => {
      const source = atomsById.get(bond.source)
      const target = atomsById.get(bond.target)
      const weight = source && target ? euclideanDistance(source, target) : 1

      return {
        id: bond.id,
        label: weight.toFixed(2),
        source: String(bond.source),
        target: String(bond.target),
        weight,
      }
    }),
  }
}

function asUndirectedGraph(graph: AlgorithmGraph): AlgorithmGraph {
  return {
    ...graph,
    directed: false,
  }
}

function buildMorganTrace(graph: AlgorithmGraph): GraphTraceResult {
  const analysis = buildMorganAnalysis(graph, 4)
  const finalRound = analysis.rounds.at(-1)

  return {
    algorithm: "Morgan label propagation",
    headline: `Stabilized after round ${analysis.stabilizedAfterRound}`,
    detail:
      "Each round re-labels atoms from their local neighborhoods to approximate the intuition behind circular fingerprints.",
    order: analysis.rounds.map((round) => `Round ${round.round}`),
    steps: analysis.rounds.map((round) => ({
      label: `Round ${round.round}`,
      detail: `Labels ${formatMorganRound(round.labels)}. Changed nodes: ${round.changedNodeIds.join(", ") || "None"}.`,
      activeNodeIds: round.changedNodeIds,
      activeEdgeIds: [],
      visitedNodeIds: graph.nodes.map((node) => node.id),
      frontierNodeIds: [],
      pathNodeIds: [],
      pathEdgeIds: [],
    })),
    metrics: {
      stabilizedAfterRound: analysis.stabilizedAfterRound,
      distinctLabels: new Set(Object.values(finalRound?.labels ?? {})).size,
    },
  }
}

function normalizePositions(points: Map<number, Point>): Map<number, Point> {
  const entries = [...points.entries()]

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

  return new Map(
    entries.map(([id, point]) => [
      id,
      {
        x: 80 + ((point.x - minX) / width) * 520,
        y: 60 + ((point.y - minY) / height) * 300,
      },
    ]),
  )
}

function euclideanDistance(
  left: MoleculeGraph["atoms"][number],
  right: MoleculeGraph["atoms"][number],
): number {
  const dx = left.x - right.x
  const dy = left.y - right.y
  const dz = left.z - right.z
  return Math.hypot(dx, dy, dz)
}

function humanizeMetricLabel(label: string): string {
  return label.replaceAll(/([A-Z])/g, " $1").replace(/^./, (value) => value.toUpperCase())
}

function formatMorganRound(labels: Record<string, number>): string {
  return Object.entries(labels)
    .map(([nodeId, value]) => `${nodeId}:${value}`)
    .join(", ")
}

function emptyGraph(id: string): AlgorithmGraph {
  return {
    id,
    title: id,
    directed: false,
    nodes: [],
    edges: [],
  }
}
