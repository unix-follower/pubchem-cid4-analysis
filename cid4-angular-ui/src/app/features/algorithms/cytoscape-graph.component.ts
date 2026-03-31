import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  ElementRef,
  afterNextRender,
  effect,
  inject,
  input,
  viewChild,
} from "@angular/core"
import type cytoscape from "cytoscape"

import { AlgorithmGraph, GraphTraceStep } from "../../core/algorithms/types"

@Component({
  selector: "app-cytoscape-graph",
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: {
    class: "cytoscape-host",
  },
  template: `
    <div #canvas class="cytoscape-canvas" role="img" [attr.aria-label]="ariaLabel()"></div>
  `,
  styles: [
    `
      :host {
        display: block;
        min-height: 420px;
      }

      .cytoscape-canvas {
        width: 100%;
        min-height: 420px;
        border-radius: 24px;
        background:
          radial-gradient(circle at top left, rgba(244, 211, 163, 0.55), transparent 25%),
          linear-gradient(180deg, #fcfaf5 0%, #eef5f7 100%);
        box-shadow: inset 0 0 0 1px rgba(16, 35, 61, 0.08);
      }
    `,
  ],
})
export class CytoscapeGraphComponent {
  readonly graph = input.required<AlgorithmGraph>()
  readonly state = input<GraphTraceStep | null>(null)
  readonly ariaLabel = input("Algorithm graph view")

  private readonly canvasRef = viewChild<ElementRef<HTMLDivElement>>("canvas")
  private readonly destroyRef = inject(DestroyRef)

  private cytoscapeFactory: typeof cytoscape | null = null
  private cy: cytoscape.Core | null = null

  constructor() {
    afterNextRender(() => {
      void this.ensureCytoscapeLoaded()
    })

    effect(() => {
      this.graph()
      this.state()
      void this.renderGraph()
    })

    this.destroyRef.onDestroy(() => {
      this.cy?.destroy()
      this.cy = null
    })
  }

  private async ensureCytoscapeLoaded(): Promise<void> {
    if (typeof window === "undefined") {
      return
    }

    if (this.cytoscapeFactory) {
      return
    }

    const module = await import("cytoscape")
    this.cytoscapeFactory = module.default
    await this.renderGraph()
  }

  private async renderGraph(): Promise<void> {
    const host = this.canvasRef()?.nativeElement

    if (!host || typeof window === "undefined") {
      return
    }

    if (!this.cytoscapeFactory) {
      return
    }

    const graph = this.graph()
    const elements = buildElements(graph)

    if (!this.cy) {
      this.cy = this.cytoscapeFactory({
        container: host,
        elements,
        layout: selectLayout(graph),
        style: buildStylesheet(),
        userZoomingEnabled: true,
        userPanningEnabled: true,
        boxSelectionEnabled: false,
      })
    } else {
      this.cy.elements().remove()
      this.cy.add(elements)
      this.cy.layout(selectLayout(graph)).run()
    }

    applyTraceState(this.cy, this.state())
    this.cy.fit(undefined, 32)
  }
}

function buildElements(graph: AlgorithmGraph): cytoscape.ElementDefinition[] {
  return [
    ...graph.nodes.map((node) => ({
      data: {
        id: node.id,
        label: node.label,
      },
      position:
        node.x !== undefined && node.y !== undefined
          ? {
              x: node.x,
              y: node.y,
            }
          : undefined,
    })),
    ...graph.edges.map((edge) => ({
      data: {
        id: edge.id,
        label: edge.label ?? "",
        weight: edge.weight ?? 1,
        source: edge.source,
        target: edge.target,
        directed: graph.directed ? 1 : 0,
      },
    })),
  ]
}

function selectLayout(graph: AlgorithmGraph): cytoscape.LayoutOptions {
  const hasPresetPositions = graph.nodes.every(
    (node) => node.x !== undefined && node.y !== undefined,
  )

  if (hasPresetPositions) {
    return {
      name: "preset",
      fit: true,
      padding: 32,
    }
  }

  return {
    name: "breadthfirst",
    directed: graph.directed,
    padding: 32,
    spacingFactor: 1.15,
  }
}

function buildStylesheet(): cytoscape.StylesheetCSS[] {
  return [
    {
      selector: "node",
      css: {
        "background-color": "#d8e6ea",
        color: "#10233d",
        label: "data(label)",
        "font-size": 11,
        "font-weight": 700,
        "text-wrap": "wrap",
        "text-max-width": "84px",
        "text-valign": "center",
        "text-halign": "center",
        width: 48,
        height: 48,
        "border-width": 2,
        "border-color": "rgba(16, 35, 61, 0.12)",
      },
    },
    {
      selector: "edge",
      css: {
        width: 3,
        label: "data(label)",
        color: "#5d728c",
        "font-size": 10,
        "curve-style": "bezier",
        "line-color": "#9fb1c2",
        "target-arrow-color": "#9fb1c2",
        "target-arrow-shape": "none",
      },
    },
    {
      selector: "edge[directed = 1]",
      css: {
        "target-arrow-shape": "triangle",
      },
    },
    {
      selector: ".is-visited",
      css: {
        "background-color": "#8fb9c3",
      },
    },
    {
      selector: ".is-frontier",
      css: {
        "background-color": "#f2cf8a",
      },
    },
    {
      selector: ".is-active",
      css: {
        "background-color": "#c45a1b",
        color: "#fffdf9",
      },
    },
    {
      selector: ".is-path",
      css: {
        "background-color": "#2f6b39",
        "line-color": "#2f6b39",
        "target-arrow-color": "#2f6b39",
      },
    },
  ]
}

function applyTraceState(cy: cytoscape.Core, state: GraphTraceStep | null): void {
  cy.elements().removeClass("is-visited is-frontier is-active is-path")

  if (!state) {
    return
  }

  applyClass(cy, state.visitedNodeIds, "is-visited")
  applyClass(cy, state.frontierNodeIds, "is-frontier")
  applyClass(cy, state.activeNodeIds, "is-active")
  applyClass(cy, state.activeEdgeIds, "is-active")
  applyClass(cy, state.pathNodeIds, "is-path")
  applyClass(cy, state.pathEdgeIds, "is-path")
}

function applyClass(cy: cytoscape.Core, ids: string[], className: string): void {
  for (const id of ids) {
    cy.$id(id).addClass(className)
  }
}
